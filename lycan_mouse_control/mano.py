"""Datos de una mano detectada en un cuadro (lo que entrega el detector)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ManoDetectada:
    img: np.ndarray        # 21x3, x e y en 0..1 de la imagen YA EN ESPEJO (la z no se usa)
    mundo: np.ndarray      # 21x3 en metros, origen cerca del centro de la mano
    etiqueta: str = "Right"  # 'Left' | 'Right' (con imagen en espejo = mano real)
    confianza: float = 1.0
