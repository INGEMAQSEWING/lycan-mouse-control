"""Medidas puras sobre los 21 puntos de una mano (ndarray 21x3).

Con puntos en metros (``mundo`` de MediaPipe) las medidas no cambian con la distancia
a la cámara. Ninguna función lanza excepción con datos raros: devuelven NaN y el
clasificador lo trata como "ninguna seña".
"""
from __future__ import annotations

import math

import numpy as np

from .constantes import DEDOS_LARGOS, PUNTOS_PALMA

_EPS = 1e-9


def _p(w, i):
    return w[i]


def dist(a, b) -> float:
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


def ang(a, b) -> float:
    """Ángulo en grados entre dos vectores (0 = misma dirección)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if not (na > _EPS and nb > _EPS):
        return float("nan")
    c = float(np.dot(a, b)) / (na * nb)
    if not math.isfinite(c):
        return float("nan")
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def escala_palma(w) -> float:
    """(|0-5| + |0-17| + |5-17| + |0-9|) / 4  (típico 0.075-0.095 m)."""
    return (dist(w[0], w[5]) + dist(w[0], w[17]) + dist(w[5], w[17]) + dist(w[0], w[9])) / 4.0


def centro_palma(w) -> np.ndarray:
    return np.mean(np.asarray(w, float)[list(PUNTOS_PALMA)], axis=0)


def doblez(w, dedo) -> float:
    """Suma de los ángulos de PIP y DIP; 0 = dedo recto. ``dedo``: nombre o 4 índices."""
    idx = DEDOS_LARGOS[dedo] if isinstance(dedo, str) else dedo
    mcp, pip, dip, punta = (w[i] for i in idx)
    return ang(np.subtract(pip, mcp), np.subtract(dip, pip)) + ang(np.subtract(dip, pip), np.subtract(punta, dip))


def razon_dedo(w, dedo) -> float:
    """|punta-0| / |PIP-0| (solo para desempatar)."""
    idx = DEDOS_LARGOS[dedo] if isinstance(dedo, str) else dedo
    d_pip = dist(w[idx[1]], w[0])
    return dist(w[idx[3]], w[0]) / (d_pip + _EPS)


def pellizco(w, palma=None) -> float:
    palma = escala_palma(w) if palma is None else palma
    return dist(w[4], w[8]) / (palma + _EPS)


def pellizco_corazon(w, palma=None) -> float:
    palma = escala_palma(w) if palma is None else palma
    return dist(w[4], w[12]) / (palma + _EPS)


def separacion_ic(w) -> float:
    """|8-12| / |5-9|: separación índice-corazón comparada con la de sus nudillos."""
    return dist(w[8], w[12]) / (dist(w[5], w[9]) + _EPS)


def angulo_ic(w) -> float:
    return ang(np.subtract(w[8], w[5]), np.subtract(w[12], w[9]))


def pulgar_recogido(w, palma=None) -> bool:
    palma = escala_palma(w) if palma is None else palma
    return dist(w[4], w[9]) / (palma + _EPS) < 0.55 or dist(w[4], w[13]) / (palma + _EPS) < 0.55


def punta_cerca_palma(w, punta, palma=None, centro=None) -> float:
    palma = escala_palma(w) if palma is None else palma
    c = centro_palma(w) if centro is None else centro
    return dist(w[punta], c) / (palma + _EPS)


def angulo_pulgar(w) -> float:
    """ang(3-2, 4-3): 0 = pulgar recto."""
    return ang(np.subtract(w[3], w[2]), np.subtract(w[4], w[3]))


def normal_palma(w) -> np.ndarray:
    """n = (5-0) x (17-0)."""
    return np.cross(np.subtract(w[5], w[0]), np.subtract(w[17], w[0]))


def separacion_media_puntas(w, palma=None) -> float:
    """Separación media entre puntas vecinas (4-8, 8-12, 12-16, 16-20) / palma."""
    palma = escala_palma(w) if palma is None else palma
    d = dist(w[4], w[8]) + dist(w[8], w[12]) + dist(w[12], w[16]) + dist(w[16], w[20])
    return d / 4.0 / (palma + _EPS)


def puntos_validos(w) -> bool:
    """False si hay NaN/inf, forma equivocada o la palma tiene tamaño ~0."""
    try:
        a = np.asarray(w, float)
    except (TypeError, ValueError):
        return False
    if a.shape != (21, 3) or not np.all(np.isfinite(a)):
        return False
    return escala_palma(a) > 1e-4
