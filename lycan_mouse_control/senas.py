"""Clasificador puro de una mano: puntos en metros (21x3) -> una sola Seña por cuadro.

Orden de prioridad (gana la primera que se cumpla):
PUNO, ACTIVAR, V, PELLIZCO_CORAZON (solo si la variante está activa), PELLIZCO,
ABIERTA, APUNTAR, NINGUNA.

Cada mano seguida tiene su propio ``Clasificador`` (lleva la histéresis de cada medida).
"""
from __future__ import annotations

import copy
import math
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
    ABIERTA = "ABIERTA"
    APUNTAR = "APUNTAR"
    NINGUNA = "NINGUNA"


EXT, DOB, DUD = "EXT", "DOB", "DUD"

PUNO_EN_CURSO_SALIR = 72.0   # ° para salir de "puño en curso" (se entra con 80°)
CUADROS_TRAS_CURSO = 5       # ~150 ms a 30 cuadros/s después de salir del puño en curso...
PELLIZCO_TRAS_CURSO = 0.20   # ... el pellizco tiene que estar claramente cerrado

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
}

# Medidas que la calibración puede mover (como máximo ±40 % de fábrica).
_CALIBRABLES = (
    ("pellizco", "entrar"), ("pellizco", "salir"),
    ("pellizco_corazon", "entrar"), ("pellizco_corazon", "salir"),
    ("juntos", "s_entrar"), ("juntos", "s_salir"), ("juntos", "a_entrar"), ("juntos", "a_salir"),
    ("v", "s_entrar"), ("v", "s_salir"),
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
    for grupo in ("pellizco", "pellizco_corazon", "juntos", "v"):
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

    def como_dict(self) -> dict:
        return {"palma": self.palma, "p": self.p, "pc": self.pc, "s": self.s, "a": self.a,
                "doblez": dict(self.doblez), "dedos": dict(self.dedos),
                "pulgar_ext": self.pulgar_ext, "extendidos": self.extendidos}


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
                       "pulgar_ang", "pulgar_dist", "sep_puntas")}
        self._dedos = {k: DUD for k in ("indice", "corazon", "anular", "menique")}
        self._h_pellizco = Histeresis(u["pellizco"]["entrar"], u["pellizco"]["salir"], True)
        self._h_pc = Histeresis(u["pellizco_corazon"]["entrar"], u["pellizco_corazon"]["salir"], True)
        self._h_js = Histeresis(u["juntos"]["s_entrar"], u["juntos"]["s_salir"], True)
        self._h_ja = Histeresis(u["juntos"]["a_entrar"], u["juntos"]["a_salir"], True)
        self._h_vs = Histeresis(u["v"]["s_entrar"], u["v"]["s_salir"], False)
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
            return self._clasificar(w, etiqueta)
        except (ValueError, FloatingPointError, TypeError, IndexError):
            self.sena = Sena.NINGUNA
            self.medidas = Medidas()
            return self.sena

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

        dd = m.dedos
        if self._puno_en_curso(m):
            # Un pellizco "ganado" mientras la mano pasa por el puño no vale: al abrir el puño
            # despacio la distancia pulgar-índice sigue dentro de la histéresis y daría un clic
            # izquierdo fantasma. Hay que volver a cerrar el pellizco de verdad.
            self._h_pellizco.dentro = False
            en_pellizco = False
        elif self._tras_curso <= CUADROS_TRAS_CURSO and not (m.p < PELLIZCO_TRAS_CURSO):
            # recién salida del puño (~150 ms): solo vale un pellizco claramente cerrado
            self._h_pellizco.dentro = False
            en_pellizco = False
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
            if ic_ext and am_dob and juntos_s and juntos_a:
                sena = Sena.ACTIVAR
            elif ic_ext and am_dob and v_s and math.isfinite(m.a) and m.a > u["v"]["a_min"]:
                sena = Sena.V
            elif (u["pellizco_corazon"].get("activo") and en_pc
                  and m.p > u["pellizco_extra"]["p_min_corazon"]):
                sena = Sena.PELLIZCO_CORAZON
            elif (en_pellizco and m.doblez["indice"] < u["pellizco_extra"]["doblez_indice_max"]
                  and g.dist(w[8], c) / palma > u["pellizco_extra"]["indice_palma_min"]):
                sena = Sena.PELLIZCO
            elif (all(v == EXT for v in dd.values()) and m.pulgar_ext
                  and sep_puntas > u["abierta"]["sep_min"]):
                sena = Sena.ABIERTA
            elif dd["indice"] == EXT and dd["corazon"] != EXT:
                sena = Sena.APUNTAR
        self.sena = sena
        self.medidas = m
        return sena


def clasificar_una(w, umbrales: dict | None = None, cuadros: int = 1) -> Sena:
    """Atajo para pruebas: clasifica la misma mano ``cuadros`` veces con un clasificador nuevo."""
    c = Clasificador(umbrales)
    s = Sena.NINGUNA
    for _ in range(max(1, cuadros)):
        s = c.clasificar(w)
    return s
