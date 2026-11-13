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


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class Puntero:
    def __init__(self, mapeo: Mapeo, cfg: dict | None = None):
        cfg = cfg or {}
        self.mapeo = mapeo
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
        self._aplicar_filtro()
        self.hist: deque = deque()
        self.ult_enviado: tuple[int, int] | None = None
        self.pos: tuple[float, float] | None = None      # última posición filtrada
        self.ancla: tuple[float, float] | None = None
        self.pos_al_anclar: tuple[float, float] | None = None
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
        for f in (self.fx, self.fy):
            f.mincutoff, f.beta, f.dcutoff = mc, b, self.dcutoff

    def poner_dibujo_fino(self, si: bool):
        self.dibujo_fino = bool(si)
        self._aplicar_filtro()

    def configurar(self, cfg: dict):
        self.__init__(self.mapeo, cfg)  # noqa: PLC2801 (reconstrucción simple)

    def reset(self):
        """Al activar, al reaparecer la mano, al salir de un gesto de dos manos o cambiar de monitor."""
        self.fx.reset()
        self.fy.reset()
        self.hist.clear()
        self.pos = None
        self.ancla = None
        self.pos_al_anclar = None
        self.arrastrando = False
        self.t_fuera_desde = None
        self._rel_prev = None

    # ---- observar la mano ----
    def observar(self, t: float, u: float, v: float, embrague: bool = False):
        """Filtra la punta del índice (u, v en 0..1 de la imagen). Devuelve (x, y) en píxeles."""
        if not (math.isfinite(u) and math.isfinite(v)):
            return self.pos
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
        return self.pos

    def _relativo(self, t, u, v, embrague):
        m = self.mapeo.monitor
        if self._rel_pos is None:
            base = self.ult_enviado or (m.x + m.ancho / 2.0, m.y + m.alto / 2.0)
            self._rel_pos = (float(base[0]), float(base[1]))
        if self._rel_prev is not None and not embrague:
            t0, u0, v0 = self._rel_prev
            dt = max(t - t0, 1e-3)
            du, dv = u - u0, v - v0
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
        self.ancla = self._punto_quieto(t_ref) or self.posicion_en(t_ref - self.rebobinado_s) or self.pos
        self.pos_al_anclar = self.pos
        self.arrastrando = False
        return self._enviar(*self.ancla, umbral=0.5)

    def mover_anclado(self, t: float):
        if self.ancla is None or self.pos is None:
            return self._enviar(*self.pos) if self.pos else None
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
        self.arrastrando = False
        self.congelado_hasta = t + congelar_s

    def ir_a(self, x: float, y: float):
        """Mover a un punto exacto (sin zona muerta)."""
        return self._enviar(x, y, umbral=0.5)
