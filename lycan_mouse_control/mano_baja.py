"""1.0.2 paquete C «Mano baja»: trabajar con la mano cerca del teclado, sin levantar el brazo.

Lógica PURA (no importa ctypes, cv2 ni tkinter): la usan la calibración, el motor y el asistente.

- ``recortar_zona``: la zona de la mano no puede bajar tanto que la muñeca se salga de la imagen.
- ``muneca_visible``: en la calibración, la muñeca se tiene que ver casi siempre.
- Con la mano baja la mano queda más cerca de la cámara: ``calibracion.evaluar_distancia`` la acepta
  un poco más grande (``ANCHO_MANO_MAX_BAJA``).
- ``VigiaManoBaja``: avisa una vez si la mano pasa más de 2 s por encima de la zona.
"""
from __future__ import annotations

import math

MUNECA_LIMITE = 0.97        # la muñeca (punto 0) por debajo de esto se sale de la imagen
MUNECA_FRACCION = 0.90      # ... y se tiene que ver así en al menos el 90 % de los cuadros
MARGEN_MUNECA = 1.1         # y1 <= 1 - 1.1 x alto de la mano
ALTO_MIN_ZONA = 0.12        # la zona nunca queda más baja que esto (validar pide 0.1)
ANCHO_MANO_MAX = 0.25       # como en la calibración normal...
ANCHO_MANO_MAX_BAJA = 0.32  # ... pero con la mano baja se acepta un poco más cerca
ENCIMA_S = 2.0              # tiempo por encima de la zona antes del aviso
ENCIMA_MARGEN = 0.03        # la punta del índice más arriba que y0 - 0.03


def recortar_zona(zona: dict, alto_mano: float | None) -> dict:
    """Copia de la zona (x0, y0, x1, y1) con y1 <= 1 - 1.1 x alto de la mano.

    ``alto_mano`` = de la muñeca a la punta más alta, en fracción del alto de la imagen. Si no
    hay dato (o es raro) se devuelve la zona tal cual. Si al recortar queda muy baja, se sube
    entera (se corre y0 hacia arriba), sin salirse de la imagen."""
    z = dict(zona)
    try:
        alto = float(alto_mano)
    except (TypeError, ValueError):
        return z
    if not math.isfinite(alto) or alto <= 0 or alto >= 0.8:
        return z
    tope = 1.0 - MARGEN_MUNECA * alto
    if z["y1"] > tope:
        z["y1"] = round(tope, 3)
    if z["y1"] - z["y0"] < ALTO_MIN_ZONA:
        z["y0"] = round(max(0.0, z["y1"] - ALTO_MIN_ZONA), 3)
    return z


def muneca_visible(ys, limite: float = MUNECA_LIMITE, fraccion: float = MUNECA_FRACCION) -> bool:
    """True si la muñeca (y de la imagen, 0 arriba y 1 abajo) se vio por encima del borde de
    abajo en al menos el 90 % de los cuadros. Sin cuadros: False (no se puede decir que se ve)."""
    vals = []
    for y in ys or ():
        try:
            v = float(y)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v):
            vals.append(v)
    if not vals:
        return False
    dentro = sum(1 for y in vals if y < limite)
    return dentro >= fraccion * len(vals) - 1e-9


class VigiaManoBaja:
    """Con la mano baja: si la punta del índice pasa más de 2 s por encima de la zona, avisa
    «Baje la mano hasta la zona del teclado» UNA vez. Vuelve a poder avisar cuando la mano baja."""

    def __init__(self):
        self.desde = None
        self.avisado = False

    def paso(self, t: float, y_punta: float | None, y0_zona: float) -> bool:
        if y_punta is None or not math.isfinite(float(y_punta)):
            self.desde = None
            return False
        if float(y_punta) < y0_zona - ENCIMA_MARGEN:
            if self.desde is None:
                self.desde = t
            if not self.avisado and t - self.desde >= ENCIMA_S - 1e-9:
                self.avisado = True
                return True
            return False
        self.desde = None
        self.avisado = False
        return False
