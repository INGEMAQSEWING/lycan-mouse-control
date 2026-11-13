"""DPI: llamar ANTES de importar tkinter o leer medidas de pantalla.

Sin esto, con escala del 125-150 % el puntero no llega a los bordes o cae corrido.
"""
from __future__ import annotations

import ctypes
import sys

_RESULTADO: str | None = None


def activar() -> str:
    """PER_MONITOR_AWARE_V2 (-4) -> SetProcessDpiAwareness(2) -> SetProcessDPIAware()."""
    global _RESULTADO
    if _RESULTADO is not None:
        return _RESULTADO
    if sys.platform != "win32":  # pragma: no cover
        _RESULTADO = "no-windows"
        return _RESULTADO
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        f = user32.SetProcessDpiAwarenessContext
        f.argtypes = (ctypes.c_void_p,)
        f.restype = ctypes.c_bool
        if f(ctypes.c_void_p(-4)):
            _RESULTADO = "per-monitor-v2"
            return _RESULTADO
        # ERROR_ACCESS_DENIED (5) = ya estaba fijado (p. ej. por el manifiesto del .exe)
        if ctypes.get_last_error() == 5:
            _RESULTADO = "ya-fijado"
            return _RESULTADO
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            _RESULTADO = "per-monitor"
            return _RESULTADO
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
        _RESULTADO = "system"
    except (AttributeError, OSError):
        _RESULTADO = "ninguno"
    return _RESULTADO


def escala_sistema() -> float:
    """1.0 = 100 %."""
    try:
        return ctypes.windll.user32.GetDpiForSystem() / 96.0
    except (AttributeError, OSError):
        return 1.0
