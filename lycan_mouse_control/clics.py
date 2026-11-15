"""Decisiones puras de los clics nuevos de la 1.0.2 (paquete A): qué hace el meñique y cuánto
espera la seguridad de la tecla de clic antes de soltar sola el botón.

No toca Windows: la máquina de estados (estados.py) usa estas funciones y el gancho de teclado
(sistema/teclado.py) le pasa los valores de Windows.
"""
from __future__ import annotations

from . import constantes as K

# acción del meñique -> ("clic", botón, veces) | ("pulsar", teclas)
ACCIONES_MENIQUE: dict[str, tuple] = {
    "doble_clic": ("clic", K.IZQ, 2),
    "clic_derecho": ("clic", K.DER, 1),
    "clic_medio": ("clic", K.MEDIO, 1),
    "enter": ("pulsar", ("enter",)),
    "esc": ("pulsar", ("esc",)),
    "suprimir": ("pulsar", ("supr",)),
    "deshacer": ("pulsar", ("ctrl", "z")),
}
MENIQUE_FABRICA = "doble_clic"
ORDEN_MENIQUE = ("doble_clic", "clic_derecho", "clic_medio", "enter", "esc", "suprimir", "deshacer", "nada")

# Seguridad de la tecla de clic: si la tecla sostiene el botón y no llega la repetición del
# teclado en este tiempo, se supone que se perdió el «soltar» y se suelta sola.
LIMITE_TECLA_PRUEBAS_S = 1.0
MARGEN_TECLA_S = 0.25


def accion_menique(nombre) -> tuple | None:
    """None si es "nada" o no se conoce (entonces la seña ni se detecta)."""
    return ACCIONES_MENIQUE.get(nombre) if isinstance(nombre, str) else None


def limite_tecla_s(retraso: int | None, velocidad: int | None) -> float:
    """Tiempo sin repetición tras el cual se suelta la tecla de clic.

    retraso: SPI_GETKEYBOARDDELAY (0..3 = 250..1000 ms). velocidad: SPI_GETKEYBOARDSPEED
    (0..31 = unas 2.5..30 repeticiones por segundo). Límite = retraso + 2 repeticiones + 250 ms.
    Con datos raros se usa el valor de las pruebas (1 s)."""
    try:
        r = int(retraso)
        v = int(velocidad)
    except (TypeError, ValueError):
        return LIMITE_TECLA_PRUEBAS_S
    if not (0 <= r <= 3 and 0 <= v <= 31):
        return LIMITE_TECLA_PRUEBAS_S
    retraso_s = (r + 1) * 0.25
    por_segundo = 2.5 + v * (27.5 / 31.0)
    return retraso_s + 2.0 / por_segundo + MARGEN_TECLA_S
