"""Generador de manos sintéticas para las pruebas (re-exporta lycan_mouse_control.sintetico,
que también usa el programa para los dibujos de la chuleta y el asistente)."""
from lycan_mouse_control.sintetico import *  # noqa: F401,F403
from lycan_mouse_control.sintetico import (POSTURAS, SENA_ESPERADA, Variacion, construir, intermedia,  # noqa: F401
                                           mano, mover_mano, proyectar, rotacion, variacion_aleatoria)
