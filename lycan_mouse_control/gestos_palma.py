"""1.0.2 paquete C «Palma y comodidad»: lógica PURA que usa la máquina de estados.

- Pasar página con la palma (scroll): mostrar la palma abierta, estirada y quieta medio segundo
  (suena un aviso) y luego subir o bajar la mano: la página sigue a la mano (rueda del ratón).
  Termina con el puño, apuntando con el índice, cualquier pellizco, la seña de activar, la V o
  sacando la mano. Al soltar moviendo rápido la página sigue un poco y frena sola (inercia).
- Barrido: pasar la mano abierta rápido a la derecha o a la izquierda = siguiente / anterior
  (flechas en el perfil genérico, Alt+flechas en el navegador). En programas de diseño no hace
  nada de fábrica.

Está escrito como una «mezcla» (mixin) de ``MaquinaEstados``, igual que ``gestos_puno.py``: usa
sus campos y la máquina solo llama a estas funciones desde sus enganches. No importa ctypes, cv2
ni tkinter.
"""
from __future__ import annotations

import math
from collections import deque

from . import constantes as K
from .acciones import Aviso, Pulsar, Rueda, SoltarTodo, Sonido
from .constantes import WHEEL_DELTA
from .gestos_puno import _num
from .senas import Sena

# ---- scroll con la palma ----
SCROLL_QUIETA_S = 0.5        # la palma estirada se sostiene quieta medio segundo
SCROLL_QUIETA_V = 0.10       # anchos de la imagen por segundo: más que esto = se mueve
VENTANA_V_S = 0.15           # la velocidad se mide en los últimos 150 ms
SCROLL_PISTA_S = 0.5         # la mano lleva al menos medio segundo a la vista
# La espera de la palma quieta solo EMPIEZA con la mano abierta 3 cuadros seguidos y la separación
# de los dedos de verdad en 0,60 o más: la separación va suavizada y al pasar de apuntar (que mide
# ~0,8) a la mano abierta relajada quedaba un cuadro «estirada» y la histéresis la dejaba pegada.
ABIERTA_CUADROS = 3
SEP_ENTRAR = 0.60
SCROLL_TRAS_GESTO_S = 1.0    # ni justo después de un gesto, arrastre, giro, golpe o barrido
FIN_CUADROS = 2              # cuadros seguidos de la seña que termina el scroll
MUESCAS_MAX_S = 20.0         # tope de muescas por segundo fuera de los programas de diseño
PENDIENTES_MAX = 2.0         # como mucho 2 muescas pendientes (si la mano va más rápido que la rueda)
FRACCION_MIN = 0.25          # con rueda fraccionaria: nada por debajo de un cuarto de muesca (temblor)
# ---- inercia del scroll ----
INERCIA_MIN = 4.0            # muescas por segundo al soltar para que siga sola
INERCIA_FIN = 0.8            # por debajo, se detiene
INERCIA_MAX_S = 6.0          # nunca dura más que esto
ATRAPAR_CUADROS = 2          # cuadros de puño o de palma estirada para atraparla
# ---- barrido ----
BARRIDO_DIST = 0.20          # anchos de la imagen...
BARRIDO_TIEMPO_S = 0.25      # ... en 250 ms o menos
BARRIDO_RECTO = 2.5          # |dx| >= 2.5 |dy|
BARRIDO_ABIERTA = 0.70       # la mano abierta (o 4 dedos estirados) en el 70 % de los cuadros
BARRIDO_QUIETA_V = 0.5       # anchos/s en los 100 ms de antes: arranca desde quieta
BARRIDO_ANTES_S = 0.10
BARRIDO_PISTA_S = 0.30       # la mano lleva 300 ms a la vista (una mano que entra no dispara)
BARRIDO_TRAS_GESTO_S = 0.30  # ni justo después de soltar un arrastre, un giro o el scroll
BARRIDO_BLOQUEO_S = 0.8      # tras un barrido, otro no sale en 800 ms...
BARRIDO_CONTRARIO_S = 1.0    # ... y el de la dirección contraria en 1 s (la mano que vuelve)
HISTORIA_S = 0.6

# Señas que terminan el scroll (2 cuadros seguidos). La mano relajada o NINGUNA no lo terminan.
SENAS_FIN = (Sena.PUNO, Sena.APUNTAR, Sena.PELLIZCO, Sena.PELLIZCO_ANULAR, Sena.PELLIZCO_MENIQUE,
             Sena.PELLIZCO_CORAZON, Sena.ACTIVAR, Sena.V)


class GestosPalma:
    """Mezcla de ``MaquinaEstados`` con el scroll de la palma, su inercia y el barrido."""

    # ------------------------------------------------------------------ config
    def _leer_config_palma(self):
        cfg = self.cfg
        sc = cfg.get("scroll")
        sc = sc if isinstance(sc, dict) else {}
        self.scroll_palma = sc.get("palma", True) is not False
        self.scroll_inercia_on = sc.get("inercia", True) is not False
        self.scroll_friccion = _num(sc.get("friccion"), 2.0, 0.3, 6.0)
        self.scroll_invertir = sc.get("invertir", False) is True
        self.scroll_paso = _num(sc.get("paso"), 0.025, 0.005, 0.10)
        gestos = cfg.get("gestos")
        self.barrido_on = not isinstance(gestos, dict) or gestos.get("barrido", True) is not False

    def _reiniciar_palma(self):
        self.t_ocupado = -10.0          # última vez con un gesto, un botón abajo o un arrastre
        self.t_barrido = -10.0
        self.palma_fue_scroll = False   # lo lee el golpe (paquete B): esa palma no «arma»
        self.gpal = {"quieta_desde": None, "v_hist": deque(), "id": None, "abierta_n": 0}
        self.gbar = {"hist": deque(), "bloqueo": -10.0, "bloqueo_dir": {"der": -10.0, "izq": -10.0}}
        cuenta = getattr(self, "cuenta", None)
        if isinstance(cuenta, dict):
            cuenta.setdefault("scroll", 0)

    # ------------------------------------------------------------- utilidades
    def _anotar_ocupado(self, t):
        """Desde paso(): la palma y el barrido no arrancan justo después de un gesto o un arrastre."""
        if self.gesto is not None or self.izq or self.algo_sostenido():
            self.t_ocupado = t
            self.gpal["quieta_desde"] = None
            self.gbar["hist"].clear()

    def _signo_scroll(self) -> int:
        """Subir la mano = el contenido sube = rueda negativa (al revés con «invertir»)."""
        return 1 if self.scroll_invertir else -1

    def _lim_muescas(self) -> float:
        p = self.perfil
        if getattr(p, "diseno", False):
            return max(float(p.max_muescas_s), 0.5)
        return MUESCAS_MAX_S

    def _cy(self, p) -> float:
        return float(p.centro[1])

    def _velocidad_centro(self, hist, t) -> float:
        """Anchos de la imagen por segundo del centro de la palma en los últimos 150 ms."""
        viejo = None
        for e in hist:
            if t - e[0] <= VENTANA_V_S + 1e-9:
                viejo = e
                break
        if viejo is None or not hist:
            return 0.0
        nuevo = hist[-1]
        dt = nuevo[0] - viejo[0]
        if dt < 0.03:
            return 0.0
        return math.hypot(nuevo[1] - viejo[1], (nuevo[2] - viejo[2]) / self.aspecto) / dt

    # ----------------------------------------------------- enganche en _una_mano
    def _gestos_palma(self, t, p, s, acc) -> bool:
        """Desde _una_mano (sin gesto en curso): arranca el scroll o dispara un barrido.
        True si el gesto se quedó el cuadro (el puntero no se mueve)."""
        if not p.detectada:
            return False
        gp = self.gpal
        if gp["id"] != p.id:
            gp["id"] = p.id
            gp["quieta_desde"] = None
            gp["v_hist"].clear()
            self.gbar["hist"].clear()
        c = p.centro
        hist = gp["v_hist"]
        hist.append((t, float(c[0]), float(c[1])))
        while hist and t - hist[0][0] > HISTORIA_S:
            hist.popleft()
        gp["abierta_n"] = gp["abierta_n"] + 1 if s == Sena.ABIERTA else 0
        estirada = s == Sena.ABIERTA and bool(getattr(p.medidas, "palma_estirada", False))
        if not estirada and s not in (Sena.PUNO, Sena.NINGUNA):
            self.palma_fue_scroll = False        # la mano ya dejó la palma del scroll
        if self._quizas_scroll(t, p, s, estirada, acc):
            return True
        return self._quizas_barrido(t, p, s, acc)

    # ------------------------------------------------------------- scroll: arranque
    def _scroll_permitido(self, t, p) -> bool:
        gp = getattr(self, "gp", {}) or {}
        return (self.scroll_palma and self.base == K.ACTIVO and self.puede_presionar()
                and not self.requiere_soltar and self.ep_inicio is None and not p.sospechosa
                and t - getattr(p, "t_nacio", t) >= SCROLL_PISTA_S - 1e-9
                and t - self.t_ocupado >= SCROLL_TRAS_GESTO_S - 1e-9
                and t - self.t_barrido >= SCROLL_TRAS_GESTO_S - 1e-9
                and t >= float(gp.get("bloqueo", -10.0)) - 1e-9          # golpe (paquete B)
                and gp.get("abrir") is None
                and not getattr(self, "palma_usada", False))

    def _quizas_scroll(self, t, p, s, estirada, acc) -> bool:
        gp = self.gpal
        if not estirada or not self._scroll_permitido(t, p) \
                or self._velocidad_centro(gp["v_hist"], t) >= SCROLL_QUIETA_V:
            gp["quieta_desde"] = None
            return False
        if gp["quieta_desde"] is None:
            try:
                sep = float(getattr(p.medidas, "sep", float("nan")))
            except (TypeError, ValueError):
                sep = float("nan")
            if gp["abierta_n"] < ABIERTA_CUADROS or not sep >= SEP_ENTRAR - 1e-9:
                return False
            gp["quieta_desde"] = t
        if t - gp["quieta_desde"] < SCROLL_QUIETA_S - 1e-9:
            return False
        self._iniciar_scroll(t, p, acc)
        return True

    def _iniciar_scroll(self, t, p, acc):
        self.gpal["quieta_desde"] = None
        self.gesto = "scroll"
        self.g = {"id": p.id, "y_ref": self._cy(p), "tok": 1.0, "t_tok": t, "fin_n": 0,
                  "hist": deque([(t, self._cy(p))]), "t0": t}
        self.palma_fue_scroll = True
        self.cuenta["scroll"] = self.cuenta.get("scroll", 0) + 1
        acc.append(Aviso("scroll"))
        acc.append(Sonido("scroll"))
        self._marcar("pasando")

    # ------------------------------------------------- gesto en curso (desde paso())
    def _paso_gesto_palma(self, t, p, acc, avisos):
        if self.gesto == "scroll_inercia":
            self._paso_scroll_inercia(t, p, acc)
        else:
            self._paso_scroll(t, p, acc)

    def _emitir_muescas(self, t, m: float, acc) -> float:
        """Manda hasta ``m`` muescas (con el signo de la rueda) respetando la cubeta propia del
        scroll. Devuelve las que salieron (con signo)."""
        g = self.g
        lim = self._lim_muescas()
        g["tok"] = min(1.0, g["tok"] + max(t - g["t_tok"], 0.0) * lim)
        g["t_tok"] = t
        perfil = self.perfil
        fraccion = perfil.rueda_fraccion and not (getattr(perfil, "alejar_entero", False) and m < 0)
        enviadas = 0.0
        if fraccion:
            cant = min(abs(m), g["tok"])
            if abs(m) >= FRACCION_MIN and cant * WHEEL_DELTA >= 15:
                delta = int(math.copysign(math.floor(cant * WHEEL_DELTA), m))
                if delta:
                    self._emitir(acc, [Rueda(delta)])
                    g["tok"] -= abs(delta) / WHEEL_DELTA
                    enviadas = delta / WHEEL_DELTA
            return enviadas
        while abs(m - enviadas) >= 1.0 - 1e-9 and g["tok"] >= 1.0 - 1e-9:
            d = 1 if m > 0 else -1
            self._emitir(acc, [Rueda(WHEEL_DELTA * d)])
            g["tok"] -= 1.0
            enviadas += d
        return enviadas

    def _paso_scroll(self, t, p, acc):
        g = self.g
        if p.id != g["id"]:
            self._terminar_scroll(t, acc, inercia=False)
            return
        if not p.detectada:
            return                       # pista retenida: se salta el cuadro sin tocar nada
        s = p.sena
        if s in SENAS_FIN:
            g["fin_n"] += 1
            if g["fin_n"] >= FIN_CUADROS:
                self._terminar_scroll(t, acc, inercia=s != Sena.PUNO)
            return
        g["fin_n"] = 0
        y = self._cy(p)
        hist = g["hist"]
        hist.append((t, y))
        while len(hist) > 2 and t - hist[1][0] >= VENTANA_V_S - 1e-9:
            hist.popleft()
        signo = self._signo_scroll()
        paso = self.scroll_paso
        m = (g["y_ref"] - y) / paso * signo          # muescas de rueda que pide la mano
        env = self._emitir_muescas(t, m, acc)
        g["y_ref"] -= env * signo * paso
        resto = (g["y_ref"] - y) / paso
        if abs(resto) > PENDIENTES_MAX:
            g["y_ref"] = y + math.copysign(PENDIENTES_MAX, resto) * paso
        if env:
            self._marcar("pasando")

    def _velocidad_scroll(self) -> float:
        """Muescas por segundo (con el signo de la rueda) de los últimos ~150 ms de la mano."""
        hist = self.g.get("hist") or ()
        if len(hist) < 2:
            return 0.0
        (t0, y0), (t1, y1) = hist[0], hist[-1]
        if t1 - t0 < 0.03:
            return 0.0
        return (y0 - y1) / self.scroll_paso * self._signo_scroll() / (t1 - t0)

    def _terminar_scroll(self, t, acc, inercia: bool):
        v = self._velocidad_scroll()
        if inercia and self.scroll_inercia_on and abs(v) > INERCIA_MIN:
            v = max(-MUESCAS_MAX_S, min(MUESCAS_MAX_S, v))
            g = self.g
            self.gesto = "scroll_inercia"
            self.g = {"id": g["id"], "v": v, "t_ult": t, "t0": t, "tok": g["tok"], "t_tok": g["t_tok"],
                      "pend": 0.0, "punos": 0, "palmas": 0}
            self._marcar("pasando")
            return
        self._fin_scroll(t, acc)

    def _fin_scroll(self, t, acc, aviso: bool = True):
        if self.algo_sostenido():
            self._emitir(acc, [SoltarTodo("fin del scroll")])
        self.gesto = None
        self.g = {}
        self._pedir_rearme(dos_manos=False)
        self.puntero.reset()
        self.t_ocupado = t
        self._puno_del_scroll(t)
        self._marcar("scroll_fin")
        if aviso:
            acc.append(Aviso("scroll_fin"))

    def _puno_del_scroll(self, t):
        """El puño que termina el scroll queda «usado» para el golpe del paquete B: abrirlo de
        golpe no despieza y cerrarlo no arma."""
        gp = getattr(self, "gp", None)
        if isinstance(gp, dict):
            gp.update(sucio=True, previo_puno=True, t_puno=t, est_ult=-10.0, est_desde=None,
                      est_desde_ult=None, armar=None, abrir=None)

    # ------------------------------------------------------------- inercia
    def _paso_scroll_inercia(self, t, p, acc):
        g = self.g
        if p is not None and p.detectada:
            estirada = p.sena == Sena.ABIERTA and bool(getattr(p.medidas, "palma_estirada", False))
            g["punos"] = g["punos"] + 1 if p.sena == Sena.PUNO else 0
            g["palmas"] = g["palmas"] + 1 if estirada else 0
            if g["punos"] >= ATRAPAR_CUADROS:
                self._fin_scroll(t, acc)                 # atrapada con el puño: se detiene
                return
            if g["palmas"] >= ATRAPAR_CUADROS and p.id == g["id"]:
                # atrapada con la palma: la página vuelve a seguir a la mano
                self.gesto = "scroll"
                self.g = {"id": p.id, "y_ref": self._cy(p), "tok": g["tok"], "t_tok": g["t_tok"],
                          "fin_n": 0, "hist": deque([(t, self._cy(p))]), "t0": t}
                self._marcar("pasando")
                return
        if t - g["t0"] >= INERCIA_MAX_S - 1e-9:
            self._fin_scroll(t, acc)
            return
        dt = min(max(t - g["t_ult"], 0.0), 0.07)
        g["t_ult"] = t
        g["pend"] += g["v"] * dt
        env = self._emitir_muescas(t, g["pend"], acc)
        g["pend"] -= env
        if abs(g["pend"]) > PENDIENTES_MAX:
            g["pend"] = math.copysign(PENDIENTES_MAX, g["pend"])
        g["v"] *= math.exp(-self.scroll_friccion * dt)
        if abs(g["v"]) < INERCIA_FIN:
            self._fin_scroll(t, acc)

    def frenar_scroll(self, t: float) -> list:
        """Orden del gancho de teclado: se apretó una tecla con la página andando sola."""
        self._t = t
        acc: list = []
        if self.gesto == "scroll_inercia":
            self._fin_scroll(t, acc)
        return acc

    # ------------------------------------------------------------- barrido
    def tecla_barrido(self, direccion: str) -> tuple | None:
        """Teclas del barrido en el programa activo, o None (el barrido no se detecta)."""
        if not self.barrido_on:
            return None
        return self.atajo_gesto("barrido_" + direccion)

    def _quizas_barrido(self, t, p, s, acc) -> bool:
        gb = self.gbar
        teclas = {d: self.tecla_barrido(d) for d in ("der", "izq")}
        if not any(teclas.values()):
            gb["hist"].clear()
            return False
        ok = s == Sena.ABIERTA or p.medidas.extendidos >= 4
        c = p.centro
        hist = gb["hist"]
        hist.append((t, float(c[0]), float(c[1]) / self.aspecto, ok, s == Sena.APUNTAR))
        while hist and t - hist[0][0] > HISTORIA_S:
            hist.popleft()
        if (t < gb["bloqueo"] - 1e-9 or not self.puede_presionar() or self.requiere_soltar
                or self.ep_inicio is not None or p.sospechosa
                or t - getattr(p, "t_nacio", t) < BARRIDO_PISTA_S - 1e-9
                or t - self.t_ocupado < BARRIDO_TRAS_GESTO_S - 1e-9):
            return False
        direccion = self._buscar_barrido(hist)
        if direccion is None or teclas.get(direccion) is None:
            return False
        if t < gb["bloqueo_dir"][direccion] - 1e-9:
            return False
        self._disparar_barrido(t, direccion, teclas[direccion], acc)
        return False

    @staticmethod
    def _buscar_barrido(hist) -> str | None:
        """'der' / 'izq' si la historia termina en un barrido: ≥ 0,20 anchos en ≤ 250 ms, casi
        horizontal, con la mano abierta y arrancando desde quieta. Si no, None."""
        if len(hist) < 3:
            return None
        lista = list(hist)
        tn, xn, yn = lista[-1][0], lista[-1][1], lista[-1][2]
        for i, (ti, xi, yi, _ok, _ap) in enumerate(lista[:-1]):
            if tn - ti > BARRIDO_TIEMPO_S + 1e-9:
                continue
            dx, dy = xn - xi, yn - yi
            if abs(dx) < BARRIDO_DIST - 1e-9 or abs(dx) < BARRIDO_RECTO * abs(dy):
                continue
            tramo = lista[i:]
            if any(e[4] for e in tramo):                   # nunca apuntando con el índice
                continue
            if sum(1 for e in tramo if e[3]) < BARRIDO_ABIERTA * len(tramo) - 1e-9:
                continue
            antes = [e for e in lista[:i + 1] if e[0] <= ti - BARRIDO_ANTES_S + 1e-9]
            if not antes:
                continue                                   # sin historia: la mano recién entra
            j = antes[-1]
            if ti - j[0] <= 1e-6:
                continue
            v = math.hypot(xi - j[1], yi - j[2]) / (ti - j[0])
            if v >= BARRIDO_QUIETA_V:
                continue
            return "der" if dx > 0 else "izq"
        return None

    def _disparar_barrido(self, t, direccion: str, teclas: tuple, acc):
        gb = self.gbar
        gb["bloqueo"] = t + BARRIDO_BLOQUEO_S
        contraria = "izq" if direccion == "der" else "der"
        gb["bloqueo_dir"][contraria] = max(gb["bloqueo_dir"][contraria], t + BARRIDO_CONTRARIO_S)
        gb["hist"].clear()
        self.t_barrido = t
        self.gpal["quieta_desde"] = None
        self._emitir(acc, [Pulsar(tuple(teclas))])
        acc.append(Sonido("clic"))
        acc.append(Aviso("barrido_" + direccion))
        self._marcar("barrido_" + direccion)

