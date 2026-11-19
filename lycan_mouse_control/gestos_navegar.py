"""1.0.3 «Señas para navegar»: lógica PURA que usa la máquina de estados.

- Clic izquierdo EMPUJANDO: apuntando con el índice, se empuja la mano hacia la cámara. Apenas la
  mano empieza a acercarse (se ve más grande), el puntero se queda QUIETO en el punto donde estaba
  un instante antes; cuando la mano se acercó lo suficiente, hace clic ahí. Al retirar la mano el
  puntero se suelta. Dos empujones seguidos caen en el mismo punto (doble clic de Windows).
- Scroll ABANICANDO: con la mano abierta, un golpe rápido arriba / abajo / izquierda / derecha
  mueve la página para ese lado. Solo cuenta el golpe que TERMINA con la mano abierta: la vuelta
  (con los dedos doblados, como al remar) no cuenta. Así se ve en los videos del usuario
  (pruebas/datos_reales/abanico_*.npz).

Funciona en todos los programas. En los programas de diseño el abanico se apaga (allá quedan
girar con un puño, el zoom y abrir/cerrar de golpe); el clic empujando sí funciona.

Es una «mezcla» (mixin) de ``MaquinaEstados``, igual que ``gestos_palma.py``. No importa ctypes,
cv2 ni tkinter.
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from . import constantes as K
from .acciones import Clic, Rueda, Sonido
from .constantes import WHEEL_DELTA
from .gestos_puno import _num
from .senas import Sena

# ---- abanico ----
AB_V_MIN = 0.8          # altos de imagen por segundo: más que esto = la mano va en un golpe
AB_V_GOLPE = 1.0        # el golpe tiene que llegar al menos a esta velocidad
AB_V_MAX = 5.0          # más rápido que esto es un salto de MediaPipe, no una mano
AB_VENTANA_S = 0.066    # la velocidad se mide contra el cuadro de hace ~2 cuadros
AB_DIST_MIN = 0.12      # recorrido mínimo del golpe (altos de imagen)
AB_DUR_MAX_S = 0.9      # un golpe más largo es mover la mano, no abanicar
AB_HUECO = 2            # cuadros lentos seguidos que terminan el golpe
AB_ABIERTA = 4          # dedos extendidos (contando el pulgar) al final del golpe
AB_PISTA_S = 0.3        # la mano lleva un rato a la vista (una mano que entra no cuenta)
AB_DIST_REF = 0.30      # un golpe de este recorrido manda «paso» muescas
AB_QUIETO_S = 0.6       # tras un golpe que contó, el puntero se queda quieto este tiempo
AB_RECTO = 1.5          # el recorrido en la dirección del golpe es al menos 1,5 veces el de lado
AB_SIN_CLIC_S = 0.4     # con la mano (no apuntando) moviéndose rápido, los pellizcos no hacen clic
EM_QUIETA_S = 0.25      # tras un movimiento rápido de la mano, el empujón espera esto
# ---- empujar ----
EM_APUNTA_S = 0.20      # apuntando quieto al menos esto antes de empujar
EM_VENTANA_S = 0.10     # el crecimiento se mide contra el tamaño de hace 100 ms
EM_INICIO = 0.045       # crecer 4,5 % en 100 ms = empezó a empujar (el puntero se queda quieto)
EM_V_LADO = 0.6         # altos/s: si la mano va de lado más rápido, es moverse, no empujar
EM_TIEMPO_MAX_S = 0.8   # si en este tiempo no llega, no hay clic
EM_ADENTRO_MAX_S = 2.0  # después del clic, el puntero se suelta solo a más tardar en 2 s
EM_DOBLE_S = 0.6        # otro empujón antes de esto cae en el mismo punto (doble clic)
EM_DOBLE_PX = 40.0
EM_TRAS_ABANICO_S = 0.6  # tras abanicar, el empujón no cuenta (la mano cambia de tamaño al abanicar)
EM_OTRA_CUADROS = 2     # cuadros seguidos con otra seña clara que cancelan el empujón
OPUESTA = {"arriba": "abajo", "abajo": "arriba", "izq": "der", "der": "izq"}
HUESOS_PALMA = ((0, 5), (0, 17), (5, 17), (0, 9), (5, 9), (9, 13), (13, 17))


def tamano_aparente(img, mundo, aspecto: float) -> float:
    """Qué tan grande se ve la palma (crece al acercarla a la cámara).

    Se divide el largo de los huesos de la palma en la imagen por su largo «de frente» en metros
    (MediaPipe da los puntos en metros girados como la cámara). Así, girar o inclinar la mano casi
    no cambia el valor; acercarla a la cámara sí. Devuelve nan si no se puede medir."""
    if mundo is None:
        return float("nan")
    try:
        img = np.asarray(img, float)
        mundo = np.asarray(mundo, float)
        num = 0.0
        den = 0.0
        for a, b in HUESOS_PALMA:
            dx = (img[a, 0] - img[b, 0]) * aspecto
            dy = img[a, 1] - img[b, 1]
            num += math.hypot(dx, dy)
            den += math.hypot(mundo[a, 0] - mundo[b, 0], mundo[a, 1] - mundo[b, 1])
        if not (math.isfinite(num) and math.isfinite(den)) or den < 1e-4:
            return float("nan")
        return num / den
    except (IndexError, TypeError, ValueError):
        return float("nan")


class GestosNavegar:
    """Mezcla de ``MaquinaEstados`` con el clic empujando y el scroll abanicando."""

    # ------------------------------------------------------------------ config
    def _leer_config_navegar(self):
        nv = self.cfg.get("navegar")
        nv = nv if isinstance(nv, dict) else {}
        self.abanico_on = nv.get("abanico", True) is not False
        self.empujar_on = nv.get("empujar", True) is not False
        self.abanico_paso = _num(nv.get("abanico_paso"), 3.0, 1.0, 10.0)
        self.empujar_fuerza = _num(nv.get("empujar_fuerza"), 0.15, 0.05, 0.50)
        self.abanico_invertir = nv.get("invertir", False) is True

    def _reiniciar_navegar(self):
        self.gab = {"hist": deque(), "golpe": None, "id": None, "t_ult": -10.0, "t_mov": -10.0,
                    "t_abierta_mov": -10.0, "pos": None}
        self.gem = {"hist": deque(), "fase": None, "apunta_desde": None, "id": None,
                    "base": None, "t0": None, "pos": None, "t_clic": -10.0, "pos_clic": None,
                    "otra_n": 0}
        cuenta = getattr(self, "cuenta", None)
        if isinstance(cuenta, dict):
            cuenta.setdefault("empujar", 0)
            cuenta.setdefault("abanico", 0)

    # ------------------------------------------------------------- utilidades
    def _navegar_permitido(self, t, p) -> bool:
        return (self.base == K.ACTIVO and self.gesto is None and not self.izq
                and not self.algo_sostenido() and not self.requiere_soltar
                and self.ep_inicio is None and not p.sospechosa)

    def abanico_activo(self) -> bool:
        return self.abanico_on and not getattr(self.perfil, "diseno", False)

    def mano_abanicando(self, t) -> bool:
        """La mano (no apuntando) se mueve rápido o acaba de abanicar: un pellizco que aparezca
        ahora es la mano doblándose a mitad del abanico, no un clic."""
        if not self.abanico_activo():
            return False
        ga = self.gab
        return t - ga["t_abierta_mov"] < AB_SIN_CLIC_S or t - ga["t_ult"] < AB_SIN_CLIC_S

    def empujando(self) -> bool:
        return self.gem["fase"] is not None

    def _cancelar_empujar(self, t, congelar_s: float = 0.10):
        if self.gem["fase"] is not None:
            self.gem["fase"] = None
            self.puntero.congelado_hasta = max(self.puntero.congelado_hasta, t + congelar_s)

    # ----------------------------------------------------- enganche en _una_mano
    def _gestos_navegar(self, t, p, s, acc) -> tuple[bool, float]:
        """Desde _una_mano. Devuelve (el puntero no se mueve este cuadro, progreso)."""
        quieto = False
        progreso = 0.0
        # el abanico siempre sigue el movimiento de la mano (lo usa también el empujón para no
        # confundir una mano que se mueve rápido con un empujón); solo manda rueda si está activo
        quieto = self._abanico(t, p, s, acc) and self.abanico_activo()
        if self.empujar_on:
            q2, progreso = self._empujar(t, p, s, acc)
            quieto = quieto or q2
        else:
            self.gem["fase"] = None
        return quieto, progreso

    # ------------------------------------------------------------------ abanico
    def _abanico(self, t, p, s, acc) -> bool:
        ga = self.gab
        if ga["id"] != p.id:
            ga["id"] = p.id
            ga["hist"].clear()
            ga["golpe"] = None
        if not p.detectada:
            # La mano se salió de la imagen en pleno golpe (al bajar, la mano suele salirse por
            # abajo): el golpe se evalúa con lo que se alcanzó a ver. Soltar el brazo para
            # descansar sale en diagonal y no cuenta (tiene que ser recto).
            if ga["golpe"] is not None:
                self._fin_golpe(t, p, ga["golpe"], acc, perdida=True)
            ga["golpe"] = None
            return self._quieto_abanico(t)
        c = p.centro
        x, y = float(c[0]) * self.aspecto, float(c[1])
        ext = int(getattr(p.medidas, "extendidos", 0) or 0)
        hist = ga["hist"]
        hist.append((t, x, y))
        while hist and t - hist[0][0] > 0.5:
            hist.popleft()
        ref = None
        for e in reversed(hist):
            if t - e[0] >= AB_VENTANA_S - 1e-3:
                ref = e
                break
        g = ga["golpe"]
        if ref is None:
            return self._quieto_abanico(t)
        dt = t - ref[0]
        vx, vy = (x - ref[1]) / dt, (y - ref[2]) / dt
        vel = math.hypot(vx, vy)
        # la mano (no apuntando) se movió rápido en 3 de los cuadros de los últimos 200 ms: está
        # abanicando (el salto de un cuadro al cambiar de seña no cuenta)
        mov = ga.setdefault("mov", deque())
        mov.append((t, vel >= AB_V_MIN and ext >= 3))
        while mov and t - mov[0][0] > 0.2:
            mov.popleft()
        if sum(1 for _, m in mov if m) >= 3:
            ga["t_abierta_mov"] = t
        if vel >= AB_V_MIN:
            ga["t_mov"] = t
            if abs(vx) > abs(vy):
                d = "der" if vx > 0 else "izq"
            else:
                d = "abajo" if vy > 0 else "arriba"
            if g is not None and OPUESTA[g["d"]] == d:
                # el golpe termina al volver la mano (dirección contraria)
                self._fin_golpe(t, p, g, acc)
                g = None
            # Si la mano dobla de lado sin frenar, el golpe sigue: al final se mide qué tan recto
            # fue en total (soltar el brazo para descansar sale en curva y no cuenta).
            if g is None:
                g = {"d": d, "t0": ref[0], "x0": ref[1], "y0": ref[2], "vmax": 0.0, "ext": [], "hueco": 0}
                ga["golpe"] = g
            g["x1"], g["y1"], g["t1"] = x, y, t
            g["vmax"] = max(g["vmax"], vel)
            g["ext"].append(ext)
            g["hueco"] = 0
        elif g is not None:
            g["hueco"] += 1
            if g["hueco"] >= AB_HUECO:
                self._fin_golpe(t, p, g, acc)
                ga["golpe"] = None
        return self._quieto_abanico(t)

    def _quieto_abanico(self, t) -> bool:
        """El puntero no sigue a la mano mientras abanica: durante un golpe con la mano abierta y
        un rato después de un golpe que contó."""
        ga = self.gab
        g = ga["golpe"]
        return (t - ga["t_ult"] < AB_QUIETO_S
                or (g is not None and len(g["ext"]) >= 1 and max(g["ext"]) >= AB_ABIERTA))

    def _fin_golpe(self, t, p, g, acc, perdida: bool = False):
        ga = self.gab
        ga["golpe"] = None
        if not self.abanico_activo():
            return
        eje_x = g["d"] in ("der", "izq")
        dx, dy = abs(g["x1"] - g["x0"]), abs(g["y1"] - g["y0"])
        dist, lado = (dx, dy) if eje_x else (dy, dx)
        ext = g["ext"]
        abierta = len(ext) >= 2 and ext[-1] >= AB_ABIERTA and ext[-2] >= AB_ABIERTA
        if not (abierta and dist >= AB_DIST_MIN and dist >= AB_RECTO * lado
                and AB_V_GOLPE <= g["vmax"] <= AB_V_MAX and g["t1"] - g["t0"] <= AB_DUR_MAX_S):
            return
        if not self._navegar_permitido(t, p) or t - getattr(p, "t_nacio", t) < AB_PISTA_S - 1e-9:
            return
        # antes del primer golpe de una tanda, se guarda dónde estaba el puntero para volver ahí
        if t - ga["t_ult"] >= AB_QUIETO_S:
            ga["pos"] = self.puntero.posicion_en(g["t0"] - 0.10)
        n = max(1, min(int(round(self.abanico_paso * dist / AB_DIST_REF)), int(3 * self.abanico_paso)))
        signo = -1 if self.abanico_invertir else 1
        if g["d"] == "arriba":
            r = Rueda(WHEEL_DELTA * n * signo)
        elif g["d"] == "abajo":
            r = Rueda(-WHEEL_DELTA * n * signo)
        elif g["d"] == "der":
            r = Rueda(WHEEL_DELTA * n * signo, horizontal=True)
        else:
            r = Rueda(-WHEEL_DELTA * n * signo, horizontal=True)
        pos = ga.get("pos")
        if pos is not None:
            self._emitir(acc, [self.puntero.ir_a(*pos)])
        self._emitir(acc, [r])
        ga["t_ult"] = t
        self.puntero.congelado_hasta = max(self.puntero.congelado_hasta, t + AB_QUIETO_S)
        self._cancelar_empujar(t)
        self.cuenta["abanico"] = self.cuenta.get("abanico", 0) + 1
        self._marcar("abanico_" + g["d"])

    # ------------------------------------------------------------------ empujar
    def _empujar(self, t, p, s, acc) -> tuple[bool, float]:
        ge = self.gem
        if ge["id"] != p.id:
            ge["id"] = p.id
            ge["hist"].clear()
            ge["apunta_desde"] = None
            self._cancelar_empujar(t)
        if not p.detectada:
            ge["t_det"] = None
            if ge["fase"] == "empujando":
                self._cancelar_empujar(t)
            elif ge["fase"] == "adentro":
                self._cancelar_empujar(t, 0.15)
            return False, 0.0
        if ge.get("t_det") is None:
            ge["t_det"] = t                  # la mano se ve sin cortes desde aquí
        tam = tamano_aparente(p.img, getattr(p, "mundo", None), self.aspecto)
        c = p.centro
        x, y = float(c[0]) * self.aspecto, float(c[1])
        hist = ge["hist"]
        if math.isfinite(tam):
            hist.append((t, tam, x, y))
        while hist and t - hist[0][0] > 0.6:
            hist.popleft()
        if s == Sena.APUNTAR:
            if ge["apunta_desde"] is None:
                ge["apunta_desde"] = t
        elif s != Sena.NINGUNA:
            ge["apunta_desde"] = None
        fase = ge["fase"]
        if fase is None:
            return False, self._quizas_empujar(t, p, s, tam, acc)
        # otra seña clara (puño, pellizco, mano abierta...) cancela el empujón
        if s not in (Sena.APUNTAR, Sena.NINGUNA):
            ge["otra_n"] += 1
        else:
            ge["otra_n"] = 0
        base = ge["base"]
        if fase == "empujando":
            if ge["otra_n"] >= EM_OTRA_CUADROS or not self._navegar_permitido(t, p):
                self._cancelar_empujar(t)
                return False, 0.0
            if math.isfinite(tam) and tam >= base * (1.0 + self.empujar_fuerza):
                self._emitir(acc, [self.puntero.ir_a(*ge["pos"]), Clic(K.IZQ)])
                acc.append(Sonido("clic"))
                ge["fase"] = "adentro"
                ge["t_clic"] = t
                ge["pos_clic"] = ge["pos"]
                self.cuenta["empujar"] = self.cuenta.get("empujar", 0) + 1
                self._marcar("clic_izquierdo")
                return True, 1.0
            if t - ge["t0"] > EM_TIEMPO_MAX_S or (math.isfinite(tam) and tam < base * 1.01):
                self._cancelar_empujar(t)    # se arrepintió o se quedó a mitad: no hay clic
                return False, 0.0
            avance = (tam / base - 1.0) / self.empujar_fuerza if math.isfinite(tam) else 0.0
            self._emitir(acc, [self.puntero.ir_a(*ge["pos"])])
            return True, min(max(avance, 0.0), 1.0)
        # fase "adentro": el puntero sigue quieto hasta retirar la mano
        if (ge["otra_n"] >= EM_OTRA_CUADROS or t - ge["t_clic"] > EM_ADENTRO_MAX_S
                or (math.isfinite(tam) and tam < base * (1.0 + self.empujar_fuerza * 0.5))):
            ge["apunta_desde"] = t if s == Sena.APUNTAR else None
            self._cancelar_empujar(t, 0.15)
            return False, 0.0
        return True, 0.0

    def _quizas_empujar(self, t, p, s, tam, acc) -> float:
        ge = self.gem
        if (s != Sena.APUNTAR or ge["apunta_desde"] is None or t - ge["apunta_desde"] < EM_APUNTA_S - 1e-9
                or not math.isfinite(tam) or not self._navegar_permitido(t, p)
                or t - self.gab["t_ult"] < EM_TRAS_ABANICO_S
                or t - self.gab["t_mov"] < EM_QUIETA_S
                or t - getattr(p, "t_nacio", t) < AB_PISTA_S
                or ge.get("t_det") is None or t - ge["t_det"] < EM_APUNTA_S
                or self.puno_inicio is not None or self.pel_desde is not None):
            return 0.0
        ref = None
        for e in reversed(ge["hist"]):
            if t - e[0] >= EM_VENTANA_S - 1e-3:
                ref = e
                break
        if ref is None or ref[1] <= 0:
            return 0.0
        dt = t - ref[0]
        crece = tam / ref[1] - 1.0
        lado = math.hypot(ge["hist"][-1][2] - ref[2], ge["hist"][-1][3] - ref[3]) / max(dt, 1e-3)
        if crece < EM_INICIO or lado > EM_V_LADO:
            return 0.0
        # empezó a empujar: el puntero vuelve a donde estaba antes de que la mano arrancara
        t0 = ref[0]
        pos = self.puntero.posicion_en(t0 - self.puntero.rebobinado_s)
        if pos is None:
            return 0.0
        if (ge["pos_clic"] is not None and t - ge["t_clic"] <= EM_DOBLE_S
                and math.hypot(pos[0] - ge["pos_clic"][0], pos[1] - ge["pos_clic"][1]) <= EM_DOBLE_PX):
            pos = ge["pos_clic"]            # segundo empujón: mismo punto (doble clic)
        ge["fase"] = "empujando"
        ge["t0"] = t0
        ge["base"] = ref[1]
        ge["pos"] = (float(pos[0]), float(pos[1]))
        ge["otra_n"] = 0
        self._emitir(acc, [self.puntero.ir_a(*ge["pos"])])
        self._marcar("empujando")
        return min(max(crece / self.empujar_fuerza, 0.0), 1.0)
