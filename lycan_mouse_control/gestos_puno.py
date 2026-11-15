"""1.0.2 paquete B «Girar con un puño»: lógica PURA que usa la máquina de estados.

- Girar con un puño (modo 3D): cerrar el puño y moverlo = girar con la combinación de orbitar del
  programa (botón del medio en EDWIN CNC 3D y SketchUp). Puño quieto sigue siendo clic derecho.
- Lanzar con inercia (apagado de fábrica): soltar el puño moviéndolo rápido deja la pieza girando
  y frena sola. Cerrar el puño la atrapa; sacar la mano, apretar una tecla o pausar la frena.
- Abrir la mano de golpe = despiezar; cerrarla de golpe = armar. Mandan el atajo que el usuario
  ponga para cada programa (ningún programa trae uno de fábrica).

Está escrito como una «mezcla» (mixin) de ``MaquinaEstados``: usa sus campos (puntero, traductor,
mapeo, tm...) y la máquina solo llama a estas funciones desde sus enganches. No importa ctypes,
cv2 ni tkinter.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from . import constantes as K
from .acciones import Aviso, Mover, MoverDelta, Pulsar, SoltarTodo, Sonido
from .filtros import OneEuro
from .perfiles import gesto_de
from .senas import Sena
from .teclas import interpretar_envio, nombre_envio

# ---- girar con un puño ----
PUNO_QUIETO = 0.02          # anchos: hasta aquí el puño está quieto (clic derecho)
PUNO_GIRA = 0.03            # anchos: más de esto antes del clic derecho = girar
PUNO_MOVIDO_CUADROS = 2     # revisión 1.0.2: ...en 2 cuadros seguidos (un cuadro de temblor no gira)
GIROS = ("un_puno", "dos_punos", "ambos")
# revisión 1.0.2: estas señas (sostenidas 100 ms) también sueltan el giro con un puño
SENAS_SUELTAN_GIRO = (Sena.APUNTAR, Sena.PELLIZCO, Sena.PELLIZCO_ANULAR, Sena.PELLIZCO_MENIQUE,
                      Sena.PELLIZCO_CORAZON, Sena.ACTIVAR, Sena.V)
OTRA_SENA_SUELTA_S = 0.10
# ---- lanzar ----
VENTANA_VELOCIDAD_S = 0.15  # la velocidad al soltar se mide en los últimos 150 ms
LANZAR_MIN = 0.4            # anchos del monitor por segundo para que siga girando
LANZAR_MAX = 8.0            # tope: anchos del monitor por segundo
INERCIA_MIN_PX_S = 30.0     # por debajo, la pieza se detiene
INERCIA_MAX_S = 4.0         # la inercia nunca dura más que esto
ATRAPAR_CUADROS = 2         # cuadros de puño para atrapar la pieza
# ---- golpe ----
GOLPE_HUECO_S = 0.15        # entre el último puño y la palma estirada (o al revés)
# ...o 3,5 cuadros si la cámara va lenta (el plan decía 2,5; la separación de los dedos va suavizada y
# la palma estirada se ve un cuadro más tarde: a 15 cuadros/s 2,5 cuadros no alcanzaban)
GOLPE_HUECO_CUADROS = 3.5
GOLPE_HUECO_MAX_S = 0.20    # revisión 1.0.2: tope (a 10 cuadros/s 3,5 cuadros eran 350 ms)
GOLPE_MOVIDO = 0.05         # anchos: la mano casi no se mueve en un golpe
ABRIR_SOSTENER_S = 0.15     # la palma se sostiene 150 ms después de abrir
CERRAR_PALMA_MIN_S = 0.20   # la palma estirada se ve al menos 200 ms antes de cerrar
CERRAR_QUIETO_S = 0.12      # el puño de «armar» queda quieto 120 ms
GOLPE_BLOQUEO_S = 1.0       # tras un golpe, otro no sale en 1 s
PUNO_NUEVO_S = 0.3          # sin puño este tiempo (o con palma estirada) = puño nuevo


class GestosPuno:
    """Mezcla de ``MaquinaEstados`` con el giro de un puño, la inercia y el golpe."""

    # ------------------------------------------------------------------ config
    def _leer_config_puno(self):
        cfg = self.cfg
        orb = cfg.get("orbita") or {}
        girar = orb.get("girar", "un_puno")
        self.girar = girar if girar in GIROS else "un_puno"
        self.k_un_puno = _num(orb.get("k_un_puno"), 1.2, 0.1, 5.0)
        self.inercia_on = orb.get("inercia", False) is True
        self.friccion = _num(orb.get("friccion"), 1.5, 0.3, 6.0)
        gestos = cfg.get("gestos")
        self.golpe_on = not isinstance(gestos, dict) or gestos.get("golpe", True) is not False
        self.s_puno_3d = _num(self.tm.get("puno_3d"), 300, 150, 1000) / 1000.0

    def _reiniciar_puno(self):
        self.puno_giro_ok = False      # el puño actual puede girar (mismas reglas que el clic derecho)
        self.gp = {"id": None, "t_puno": -10.0, "c_puno": None, "sucio": False, "previo_puno": False,
                   "est_desde": None, "est_desde_ult": None, "est_ult": -10.0, "c_est": None,
                   "abrir": None, "armar": None, "bloqueo": -10.0}
        # el paquete C lo lee: la palma de un golpe no puede arrancar el scroll hasta que se deje
        self.palma_usada = False

    @property
    def girar_un_puno(self) -> bool:
        return self.girar in ("un_puno", "ambos")

    @property
    def girar_dos_punos(self) -> bool:
        return self.girar in ("dos_punos", "ambos")

    def espera_puno_s(self, otra_visible: bool) -> float:
        """Espera del clic derecho: 3D = max(puño, puño 3D) (300 ms); 2D con otra mano a la vista
        = 250 ms; si no, la del puño (200 ms)."""
        base = float(self.tm["puno"]) / 1000.0
        if self.modo == "3D":
            return max(base, self.s_puno_3d)
        if otra_visible:
            return max(base, 0.25)
        return base

    # ------------------------------------------------------------- utilidades
    def _anchos(self, a, b) -> float:
        """Distancia entre dos puntos de la imagen, en anchos de la imagen (aspecto corregido)."""
        d = (np.asarray(a, float) - np.asarray(b, float)) * np.array([1.0, 1.0 / self.aspecto])
        return float(np.hypot(d[0], d[1]))

    def _hueco_golpe(self) -> float:
        # revisión 1.0.2: con la cámara lenta los cuadros dan algo de margen, pero nunca más de
        # 200 ms (a 15 cuadros/s 3,5 cuadros eran 233 ms y abrir despacio contaba como golpe)
        return min(max(GOLPE_HUECO_S, GOLPE_HUECO_CUADROS * getattr(self, "_dt_cuadro", 0.0)),
                   GOLPE_HUECO_MAX_S)

    def atajo_gesto(self, nombre: str) -> tuple | None:
        """Teclas que manda el gesto en el programa activo, o None (el gesto no se detecta)."""
        return interpretar_envio(gesto_de(self.perfil, nombre, self.cfg))

    def _cerca_del_borde(self, c) -> bool:
        m = self.mapeo.monitor
        return (c[0] - m.x < 5 or m.x + m.ancho - 1 - c[0] < 5 or c[1] - m.y < 5
                or m.y + m.alto - 1 - c[1] < 5)

    # ------------------------------------------------- girar con un puño: arranque
    def _quizas_girar_un_puno(self, t, p, otra, movido: float, acc) -> bool:
        """Desde el bloque del puño: si el puño se movió más de 0,03 anchos antes del clic
        derecho, empieza a girar. Entre 0,02 y 0,03 no pasa nada."""
        if self.modo != "3D" or not self.girar_un_puno or movido <= PUNO_GIRA:
            return False
        if getattr(self, "puno_gira_n", PUNO_MOVIDO_CUADROS) < PUNO_MOVIDO_CUADROS:
            return False               # un solo cuadro corrido (temblor): todavía no
        if not (self.puno_giro_ok and not self.puno_disparado and not self.puno_cerrojo
                and p.detectada and p.sena == Sena.PUNO and not self.requiere_soltar
                and self.puede_presionar() and self.par_cand is None):
            return False
        if self.girar == "ambos" and otra is not None and otra.sena == Sena.PUNO:
            return False               # con «los dos», dos puños = girar con dos manos
        self._iniciar_orbita1(t, p, acc)
        return True

    def _iniciar_orbita1(self, t, p, acc):
        self.puno_valido = False        # ya no hay clic derecho
        self.puno_disparado = True
        self.gp["sucio"] = True
        self.gp["armar"] = None
        pos = None
        if self.puno_inicio is not None:
            pos = self.puntero.posicion_en(self.puno_inicio - self.puntero.rebobinado_s)
        if pos is None:
            pos = self._cursor_real()
        if pos is None:
            m = self.mapeo.monitor
            pos = (m.x + m.ancho // 2, m.y + m.alto // 2)
        x0, y0, x1, y1 = self.mapeo.monitor.zona_segura()
        x = min(max(float(pos[0]), x0), x1)
        y = min(max(float(pos[1]), y0), y1)
        self._emitir(acc, [self.puntero.ir_a(x, y)])
        if self.cursor is None:
            self.cursor = (int(round(x)), int(round(y)))
        self.puno_inicio = None
        self.gesto = "orbita1"
        self.g = {"id": p.id, "estado": "preparando", "t0": t, "agarre": (int(round(x)), int(round(y))),
                  "salida": None, "comb": self.perfil.combinacion_orbitar(self.modo),
                  "hist": deque(), "t_girando": t}
        self._rebasar_orbita1(t, p.centro)
        self._marcar("girar")

    def _rebasar_orbita1(self, t, M):
        g = self.g
        M = np.asarray(M, float)
        g["fM"] = (OneEuro(1.0, 0.02), OneEuro(1.0, 0.02))
        g["M_raw"] = M.copy()
        g["M_unw"] = M.copy()
        g["M_ref"] = np.array([g["fM"][0].filtrar(float(M[0]), t), g["fM"][1].filtrar(float(M[1]), t)])
        g["resto"] = (0.0, 0.0)

    # --------------------------------------------- gesto en curso (desde paso())
    def _paso_gesto_puno(self, t, p, acc, avisos):
        """Un cuadro del giro con un puño o de la inercia. ``p`` es la mano principal."""
        if self.gesto == "inercia":
            self._paso_inercia(t, p, acc, avisos)
        else:
            self._paso_orbita1(t, p, acc, avisos)

    def _paso_orbita1(self, t, p, acc, avisos):
        g = self.g
        if p.id != g["id"]:
            self._terminar_orbita1(t, acc, "cambió la mano")
            return
        if not p.detectada:
            return                      # pista retenida: se salta el cuadro sin tocar nada
        if self._abierta(p):
            # El cuadro de abrir no cuenta para la velocidad ni mueve nada (la palma salta).
            if g["salida"] is None:
                g["salida"] = t
                if g["estado"] == "girando" and self.inercia_on and self._quizas_lanzar(t, acc, avisos):
                    return
            if t - g["salida"] >= self.s_pellizco_out - 1e-9:
                self._terminar_orbita1(t, acc, "mano abierta")
            return
        g["salida"] = None
        if p.sena in SENAS_SUELTAN_GIRO:
            # revisión 1.0.2: pasar del puño a apuntar, a un pellizco o a la V (sin abrir la mano)
            # también suelta el giro, sin lanzar: si no, el modelo seguía girando al apuntar
            if g.get("otra_desde") is None:
                g["otra_desde"] = t
            if t - g["otra_desde"] >= max(self.s_pellizco_out, OTRA_SENA_SUELTA_S) - 1e-9:
                self._terminar_orbita1(t, acc, "otra seña")
            return
        g["otra_desde"] = None
        M = np.asarray(p.centro, float)
        est = g["estado"]
        if est in ("preparando", "reagarre"):
            g["M_raw"] = M.copy()
            if est == "preparando" and t - g["t0"] < 0.02:
                return                  # se espera un cuadro
            if est == "reagarre" and t < g["reagarre_hasta"]:
                return
            if not self._medio_permitido(t, self._cursor_real()):
                return
            self._emitir(acc, self.traductor.empezar(g["comb"]))
            g["estado"] = "girando"
            g["t_girando"] = t
            g["hist"].clear()
            self._rebasar_orbita1(t, M)
            return
        # girando
        dM_raw = self._anchos(M, g["M_raw"])
        if p.sospechosa or dM_raw > 0.15:
            g["M_raw"] = M.copy()       # salto imposible: queda como base sin mover nada
            return
        g["M_unw"] = g["M_unw"] + (M - g["M_raw"])
        g["M_raw"] = M.copy()
        Mu = g["M_unw"]
        Mf = np.array([g["fM"][0].filtrar(float(Mu[0]), t), g["fM"][1].filtrar(float(Mu[1]), t)])
        dM = Mf - g["M_ref"]
        if float(np.hypot(*dM)) >= 0.003:
            g["M_ref"] = Mf
        else:
            dM = np.zeros(2)
        W, H = self.mapeo.monitor.ancho, self.mapeo.monitor.alto
        G = self.ganancia * self.perfil.ganancia_orbita * self.k_un_puno
        dx = G * float(dM[0]) * W
        dy = G * float(dM[1]) * H
        n = math.hypot(dx, dy)
        if n > self.max_px:
            dx, dy = dx * self.max_px / n, dy * self.max_px / n
        rx, ry = g["resto"]
        dx += rx
        dy += ry
        ix, iy = int(round(dx)), int(round(dy))
        g["resto"] = (dx - ix, dy - iy)
        # para lanzar: la posición REAL de la mano (sin el filtro, que se atrasa) en los últimos 150 ms
        hist = g["hist"]
        hist.append((t, float(Mu[0]), float(Mu[1])))
        while len(hist) > 2 and t - hist[1][0] >= VENTANA_VELOCIDAD_S - 1e-9:
            hist.popleft()
        if ix or iy:
            self._emitir(acc, [MoverDelta(ix, iy)])
            self._marcar("girar")
        self._reagarre_un_puno(t, acc)

    def _reagarre_un_puno(self, t, acc):
        """Igual que con dos puños: cerca del borde se suelta, se vuelve al punto de agarre y
        a los 600 ms se vuelve a agarrar."""
        g = self.g
        c = self._cursor_real()
        if c is None:
            return
        ag = g["agarre"]
        if math.hypot(c[0] - ag[0], c[1] - ag[1]) >= 20 and self._cerca_del_borde(c):
            self._emitir(acc, self.traductor.terminar(g["comb"]))
            self._emitir(acc, [Mover(*ag)])
            self.puntero.ult_enviado = ag
            g["estado"] = "reagarre"
            g["reagarre_hasta"] = t + 0.6
            g["hist"].clear()

    def _velocidad_al_soltar(self, t) -> tuple[float, float]:
        """Píxeles por segundo con que giraba la pieza en los últimos ~150 ms (sin el cuadro de
        abrir, que no entra en la historia). Se mide con la mano, no con el puntero filtrado."""
        hist = self.g["hist"]
        if len(hist) < 2:
            return 0.0, 0.0
        (t0, x0, y0), (t1, x1, y1) = hist[0], hist[-1]
        dt = t1 - t0
        if dt <= 1e-3:
            return 0.0, 0.0
        W, H = self.mapeo.monitor.ancho, self.mapeo.monitor.alto
        G = self.ganancia * self.perfil.ganancia_orbita * self.k_un_puno
        return G * (x1 - x0) * W / dt, G * (y1 - y0) * H / dt

    def _quizas_lanzar(self, t, acc, avisos) -> bool:
        g = self.g
        W = float(self.mapeo.monitor.ancho)
        vx, vy = self._velocidad_al_soltar(t)
        v = math.hypot(vx, vy)
        if v < LANZAR_MIN * W:
            return False
        tope = LANZAR_MAX * W
        if v > tope:
            vx, vy = vx * tope / v, vy * tope / v
        self.gesto = "inercia"
        self.g = {"comb": g["comb"], "agarre": g["agarre"], "v": (vx, vy), "t_ult": t, "t0": t,
                  "resto": g.get("resto", (0.0, 0.0)), "punos": 0, "estado": "girando"}
        aviso = Aviso("inercia")
        acc.append(aviso)
        avisos.append(aviso)
        self._marcar("lanzar")
        return True

    # ------------------------------------------------------------- inercia
    def _paso_inercia(self, t, p, acc, avisos):
        g = self.g
        # atrapar: 2 cuadros de puño (vistos de verdad)
        if p is not None and p.detectada and p.sena == Sena.PUNO:
            g["punos"] += 1
            if g["punos"] >= ATRAPAR_CUADROS:
                self._atrapar(t, p)
                return
        elif p is not None and p.detectada:
            g["punos"] = 0
        if t - g["t0"] >= INERCIA_MAX_S - 1e-9:
            self._terminar_inercia(t, acc)
            return
        if g["estado"] == "reagarre":
            # en el borde: se soltó, el puntero volvió al punto de agarre y se espera para no
            # hacer doble clic del medio; luego sigue girando con lo que le quedaba
            g["t_ult"] = t
            if t < g["reagarre_hasta"] or not self._medio_permitido(t, self._cursor_real()):
                return
            self._emitir(acc, self.traductor.empezar(g["comb"]))
            g["estado"] = "girando"
            return
        dt = min(max(t - g["t_ult"], 0.0), 0.07)
        g["t_ult"] = t
        vx, vy = g["v"]
        rx, ry = g["resto"]
        dx, dy = vx * dt + rx, vy * dt + ry
        ix, iy = int(round(dx)), int(round(dy))
        g["resto"] = (dx - ix, dy - iy)
        if ix or iy:
            self._emitir(acc, [MoverDelta(ix, iy)])
        f = math.exp(-self.friccion * dt)
        g["v"] = (vx * f, vy * f)
        if math.hypot(*g["v"]) < INERCIA_MIN_PX_S:
            self._terminar_inercia(t, acc)
            return
        c = self._cursor_real()
        ag = g["agarre"]
        if c is not None and math.hypot(c[0] - ag[0], c[1] - ag[1]) >= 20 and self._cerca_del_borde(c):
            self._emitir(acc, self.traductor.terminar(g["comb"]))
            self._emitir(acc, [Mover(*ag)])
            self.puntero.ult_enviado = ag
            g["estado"] = "reagarre"
            g["reagarre_hasta"] = t + 0.6

    def _atrapar(self, t, p):
        """La pieza queda agarrada otra vez (sin soltar ni volver a bajar el botón)."""
        g = self.g
        self.gesto = "orbita1"
        # si estaba en el reagarre del borde (botón arriba), el giro sigue esperando para agarrar
        estado = "reagarre" if g.get("estado") == "reagarre" else "girando"
        self.g = {"id": p.id, "estado": estado, "t0": t, "agarre": g["agarre"], "salida": None,
                  "comb": g["comb"], "hist": deque(), "t_girando": t,
                  "reagarre_hasta": g.get("reagarre_hasta", t)}
        self._rebasar_orbita1(t, p.centro)
        self._marcar("girar")

    def _terminar_inercia(self, t, acc, aviso: str | None = None, avisos=None):
        g = self.g
        if g.get("estado") == "girando":
            self._emitir(acc, self.traductor.terminar(g["comb"]))
        if self.algo_sostenido():
            self._emitir(acc, [SoltarTodo("fin de la inercia")])
        self.gesto = None
        self.g = {}
        self.traductor.vaciar()
        self._pedir_rearme(dos_manos=False)
        self.puntero.reset()
        self._marcar("soltar")
        self.scroll_tras_giro = True     # la palma que soltó el giro no pasa página (ver paquete C)
        if aviso:
            a = Aviso(aviso)
            acc.append(a)
            if avisos is not None:
                avisos.append(a)

    def frenar(self, t: float) -> list:
        """Orden del gancho de teclado: se apretó una tecla con la pieza girando sola."""
        self._t = t
        acc: list = []
        if self.gesto == "inercia":
            self._terminar_inercia(t, acc, "frenado")
        return acc

    def _terminar_orbita1(self, t, acc, motivo):
        g = self.g
        if g.get("estado") == "girando":
            self._emitir(acc, self.traductor.terminar(g["comb"]))
        if self.algo_sostenido():
            self._emitir(acc, [SoltarTodo("fin de gesto")])
        self.gesto = None
        self.g = {}
        self.traductor.vaciar()
        self._pedir_rearme(dos_manos=(motivo != "mano abierta"))
        self.puntero.reset()
        self._marcar("soltar")
        # revisión 1.0.2: soltar el giro con la palma estirada y mirar el modelo no debe arrancar el
        # scroll (en 3D es zoom): la mano tiene que hacer otra seña primero (apuntar, puño...)
        self.scroll_tras_giro = True

    # ----------------------------------------------------------------- golpe
    def _armar_pendiente(self) -> bool:
        return self.gp.get("armar") is not None

    def _gestos_puno(self, t, p, s, acc) -> bool:
        """Abrir la mano de golpe (despiezar) y cerrarla de golpe (armar). Solo se detecta si
        «Abrir / cerrar la mano de golpe» está prendido y el programa tiene atajo. Nunca se
        queda el cuadro (devuelve False): el puntero y el puño siguen como siempre."""
        gp = self.gp
        if gp["id"] != p.id:
            self._reiniciar_puno()
            self.gp["id"] = p.id
            gp = self.gp
        abrir = self.atajo_gesto("abrir_golpe") if self.golpe_on else None
        cerrar = self.atajo_gesto("cerrar_golpe") if self.golpe_on else None
        if not p.detectada:
            return False                # pista retenida: no cuenta para nada
        centro = np.asarray(p.centro, float)
        hueco = self._hueco_golpe()
        ocupado = not self.puede_presionar()
        es_puno = s == Sena.PUNO
        estirada = bool(getattr(p.medidas, "palma_estirada", False))
        if es_puno:
            self._fin_estirada()
            if not gp["previo_puno"]:
                # puño nuevo: «limpio» si hubo palma estirada o un rato sin puño
                if t - gp["t_puno"] > PUNO_NUEVO_S or gp["est_ult"] > gp["t_puno"]:
                    gp["sucio"] = False
                # ¿cerrar de golpe? (palma estirada ≥ 200 ms y puño en ≤ 150 ms, casi sin moverse)
                if (cerrar is not None and gp["est_desde_ult"] is not None and gp["c_est"] is not None
                        and t - gp["est_ult"] <= hueco + 1e-9
                        and gp["est_ult"] - gp["est_desde_ult"] >= CERRAR_PALMA_MIN_S - 1e-9
                        and self._anchos(centro, gp["c_est"]) <= GOLPE_MOVIDO
                        and not getattr(self, "palma_fue_scroll", False)):
                    gp["armar"] = {"t0": t, "c0": centro.copy()}
            elif self.puno_disparado:
                gp["sucio"] = True       # este puño ya dio clic derecho, giró o armó
            if ocupado or self.izq:
                gp["sucio"] = True
            gp["previo_puno"] = True
            gp["t_puno"] = t
            gp["c_puno"] = centro.copy()
            gp["abrir"] = None
            arm = gp["armar"]
            if arm is not None:
                if self._anchos(centro, arm["c0"]) > PUNO_GIRA:
                    gp["armar"] = None                   # se movió: gana girar (o nada en 2D)
                elif t - arm["t0"] >= self._cerrar_quieto_s() - 1e-9:
                    gp["armar"] = None
                    if self._golpe_permitido(t) and cerrar is not None:
                        self._disparar_golpe(t, acc, "cerrar", cerrar)
                        # el puño de «armar» no da clic derecho ni gira hasta abrir la mano
                        self.puno_valido = False
                        self.puno_disparado = True
                        self.puno_cerrojo = True
                        gp["sucio"] = True
            return False
        gp["previo_puno"] = False
        gp["armar"] = None
        if ocupado or self.puno_disparado:
            gp["sucio"] = True
        if estirada:
            if gp["est_desde"] is None:
                gp["est_desde"] = t
                gp["c_est"] = centro.copy()
                # ¿abrir de golpe? (último puño → palma estirada en ≤ 150 ms, casi sin moverse)
                if (abrir is not None and not gp["sucio"] and gp["c_puno"] is not None
                        and t - gp["t_puno"] <= hueco + 1e-9
                        and self._anchos(centro, gp["c_puno"]) <= GOLPE_MOVIDO):
                    gp["abrir"] = {"t0": t}
            gp["est_ult"] = t
            gp["c_est"] = centro.copy()
            ab = gp["abrir"]
            if ab is not None and t - ab["t0"] >= ABRIR_SOSTENER_S - 1e-9:
                gp["abrir"] = None
                if self._golpe_permitido(t) and abrir is not None and not gp["sucio"]:
                    self._disparar_golpe(t, acc, "abrir", abrir)
                    self.palma_usada = True
                gp["sucio"] = True                       # este puño ya no despieza otra vez
        else:
            gp["abrir"] = None
            self._fin_estirada()
        return False

    def _cerrar_quieto_s(self) -> float:
        """Cuánto queda quieto el puño de «armar». Revisión 1.0.2: en 3D con el giro de un puño es
        lo mismo que el clic derecho (300 ms): cerrar la mano para girar no debe «armar» antes de
        alcanzar a moverla."""
        if self.modo == "3D" and self.girar_un_puno:
            return max(CERRAR_QUIETO_S, self.espera_puno_s(False))
        return CERRAR_QUIETO_S

    def _fin_estirada(self):
        gp = self.gp
        if gp["est_desde"] is not None:
            gp["est_desde_ult"] = gp["est_desde"]      # cuándo empezó la última palma estirada
        gp["est_desde"] = None
        self.palma_usada = False

    def _golpe_permitido(self, t) -> bool:
        return (self.base == K.ACTIVO and t >= self.gp["bloqueo"] - 1e-9 and self.puede_presionar()
                and not self.requiere_soltar and self.ep_inicio is None)

    def _disparar_golpe(self, t, acc, cual: str, teclas: tuple):
        self.gp["bloqueo"] = t + GOLPE_BLOQUEO_S
        self._emitir(acc, [Pulsar(tuple(teclas))])
        acc.append(Sonido("clic"))
        acc.append(Aviso("golpe_" + cual, nombre_envio(teclas)))
        self._marcar("despiezar" if cual == "abrir" else "armar")


def _num(v, fab: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float(fab)
    if not math.isfinite(x) or not (lo <= x <= hi):
        return float(fab)
    return x
