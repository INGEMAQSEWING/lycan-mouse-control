"""Cálculos puros de la calibración (sección 8.3). La pantalla está en ui/calibracion.py.

- Luz: brillo medio en gris; < 60 poca luz, > 200 contraluz.
- Distancia: ancho de la mano (puntos 0 a 17) en la imagen entre 0.08 y 0.25.
- Zona cómoda: percentiles 5 y 95 de x e y + 5 % de margen; mínimo 30 % x 30 %.
- Posturas: entrar = A + 0.35·(B-A), salir = A + 0.55·(B-A), con A = mediana "dentro" y
  B = mediana "fuera". Si las posturas se traslapan (diferencia < 3 desviaciones), se repite.
  El valor calibrado no puede alejarse más de ±40 % del de fábrica.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from .senas import UMBRALES_FABRICA, recortar_calibrado


def evaluar_luz(brillo: float) -> str:
    """'poca' | 'mucha' | 'ok' | 'sin_dato' (no llega imagen: no se puede decir que la luz está bien)."""
    if brillo is None or not math.isfinite(brillo):
        return "sin_dato"
    if brillo < 60:
        return "poca"
    if brillo > 200:
        return "mucha"
    return "ok"


def evaluar_distancia(ancho_mano: float | None, mano_baja: bool = False) -> str:
    """'sin_mano' | 'cerca' (acérquese) | 'lejos' (aléjese) | 'ok'.

    1.0.2 paquete C: con la mano baja (cerca del teclado) la mano queda más cerca de la cámara y
    se acepta un poco más grande."""
    from .mano_baja import ANCHO_MANO_MAX, ANCHO_MANO_MAX_BAJA
    if ancho_mano is None or not math.isfinite(ancho_mano):
        return "sin_mano"
    if ancho_mano < 0.08:
        return "cerca"
    if ancho_mano > (ANCHO_MANO_MAX_BAJA if mano_baja else ANCHO_MANO_MAX):
        return "lejos"
    return "ok"


def calcular_zona(puntos, aspecto_cam: float = 4 / 3) -> tuple[float, float, float, float] | None:
    """Puntos (u, v) del índice durante 5 s -> zona (x0, y0, x1, y1). None si no hay datos."""
    arr = np.asarray([p for p in puntos if p is not None], float)
    if arr.ndim != 2 or len(arr) < 10:
        return None
    arr = arr[np.all(np.isfinite(arr), axis=1)]
    if len(arr) < 10:
        return None
    x0, x1 = np.percentile(arr[:, 0], [5, 95])
    y0, y1 = np.percentile(arr[:, 1], [5, 95])
    mx, my = 0.05 * (x1 - x0), 0.05 * (y1 - y0)
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    if x1 - x0 < 0.30:
        c = (x0 + x1) / 2
        x0, x1 = c - 0.15, c + 0.15
    if y1 - y0 < 0.30:
        c = (y0 + y1) / 2
        y0, y1 = c - 0.15, c + 0.15
    def ajustar(a, b):
        if a < 0:
            b, a = b - a, 0.0
        if b > 1:
            a, b = a - (b - 1), 1.0
        return max(a, 0.0), min(b, 1.0)
    x0, x1 = ajustar(x0, x1)
    y0, y1 = ajustar(y0, y1)
    return (round(float(x0), 3), round(float(y0), 3), round(float(x1), 3), round(float(y1), 3))


def _limpio(vals):
    a = np.asarray([v for v in vals if v is not None and math.isfinite(v)], float)
    return a


def umbral(dentro, fuera):
    """(entrar, salir, problema) a partir de las muestras de las dos posturas."""
    A, B = _limpio(dentro), _limpio(fuera)
    if len(A) < 5 or len(B) < 5:
        return None, None, "pocas muestras"
    ma, mb = float(np.median(A)), float(np.median(B))
    sd = max(float(np.std(A)), float(np.std(B)))
    if abs(ma - mb) < 3 * sd:
        return None, None, "traslape"
    return ma + 0.35 * (mb - ma), ma + 0.55 * (mb - ma), None


# medida -> (postura dentro, postura fuera, grupo, clave entrar, clave salir)
PARES = {
    "pellizco": ("pellizco", "abierta", "pellizco", "entrar", "salir", "p"),
    "juntos_s": ("juntos", "v", "juntos", "s_entrar", "s_salir", "s"),
    "juntos_a": ("juntos", "v", "juntos", "a_entrar", "a_salir", "a"),
    "v_s": ("v", "juntos", "v", "s_entrar", "s_salir", "s"),
}


def calcular_umbrales(muestras: dict, senas_actual: dict | None = None):
    """muestras: {postura: [medidas dict con p, s, a...]}. Devuelve (senas_nuevo, problemas).

    ``problemas``: lista de (medida, motivo) para pedir que se repita."""
    nuevo = copy.deepcopy(senas_actual) if senas_actual else {}
    problemas = []
    for nombre, (pd, pf, grupo, k_in, k_out, medida) in PARES.items():
        dentro = [m.get(medida) for m in muestras.get(pd, [])]
        fuera = [m.get(medida) for m in muestras.get(pf, [])]
        e, s, prob = umbral(dentro, fuera)
        if prob:
            problemas.append((nombre, prob))
            continue
        fab = UMBRALES_FABRICA[grupo]
        g = nuevo.setdefault(grupo, {})
        g[k_in] = round(recortar_calibrado(e, fab[k_in]), 3)
        g[k_out] = round(recortar_calibrado(s, fab[k_out]), 3)
    return nuevo, problemas
