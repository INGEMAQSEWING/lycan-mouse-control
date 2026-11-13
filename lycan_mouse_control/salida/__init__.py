"""Salidas: Windows real (SendInput) y simulada (pruebas, asistente y --simular)."""
from .base import ErrorEnvio, SalidaBase
from .simulada import SalidaSimulada

__all__ = ["ErrorEnvio", "SalidaBase", "SalidaSimulada", "crear"]


def crear(simular: bool):
    if simular:
        return SalidaSimulada()
    from .windows import SalidaWindows
    return SalidaWindows()
