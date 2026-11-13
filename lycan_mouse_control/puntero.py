"""Posición del puntero: mapeo + One Euro en píxeles + zona muerta + rebobinado/ancla del
pellizco (clic limpio) + modo relativo opcional.

Es lógica pura: devuelve acciones ``Mover`` (o None); no toca Windows.
"""
from __future__ import annotations

import math
from collections import deque

from .acciones import Mover
from .filtros import OneEuro
from .mapeo import Mapeo

HISTORIA_S = 0.6
V_QUIETO = 60.0   # px/s: por debajo, la mano se considera quieta
V_CIERRE = 60.0   # px/s: por encima, la punta se mueve respecto de los nudillos (el dedo se cierra)
MIN_CIERRE_PX = 6.0  # recorrido mínimo de la punta respecto de los nudillos para contar como cierre
MANO_QUIETA_PX = 12.0  # si los nudillos se movieron más que esto durante el cierre, la mano no estaba quieta


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Puntero:
    def __init__(self, mapeo: Mapeo, cfg: dict | None = None, pos_cursor=None):
        cfg = cfg or {}
        self.mapeo = mapeo
        # función que da la posición REAL del cursor (x, y) o None: en modo relativo (touchpad)
        # el puntero sigue desde donde está el cursor, aunque el usuario haya movido el ratón
        self.pos_cursor = pos_cursor
        self.mincutoff = float(cfg.get("mincutoff", 0.5))
        self.beta = float(cfg.get("beta", 0.015))
        self.dcutoff = float(cfg.get("dcutoff", 1.0))
        self.zona_muerta = float(cfg.get("zona_muerta_px", 1.5))
        self.umbral_arrastre = float(cfg.get("umbral_arrastre_px", 14))
        self.rebobinado_s = float(cfg.get("rebobinado_ms", 100)) / 1000.0
        self.dibujo_fino = bool(cfg.get("dibujo_fino", False))
        self.relativo = cfg.get("modo", "absoluto") == "relativo"
        rel = cfg.get("relativo") or {}
        self.gmin = float(rel.get("gmin", 0.6))
        self.gmax = float(rel.get("gmax", 3.0))
        self.fx = OneEuro()
        self.fy = OneEuro()
        # Referencia del arrastre: los nudillos (5 y 9), que no se mueven al abrir o cerrar el
        # pellizco. La punta del índice sube ~200 px al estirar el dedo y haría un arrastre.
        self.frx = OneEuro()
        self.fry = OneEuro()
        self._aplicar_filtro()
        self.hist: deque = deque()
        self.hist_ref: deque = deque()     # (t, x, y, rx, ry): punta filtrada y nudillos filtrados
        self.ult_enviado: tuple[int, int] | None = None
        self.pos: tuple[float, float] | None = None      # última posición filtrada
        self.ancla: tuple[float, float] | None = None
        self.pos_al_anclar: tuple[float, float] | None = None
        self.pos_ref: tuple[float, float] | None = None
        self.ref_al_anclar: tuple[float, float] | None = None
        self.arrastrando = False
        self.congelado_hasta = -1.0
        self.t_fuera_desde: float | None = None
        self.cerca_borde = False
        self._rel_prev: tuple[float, float, float] | None = None
        self._rel_pos: tuple[float, float] | None = None

    # ---- configuración ----
    def _aplicar_filtro(self):
        if self.dibujo_fino:
            mc, b = 0.3, 0.01
        else:
            mc, b = self.mincutoff, self.beta
        for f in (self.fx, self.fy, self.frx, self.fry):
            f.mincutoff, f.beta, f.dcutoff = mc, b, self.dcutoff

    def poner_dibujo_fino(self, si: bool):
        self.dibujo_fino = bool(si)
        self._aplicar_filtro()

    def configurar(self, cfg: dict):
        self.__init__(self.mapeo, cfg, self.pos_cursor)  # noqa: PLC2801 (reconstrucción simple)

    def reset(self):
        """Al activar, al reaparecer la mano, al salir de un gesto de dos manos o cambiar de monitor."""
        self.fx.reset()
        self.fy.reset()
        self.frx.reset()
        self.fry.reset()
        self.hist.clear()
        self.hist_ref.clear()
        self.pos = None
        self.pos_ref = None
        self.ancla = None
        self.pos_al_anclar = None
        self.ref_al_anclar = None
        self.arrastrando = False
        self.t_fuera_desde = None
        self._rel_prev = None
        # modo relativo: la base se vuelve a tomar del cursor real (puede haber cambiado de
        # monitor o el usuario pudo mover el ratón físico mientras estaba en pausa)
        self._rel_pos = None

    # ---- observar la mano ----
    def observar(self, t: float, u: float, v: float, embrague: bool = False, ref=None):
        """Filtra la punta del índice (u, v en 0..1 de la imagen). Devuelve (x, y) en píxeles.

        ``ref`` (opcional): punto de la mano que no se mueve al abrir o cerrar los dedos
        (promedio de los nudillos 5 y 9); con él se mide el desplazamiento del arrastre."""
        if not (math.isfinite(u) and math.isfinite(v)):
            return self.pos
        if ref is not None and math.isfinite(ref[0]) and math.isfinite(ref[1]):
            # sin recortar a la zona: solo importa la diferencia
            rx = float(ref[0]) * self.mapeo.px_por_unidad_x
            ry = float(ref[1]) * self.mapeo.px_por_unidad_y
            self.pos_ref = (self.frx.filtrar(rx, t), self.fry.filtrar(ry, t))
        else:
            self.pos_ref = None
        dentro = self.mapeo.dentro(u, v)
        self.cerca_borde = self.mapeo.cerca_del_borde(u, v)
        if dentro:
            self.t_fuera_desde = None
        elif self.t_fuera_desde is None:
            self.t_fuera_desde = t
        if self.relativo:
            x, y = self._relativo(t, u, v, embrague)
        else:
            x, y = self.mapeo.a_pantalla(u, v)
        x = self.fx.filtrar(x, t)
        y = self.fy.filtrar(y, t)
        self.pos = (x, y)
        self.hist.append((t, x, y))
        while self.hist and t - self.hist[0][0] > HISTORIA_S:
            self.hist.popleft()
        if self.pos_ref is not None and not self.relativo:
            # punta y nudillos juntos: la diferencia solo cambia cuando el dedo se mueve
            # respecto de la mano (por ejemplo, al cerrar el pellizco)
            self.hist_ref.append((t, x, y, self.pos_ref[0], self.pos_ref[1]))
        else:
            self.hist_ref.clear()
        while self.hist_ref and t - self.hist_ref[0][0] > HISTORIA_S:
            self.hist_ref.popleft()
        return self.pos

    def _relativo(self, t, u, v, embrague):
        m = self.mapeo.monitor
        if self._rel_pos is None:
            base = None
            if self.pos_cursor is not None:
                try:
                    base = self.pos_cursor()
                except Exception:  # noqa: BLE001 - nunca romper el puntero por esto
                    base = None
            if base is None:
                base = (m.x + m.ancho / 2.0, m.y + m.alto / 2.0)
            bx = min(max(float(base[0]), m.x), m.x + m.ancho - 1)
            by = min(max(float(base[1]), m.y), m.y + m.alto - 1)
            self._rel_pos = (bx, by)
        if self._rel_prev is not None and not embrague:
            t0, u0, v0 = self._rel_prev
            dt = max(t - t0, 1e-3)
            # u va normalizado por el ancho de la cámara y v por el alto: se pasa v a "unidades
            # de ancho" para que la misma distancia física mueva lo mismo en x que en y.
            asp = float(getattr(self.mapeo, "aspecto_cam", 4 / 3) or 4 / 3)
            du, dv = u - u0, (v - v0) / asp
            vel = math.hypot(du, dv) / dt
            g = self.gmin + (self.gmax - self.gmin) * _smoothstep((vel - 0.05) / (0.8 - 0.05))
            x = self._rel_pos[0] + du * m.ancho * g
            y = self._rel_pos[1] + dv * m.ancho * g
            x = min(max(x, m.x), m.x + m.ancho - 1)
            y = min(max(y, m.y), m.y + m.alto - 1)
            self._rel_pos = (x, y)
        self._rel_prev = (t, u, v)
        return self._rel_pos

    def fuera_mucho(self, t: float) -> bool:
        return self.t_fuera_desde is not None and t - self.t_fuera_desde > 0.5

    def posicion_en(self, t_obj: float):
        """Posición filtrada más antigua con tiempo >= t_obj (rebobinado)."""
        for ht, hx, hy in self.hist:
            if ht >= t_obj - 1e-9:
                return (hx, hy)
        return self.pos

    def _punto_quieto(self, t_ref: float):
        """Último punto en que la mano estaba quieta entre t_ref-250 ms y t_ref-rebobinado.

        Al cerrar el pellizco la punta del índice se corre hacia el pulgar justo antes de que se
        reconozca el pellizco. Si la mano venía quieta, el clic debe caer donde estaba quieta;
        si venía moviéndose todo el tiempo, se usa el rebobinado normal (~100 ms)."""
        objetivo = t_ref - self.rebobinado_s
        limite = t_ref - 0.25
        h = list(self.hist)
        for i in range(len(h) - 1, 0, -1):
            t1, x1, y1 = h[i]
            if t1 > objetivo + 1e-9:
                continue
            if t1 < limite:
                break
            t0, x0, y0 = h[i - 1]
            v = math.hypot(x1 - x0, y1 - y0) / max(t1 - t0, 1e-3)
            if v < V_QUIETO:
                return (x1, y1)
        return None

    def _antes_del_cierre(self):
        """Dónde apuntaba la punta justo antes de que el dedo empezara a cerrarse (pellizco).

        Se mira la diferencia punta - nudillos: mientras la mano se mueve entera (o está quieta)
        casi no cambia; cuando el índice baja hacia el pulgar, cambia rápido. Se busca hacia
        atrás (hasta 600 ms) el último tramo en que cambiaba y se toma la punta en el cuadro
        anterior a ese tramo, siempre que los nudillos (la mano) hayan seguido quietos. Así un
        pellizco cerrado despacio (300-500 ms) cae donde estaba el puntero y no a mitad de la
        bajada. Devuelve None si no se ve un cierre del dedo con la mano quieta (entonces se usa
        el método de siempre: punto quieto o rebobinado de 100 ms)."""
        h = list(self.hist_ref)
        if len(h) < 3:
            return None

        def vel(i):
            t0, x0, y0, r0x, r0y = h[i - 1]
            t1, x1, y1, r1x, r1y = h[i]
            return math.hypot((x1 - r1x) - (x0 - r0x), (y1 - r1y) - (y0 - r0y)) / max(t1 - t0, 1e-3)

        n = len(h) - 1
        t_fin = h[n][0]
        i = n
        # el dedo ya terminó de cerrar y se esperaba la confirmación del pellizco
        while i > 0 and vel(i) < V_CIERRE and t_fin - h[i][0] < 0.2:
            i -= 1
        if i == 0 or vel(i) < V_CIERRE:
            return None
        recorrido = 0.0
        while i > 0 and vel(i) >= V_CIERRE:
            t0, t1 = h[i - 1][0], h[i][0]
            recorrido += vel(i) * max(t1 - t0, 1e-3)
            i -= 1
        if recorrido < MIN_CIERRE_PX:
            return None
        _, x, y, rx, ry = h[i]
        _, _, _, rx_n, ry_n = h[n]
        if math.hypot(rx_n - rx, ry_n - ry) > MANO_QUIETA_PX:
            return None          # la mano entera se movió: se usa el rebobinado de siempre
        return (x, y)

    # ---- enviar ----
    def _enviar(self, x: float, y: float, umbral: float | None = None):
        xi, yi = int(round(x)), int(round(y))
        if self.ult_enviado is not None:
            ux, uy = self.ult_enviado
            lim = self.zona_muerta if umbral is None else umbral
            if math.hypot(x - ux, y - uy) < lim or (xi, yi) == (ux, uy):
                return None
        self.ult_enviado = (xi, yi)
        return Mover(xi, yi)

    def congelado(self, t: float) -> bool:
        return t < self.congelado_hasta

    def mover(self, t: float):
        """Puntero libre: sigue a la mano (con zona muerta). None si no hay que mover."""
        if self.pos is None or self.congelado(t) or self.fuera_mucho(t):
            return None
        if self.ancla is not None:
            return self.mover_anclado(t)
        return self._enviar(*self.pos)

    def anclar(self, t_ref: float):
        """Pellizco confirmado: rebobina a t_ref - rebobinado y fija el ancla. Devuelve Mover o None."""
        if self.pos is None:
            return None
        self.ancla = (self._antes_del_cierre() or self._punto_quieto(t_ref)
                      or self.posicion_en(t_ref - self.rebobinado_s) or self.pos)
        self.pos_al_anclar = self.pos
        self.ref_al_anclar = self.pos_ref
        self.arrastrando = False
        return self._enviar(*self.ancla, umbral=0.5)

    def mover_anclado(self, t: float):
        if self.ancla is None or self.pos is None:
            return self._enviar(*self.pos) if self.pos else None
        if self.ref_al_anclar is not None and self.pos_ref is not None:
            dx = self.pos_ref[0] - self.ref_al_anclar[0]
            dy = self.pos_ref[1] - self.ref_al_anclar[1]
        else:
            dx = self.pos[0] - self.pos_al_anclar[0]
            dy = self.pos[1] - self.pos_al_anclar[1]
        if not self.arrastrando and math.hypot(dx, dy) <= self.umbral_arrastre:
            return self._enviar(*self.ancla, umbral=0.5)
        self.arrastrando = True
        m = self.mapeo.monitor
        x = min(max(self.ancla[0] + dx, m.x), m.x + m.ancho - 1)
        y = min(max(self.ancla[1] + dy, m.y), m.y + m.alto - 1)
        return self._enviar(x, y)

    def soltar_ancla(self, t: float, congelar_s: float = 0.100):
        """Al abrir el pellizco el puntero se queda quieto 100 ms donde se soltó."""
        self.ancla = None
        self.pos_al_anclar = None
        self.ref_al_anclar = None
        self.arrastrando = False
        self.congelado_hasta = t + congelar_s

    def ir_a(self, x: float, y: float):
        """Mover a un punto exacto (sin zona muerta)."""
        return self._enviar(x, y, umbral=0.5)
