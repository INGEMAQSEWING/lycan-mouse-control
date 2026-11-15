"""Clasificador puro de una mano: puntos en metros (21x3) -> una sola Seña por cuadro.

Orden de prioridad (gana la primera que se cumpla):
PUNO, PELLIZCO_ANULAR (si el clic con el anular está prendido), PELLIZCO_MENIQUE (si el meñique
hace algo), ACTIVAR, V, PELLIZCO_CORAZON (solo si la variante está activa), PELLIZCO,
ABIERTA, APUNTAR, NINGUNA.

Si dos dedos están cerca del pulgar a la vez (ninguno gana claro: regla del 0.6), esos cuadros dan
NINGUNA: es mejor no hacer nada que hacer el gesto equivocado.

Cada mano seguida tiene su propio ``Clasificador`` (lleva la histéresis de cada medida).
"""
from __future__ import annotations

import copy
import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from . import geometria as g
from .filtros import Histeresis, PromedioExp


class Sena(str, Enum):
    PUNO = "PUNO"
    ACTIVAR = "ACTIVAR"
    V = "V"
    PELLIZCO_CORAZON = "PELLIZCO_CORAZON"
    PELLIZCO = "PELLIZCO"
    PELLIZCO_ANULAR = "PELLIZCO_ANULAR"      # 1.0.2: pulgar + anular (clic izquierdo)
    PELLIZCO_MENIQUE = "PELLIZCO_MENIQUE"    # 1.0.2: pulgar + meñique (acción elegida)
    ABIERTA = "ABIERTA"
    APUNTAR = "APUNTAR"
    NINGUNA = "NINGUNA"


EXT, DOB, DUD = "EXT", "DOB", "DUD"

PUNO_EN_CURSO_SALIR = 72.0   # ° para salir de "puño en curso" (se entra con 80°)
CUADROS_TRAS_CURSO = 5       # ~150 ms a 30 cuadros/s después de salir del puño en curso...
PELLIZCO_TRAS_CURSO = 0.20   # ... el pellizco tiene que estar claramente cerrado
# 1.0.2 paquete A: pellizcos con el anular y el meñique
GANA_CLARO = 0.6             # el dedo del pellizco tiene que estar a menos de 0.6 veces el siguiente
# 2.ª revisión 1.0.2: histéresis de esa regla. Un pellizco con el anular o el meñique que ya ganó
# hace poco (menos de GANA_MEMORIA cuadros, ~150 ms) sigue con un límite más suave: si no, el ruido
# del pulgar cerca del dedo vecino lo hace parpadear con NINGUNA (corta el arrastre o repite el
# doble clic).
GANA_SEGUIR = 0.8
GANA_MEMORIA = 5
LEJOS_DEDO_MIN = 0.65        # la punta del anular/meñique lejos de la palma (doblado ~0.31)
# Revisión 1.0.2: camino al meñique el pulgar pasa por encima del anular. Si el meñique se busca y
# el pulgar se le está acercando (pm baja más que esto en 2 cuadros, en los dos, y casi tanto como
# pa), el anular no gana: va de paso.
PM_BAJANDO = 0.03
PM_PASO = 0.008              # lo mínimo que se mueve pm en CADA uno de esos 2 cuadros
ANULAR_FIRME = 2             # cuadros seguidos de PELLIZCO_ANULAR: desde ahí ya no se duda
PM_RAZON = 0.85              # yendo derecho al anular, pm baja ~0,7 de lo que baja pa
# palma estirada (la usan los paquetes B y C): ABIERTA, 5 dedos y puntas separadas
PALMA_ESTIRADA_ENTRAR = 0.60
PALMA_ESTIRADA_SALIR = 0.54

# ---- Umbrales de fábrica (sección 3.7 / 5.1 de la especificación) ----
UMBRALES_FABRICA = {
    "pellizco": {"entrar": 0.28, "salir": 0.42},
    "pellizco_corazon": {"entrar": 0.28, "salir": 0.42, "activo": False},
    "juntos": {"s_entrar": 1.25, "s_salir": 1.50, "a_entrar": 10.0, "a_salir": 15.0},
    "v": {"s_entrar": 1.9, "s_salir": 1.6, "a_min": 20.0},
    "doblez": {"extendido": [60.0, 85.0], "doblado": [110.0, 90.0]},
    "razon": {"extendido": 1.20, "doblado": 0.95},
    "puno": {"punta_palma": 0.55, "pulgar_palma": 0.75, "puntas_min": 3},
    # puno_en_curso: si los 4 dedos largos están DOBLADOS y todos pasan de este doblez (°), la
    # mano está cerrándose o abriéndose del puño; eso no es un pellizco (el pellizco real mide
    # ~70° en el índice).
    "pellizco_extra": {"doblez_indice_max": 140.0, "indice_palma_min": 0.55, "p_min_corazon": 0.5,
                       "puno_en_curso": 80.0},
    "pulgar": {"angulo_max": 35.0, "dist_min": 0.55},
    "abierta": {"sep_min": 0.35},
    # 1.0.2 paquete A
    "pellizco_anular": {"entrar": 0.28, "salir": 0.42, "activo": True},
    "pellizco_menique": {"entrar": 0.26, "salir": 0.40, "activo": True},
}

# Medidas que la calibración puede mover (como máximo ±40 % de fábrica).
_CALIBRABLES = (
    ("pellizco", "entrar"), ("pellizco", "salir"),
    ("pellizco_corazon", "entrar"), ("pellizco_corazon", "salir"),
    ("juntos", "s_entrar"), ("juntos", "s_salir"), ("juntos", "a_entrar"), ("juntos", "a_salir"),
    ("v", "s_entrar"), ("v", "s_salir"),
    ("pellizco_anular", "entrar"), ("pellizco_anular", "salir"),
    ("pellizco_menique", "entrar"), ("pellizco_menique", "salir"),
)
LIMITE_CALIBRACION = 0.40


def recortar_calibrado(valor: float, fabrica: float, limite: float = LIMITE_CALIBRACION) -> float:
    """Un umbral calibrado no puede alejarse más de ±40 % del de fábrica."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return fabrica
    if not math.isfinite(v):
        return fabrica
    lo, hi = fabrica * (1 - limite), fabrica * (1 + limite)
    if lo > hi:
        lo, hi = hi, lo
    return min(max(v, lo), hi)


def construir_umbrales(cfg_senas: dict | None = None, una_mano_zoom: bool | None = None) -> dict:
    """Une los umbrales de fábrica con los de la configuración (recortando los calibrados)."""
    u = copy.deepcopy(UMBRALES_FABRICA)
    cfg = cfg_senas or {}
    for grupo in ("pellizco", "pellizco_corazon", "juntos", "v", "pellizco_anular", "pellizco_menique"):
        for k, v in (cfg.get(grupo) or {}).items():
            if k in u[grupo]:
                if (grupo, k) in _CALIBRABLES:
                    u[grupo][k] = recortar_calibrado(v, UMBRALES_FABRICA[grupo][k])
                elif isinstance(v, bool):
                    u[grupo][k] = v
    db = cfg.get("doblez") or {}
    for k in ("extendido", "doblado"):
        val = db.get(k)
        if isinstance(val, (list, tuple)) and len(val) == 2:
            fab = UMBRALES_FABRICA["doblez"][k]
            u["doblez"][k] = [recortar_calibrado(val[0], fab[0]), recortar_calibrado(val[1], fab[1])]
    # coherencia: entrar debe quedar "por dentro" de salir
    if u["pellizco"]["entrar"] >= u["pellizco"]["salir"]:
        u["pellizco"] = dict(UMBRALES_FABRICA["pellizco"])
    pc = u["pellizco_corazon"]
    if pc["entrar"] >= pc["salir"]:
        pc["entrar"], pc["salir"] = 0.28, 0.42
    j = u["juntos"]
    if j["s_entrar"] >= j["s_salir"] or j["a_entrar"] >= j["a_salir"]:
        u["juntos"] = dict(UMBRALES_FABRICA["juntos"])
    if u["v"]["s_entrar"] <= u["v"]["s_salir"]:
        u["v"] = dict(UMBRALES_FABRICA["v"])
    if u["v"]["s_salir"] <= u["juntos"]["s_salir"]:
        u["v"]["s_salir"] = u["juntos"]["s_salir"] + 0.05
        u["v"]["s_entrar"] = max(u["v"]["s_entrar"], u["v"]["s_salir"] + 0.1)
    for grupo in ("pellizco_anular", "pellizco_menique"):
        if u[grupo]["entrar"] >= u[grupo]["salir"]:
            u[grupo] = dict(UMBRALES_FABRICA[grupo])
    # Una seña cuya acción está apagada ("nada") ni se busca: no le quita cuadros a otra.
    if "clic_anular" in cfg:
        u["pellizco_anular"]["activo"] = cfg.get("clic_anular") is not False
    if "menique" in cfg:
        u["pellizco_menique"]["activo"] = cfg.get("menique") != "nada"
    if una_mano_zoom is not None:
        u["pellizco_corazon"]["activo"] = bool(una_mano_zoom)
    return u


@dataclass
class Medidas:
    palma: float = float("nan")
    p: float = float("nan")
    pc: float = float("nan")
    s: float = float("nan")
    a: float = float("nan")
    doblez: dict = field(default_factory=dict)
    dedos: dict = field(default_factory=dict)      # nombre -> EXT/DOB/DUD
    pulgar_ext: bool = False
    extendidos: int = 0                            # dedos largos + pulgar extendidos
    palma_a_camara: bool | None = None
    # 1.0.2 paquete A
    pa: float = float("nan")                       # pulgar - anular (punta o falange) / palma
    pm: float = float("nan")                       # pulgar - meñique (punta o falange) / palma
    lejos_anular: float = float("nan")             # punta del anular - centro de la palma / palma
    lejos_menique: float = float("nan")
    sep: float = float("nan")                      # separación media de las puntas / palma
    palma_estirada: bool = False                   # ABIERTA, 5 dedos y puntas bien separadas
    pm_bajando: bool = False                       # el pulgar va hacia el meñique (revisión 1.0.2)
    en_pa: bool = False                            # el pulgar sigue dentro del pellizco con el anular
    pm_subiendo: bool = False                      # el pulgar se aleja del meñique (revisión 1.0.2)

    def como_dict(self) -> dict:
        return {"palma": self.palma, "p": self.p, "pc": self.pc, "s": self.s, "a": self.a,
                "doblez": dict(self.doblez), "dedos": dict(self.dedos),
                "pulgar_ext": self.pulgar_ext, "extendidos": self.extendidos,
                "pa": self.pa, "pm": self.pm, "lejos_anular": self.lejos_anular,
                "lejos_menique": self.lejos_menique, "sep": self.sep,
                "palma_estirada": self.palma_estirada}


class Clasificador:
    """Clasificador de UNA mano con memoria (histéresis y suavizado de medidas)."""

    def __init__(self, umbrales: dict | None = None, suavizar: float = 0.7, suavizar_puntos: float = 0.5):
        self.u = umbrales or construir_umbrales()
        self._alfa = suavizar
        self._alfa_puntos = suavizar_puntos
        self.reiniciar()

    def reiniciar(self):
        u = self.u
        self._suav = {k: PromedioExp(self._alfa) for k in
                      ("p", "pc", "s", "a", "indice", "corazon", "anular", "menique",
                       "pulgar_ang", "pulgar_dist", "sep_puntas", "pa", "pm")}
        self._dedos = {k: DUD for k in ("indice", "corazon", "anular", "menique")}
        self._h_pellizco = Histeresis(u["pellizco"]["entrar"], u["pellizco"]["salir"], True)
        self._h_pc = Histeresis(u["pellizco_corazon"]["entrar"], u["pellizco_corazon"]["salir"], True)
        self._h_js = Histeresis(u["juntos"]["s_entrar"], u["juntos"]["s_salir"], True)
        self._h_ja = Histeresis(u["juntos"]["a_entrar"], u["juntos"]["a_salir"], True)
        self._h_vs = Histeresis(u["v"]["s_entrar"], u["v"]["s_salir"], False)
        self._h_pa = Histeresis(u["pellizco_anular"]["entrar"], u["pellizco_anular"]["salir"], True)
        self._h_pm = Histeresis(u["pellizco_menique"]["entrar"], u["pellizco_menique"]["salir"], True)
        self._estirada = False
        self._pm_prev = deque(maxlen=2)  # (pm, pa) de los 2 cuadros anteriores
        self._n_anular = 0               # cuadros seguidos con PELLIZCO_ANULAR
        self._ult_dedo = (None, 10 ** 6)  # (último PELLIZCO_ANULAR/MENIQUE, cuadros desde entonces)
        self._puntos = None
        self._en_curso = False           # puño cerrándose/abriéndose (con histéresis)
        self._tras_curso = 10 ** 6       # cuadros desde la última vez que lo estuvo
        self.sena = Sena.NINGUNA
        self.medidas = Medidas()

    def actualizar_umbrales(self, umbrales: dict):
        self.u = umbrales
        self.reiniciar()

    # ---- estado de un dedo con histéresis ----
    def _estado_dedo(self, nombre: str, doblez: float, razon: float) -> str:
        ext_in, ext_out = self.u["doblez"]["extendido"]
        dob_in, dob_out = self.u["doblez"]["doblado"]
        prev = self._dedos[nombre]
        if not math.isfinite(doblez):
            return prev
        if doblez < ext_in:
            nuevo = EXT
        elif doblez > dob_in:
            nuevo = DOB
        elif prev == EXT and doblez <= ext_out:
            nuevo = EXT
        elif prev == DOB and doblez >= dob_out:
            nuevo = DOB
        elif math.isfinite(razon) and razon > self.u["razon"]["extendido"] and doblez <= ext_out:
            nuevo = EXT
        elif math.isfinite(razon) and razon < self.u["razon"]["doblado"] and doblez >= dob_out:
            nuevo = DOB
        else:
            nuevo = DUD
        self._dedos[nombre] = nuevo
        return nuevo

    def _puno_en_curso(self, m: Medidas) -> bool:
        """Los 4 dedos largos doblados por igual: es un puño cerrándose o abriéndose.

        Con histéresis: se entra cuando todos pasan de 80° y se sale solo cuando alguno baja de
        ~72° (o se estira). Sin ella, un puño flojo (~87°) con un poco de temblor cruzaba el
        límite cuadro a cuadro y dejaba pasar pellizcos sueltos: clics izquierdos fantasma."""
        ex = self.u["pellizco_extra"]
        lim = ex.get("puno_en_curso", 80.0)
        lim_salir = ex.get("puno_en_curso_salir", PUNO_EN_CURSO_SALIR)
        if any(v == EXT for v in m.dedos.values()) or not all(math.isfinite(d) for d in m.doblez.values()):
            self._en_curso = False
        elif self._en_curso:
            self._en_curso = all(d > lim_salir for d in m.doblez.values())
        else:
            self._en_curso = all(d > lim for d in m.doblez.values())
        if self._en_curso:
            self._tras_curso = 0
        else:
            self._tras_curso += 1
        return self._en_curso

    def clasificar(self, w, etiqueta: str | None = None) -> Sena:
        """Devuelve la seña de este cuadro. Nunca lanza excepción por datos raros."""
        try:
            sena = self._clasificar(w, etiqueta)
        except (ValueError, FloatingPointError, TypeError, IndexError):
            self.sena = Sena.NINGUNA
            self.medidas = Medidas()
            sena = self.sena
        if sena in (Sena.PELLIZCO_ANULAR, Sena.PELLIZCO_MENIQUE):
            self._ult_dedo = (sena, 0)
        else:
            self._ult_dedo = (self._ult_dedo[0], self._ult_dedo[1] + 1)
        return sena

    def _clasificar(self, w, etiqueta):
        if not g.puntos_validos(w):
            self.sena = Sena.NINGUNA
            self.medidas = Medidas()
            return self.sena
        w = np.asarray(w, float)
        # Suavizado de los puntos (en metros) antes de medir: baja el temblor de los ángulos
        # de los dedos cortos sin sesgo. Si la mano "salta" (otra mano), se reinicia.
        if self._puntos is None or float(np.abs(w - self._puntos).max()) > 0.04:
            self._puntos = w.copy()
        else:
            self._puntos = self._alfa_puntos * w + (1.0 - self._alfa_puntos) * self._puntos
        w = self._puntos
        u = self.u
        m = Medidas()
        palma = g.escala_palma(w)
        c = g.centro_palma(w)
        m.palma = palma
        m.p = self._suav["p"].actualizar(g.pellizco(w, palma))
        m.pc = self._suav["pc"].actualizar(g.pellizco_corazon(w, palma))
        m.s = self._suav["s"].actualizar(g.separacion_ic(w))
        m.a = self._suav["a"].actualizar(g.angulo_ic(w))
        for nombre in ("indice", "corazon", "anular", "menique"):
            d = self._suav[nombre].actualizar(g.doblez(w, nombre))
            m.doblez[nombre] = d
            m.dedos[nombre] = self._estado_dedo(nombre, d, g.razon_dedo(w, nombre))
        pul_ang = self._suav["pulgar_ang"].actualizar(g.angulo_pulgar(w))
        pul_dist = self._suav["pulgar_dist"].actualizar(g.dist(w[4], w[5]) / palma)
        sep_puntas = self._suav["sep_puntas"].actualizar(g.separacion_media_puntas(w, palma))
        m.sep = sep_puntas
        m.pa = self._suav["pa"].actualizar(g.pellizco_dedo(w, 16, 15, palma))
        m.pm = self._suav["pm"].actualizar(g.pellizco_dedo(w, 20, 19, palma))
        if len(self._pm_prev) == 2:
            (pm0, pa0), (pm1, _pa1) = self._pm_prev
            d1, d2 = pm0 - pm1, pm1 - m.pm           # lo que bajó pm en cada uno de los 2 últimos cuadros
            dm, da = pm0 - m.pm, pa0 - m.pa
            if all(math.isfinite(x) for x in (d1, d2, da)):
                # Un movimiento de verdad va en la misma dirección los dos cuadros (el temblor no).
                # Yendo al meñique: pm baja y no es solo el pulgar que se acerca al anular (en ese
                # caso pa baja bastante más que pm: el anular está entre el pulgar y el meñique).
                m.pm_bajando = bool(min(d1, d2) > PM_PASO and dm > PM_BAJANDO and dm > PM_RAZON * da)
                # volviendo del meñique: pm sube mientras el pulgar se acerca al anular
                m.pm_subiendo = bool(max(d1, d2) < -PM_PASO and -dm > PM_BAJANDO and da > PM_PASO)
        self._pm_prev.append((m.pm, m.pa))
        m.lejos_anular = g.dist(w[16], c) / palma
        m.lejos_menique = g.dist(w[20], c) / palma
        m.pulgar_ext = pul_ang < u["pulgar"]["angulo_max"] and pul_dist > u["pulgar"]["dist_min"]
        m.extendidos = sum(1 for v in m.dedos.values() if v == EXT) + (1 if m.pulgar_ext else 0)
        n = g.normal_palma(w)
        if etiqueta in ("Left", "Right") and np.all(np.isfinite(n)):
            # Solo informativo (depuración): con la imagen en espejo la palma de la mano
            # derecha mirando a la cámara tiene la normal hacia +z.
            m.palma_a_camara = bool((n[2] > 0) if etiqueta == "Right" else (n[2] < 0))

        # Histéresis de las medidas continuas
        en_pellizco = self._h_pellizco.actualizar(m.p)
        en_pc = self._h_pc.actualizar(m.pc)
        juntos_s = self._h_js.actualizar(m.s)
        juntos_a = self._h_ja.actualizar(m.a)
        v_s = self._h_vs.actualizar(m.s)
        en_pa = self._h_pa.actualizar(m.pa)
        en_pm = self._h_pm.actualizar(m.pm)

        dd = m.dedos
        en_curso = self._puno_en_curso(m)
        recien_curso = self._tras_curso <= CUADROS_TRAS_CURSO
        if en_curso:
            # (igual que el pellizco del índice: al cerrar o abrir el puño no valen)
            self._h_pa.dentro = self._h_pm.dentro = False
            en_pa = en_pm = False
        elif recien_curso:
            if not m.pa < PELLIZCO_TRAS_CURSO:
                self._h_pa.dentro = False
                en_pa = False
            if not m.pm < PELLIZCO_TRAS_CURSO:
                self._h_pm.dentro = False
                en_pm = False
        if en_curso:
            # Un pellizco "ganado" mientras la mano pasa por el puño no vale: al abrir el puño
            # despacio la distancia pulgar-índice sigue dentro de la histéresis y daría un clic
            # izquierdo fantasma. Hay que volver a cerrar el pellizco de verdad.
            self._h_pellizco.dentro = False
            en_pellizco = False
        elif recien_curso and not (m.p < PELLIZCO_TRAS_CURSO):
            # recién salida del puño (~150 ms): solo vale un pellizco claramente cerrado
            self._h_pellizco.dentro = False
            en_pellizco = False
        m.en_pa = bool(en_pa)
        sena = Sena.NINGUNA
        # 1. Puño
        lim = u["puno"]["punta_palma"]
        puntas_cerca = sum(1 for p_ in (8, 12, 16, 20) if g.dist(w[p_], c) / palma < lim)
        if (all(dd[k] == DOB for k in dd)
                and puntas_cerca >= u["puno"]["puntas_min"]
                and g.dist(w[4], c) / palma < u["puno"]["pulgar_palma"]):
            sena = Sena.PUNO
        else:
            ic_ext = dd["indice"] == EXT and dd["corazon"] == EXT
            am_dob = dd["anular"] == DOB and dd["menique"] == DOB
            dedo = self._pellizco_dedo(m, dd, en_pa, en_pm)
            if dedo is not None:
                sena = dedo
            elif self._dos_cerca(m, dd, en_pa, en_pm):
                sena = Sena.NINGUNA          # dos dedos cerca del pulgar: nadie gana claro
            elif ic_ext and am_dob and juntos_s and juntos_a:
                sena = Sena.ACTIVAR
            elif ic_ext and am_dob and v_s and math.isfinite(m.a) and m.a > u["v"]["a_min"]:
                sena = Sena.V
            elif (u["pellizco_corazon"].get("activo") and en_pc
                  and m.p > u["pellizco_extra"]["p_min_corazon"]
                  and self._gana(m.pc, m.p, *self._otros_activos(m, "pc"))):
                sena = Sena.PELLIZCO_CORAZON
            elif (en_pellizco and m.doblez["indice"] < u["pellizco_extra"]["doblez_indice_max"]
                  and g.dist(w[8], c) / palma > u["pellizco_extra"]["indice_palma_min"]):
                sena = Sena.PELLIZCO
            elif (all(v == EXT for v in dd.values()) and m.pulgar_ext
                  and sep_puntas > u["abierta"]["sep_min"]):
                sena = Sena.ABIERTA
            elif dd["indice"] == EXT and dd["corazon"] != EXT:
                sena = Sena.APUNTAR
        # palma estirada (con histéresis): la leen los gestos de la palma y del golpe
        if sena == Sena.ABIERTA and m.extendidos >= 5 and math.isfinite(sep_puntas):
            if sep_puntas >= PALMA_ESTIRADA_ENTRAR:
                self._estirada = True
            elif sep_puntas < PALMA_ESTIRADA_SALIR:
                self._estirada = False
        else:
            self._estirada = False
        m.palma_estirada = self._estirada
        self._n_anular = self._n_anular + 1 if sena == Sena.PELLIZCO_ANULAR else 0
        self.sena = sena
        self.medidas = m
        return sena

    # ---- 1.0.2 paquete A: pellizcos con el anular y el meñique ----
    @staticmethod
    def _gana(valor: float, *otros: float, limite: float = GANA_CLARO) -> bool:
        """El dedo del pellizco gana claro: está a menos de ``limite`` (0.6) veces del que le sigue."""
        if not math.isfinite(valor):
            return False
        resto = [o for o in otros if math.isfinite(o)]
        return not resto or valor < limite * min(resto)

    def _limite_gana(self, sena: Sena) -> float:
        """0.6 para entrar; 0.8 para seguir si ese mismo dedo ganó hace menos de ~150 ms."""
        ult, n = self._ult_dedo
        return GANA_SEGUIR if (ult == sena and n < GANA_MEMORIA) else GANA_CLARO

    def _otros_activos(self, m: Medidas, propio: str) -> list:
        """Distancias de los OTROS dedos que pueden pellizcar (solo los que se buscan)."""
        u = self.u
        out = []
        if propio != "pa" and u["pellizco_anular"].get("activo"):
            out.append(m.pa)
        if propio != "pm" and u["pellizco_menique"].get("activo"):
            out.append(m.pm)
        return out

    def _candidato_dedo(self, m: Medidas, dd: dict, en_pa: bool, en_pm: bool) -> list:
        """Dedos (anular, meñique) en pellizco con el índice estirado y la punta lejos de la palma."""
        u = self.u
        out = []
        if dd["indice"] != EXT:
            return out
        if u["pellizco_anular"].get("activo") and en_pa and m.lejos_anular > LEJOS_DEDO_MIN:
            out.append("pa")
        if u["pellizco_menique"].get("activo") and en_pm and m.lejos_menique > LEJOS_DEDO_MIN:
            out.append("pm")
        return out

    def _pellizco_dedo(self, m: Medidas, dd: dict, en_pa: bool, en_pm: bool):
        """PELLIZCO_ANULAR o PELLIZCO_MENIQUE si se cumple su condición completa; si no, None."""
        for c in self._candidato_dedo(m, dd, en_pa, en_pm):
            if c == "pa" and self._de_paso_al_menique(m):
                continue                  # el pulgar va camino al meñique: el anular no cuenta
            if c == "pa" and self._gana(m.pa, m.p, m.pc, *self._otros_activos(m, "pa"),
                                        limite=self._limite_gana(Sena.PELLIZCO_ANULAR)):
                return Sena.PELLIZCO_ANULAR
            if c == "pm" and self._gana(m.pm, m.p, m.pc, *self._otros_activos(m, "pm"),
                                        limite=self._limite_gana(Sena.PELLIZCO_MENIQUE)):
                return Sena.PELLIZCO_MENIQUE
        return None

    def _de_paso_al_menique(self, m: Medidas) -> bool:
        """Con el meñique buscado, el pulgar que va hacia el meñique (o que vuelve de él) pasa por
        encima del anular: esos cuadros no son un pellizco con el anular (darían un clic izquierdo
        de más). Un pellizco con el anular que ya se vio 2 cuadros seguidos queda firme: el temblor
        de la mano o un arrastre no lo cortan."""
        if not self.u["pellizco_menique"].get("activo") or self._n_anular >= ANULAR_FIRME:
            return False
        return bool(m.pm_bajando or m.pm_subiendo)

    def _dos_cerca(self, m: Medidas, dd: dict, en_pa: bool, en_pm: bool) -> bool:
        """El pulgar está en pellizco con el anular o el meñique pero otro dedo está casi igual de
        cerca: no se sabe cuál quiso usar, así que no se hace nada."""
        return bool(self._candidato_dedo(m, dd, en_pa, en_pm))


def clasificar_una(w, umbrales: dict | None = None, cuadros: int = 1) -> Sena:
    """Atajo para pruebas: clasifica la misma mano ``cuadros`` veces con un clasificador nuevo."""
    c = Clasificador(umbrales)
    s = Sena.NINGUNA
    for _ in range(max(1, cuadros)):
        s = c.clasificar(w)
    return s
