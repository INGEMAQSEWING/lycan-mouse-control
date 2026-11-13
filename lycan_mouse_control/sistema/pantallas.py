"""Escritorio virtual y monitores (EnumDisplayMonitors), en píxeles físicos (con DPI activado)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

from ..mapeo import MONITOR_REFERENCIA, Monitor

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    _user32.GetSystemMetrics.restype = ctypes.c_int
    _user32.GetMonitorInfoW.argtypes = (wt.HMONITOR, ctypes.POINTER(MONITORINFO))
    _user32.GetMonitorInfoW.restype = wt.BOOL
    _user32.EnumDisplayMonitors.argtypes = (wt.HDC, ctypes.POINTER(wt.RECT), MONITORENUMPROC, wt.LPARAM)
    _user32.EnumDisplayMonitors.restype = wt.BOOL
except (AttributeError, OSError):  # pragma: no cover
    _user32 = None


def escritorio_virtual():
    if _user32 is None:
        return (0, 0, 1366, 768)
    g = _user32.GetSystemMetrics
    return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN), g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))


def monitores() -> list[Monitor]:
    out: list[Monitor] = []
    if _user32 is None:
        return [MONITOR_REFERENCIA]

    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if _user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcMonitor
            out.append(Monitor(r.left, r.top, r.right - r.left, r.bottom - r.top, bool(mi.dwFlags & 1)))
        return True

    try:
        _user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    except OSError:
        pass
    return out or [MONITOR_REFERENCIA]


def elegir(eleccion: str | int | None = "principal") -> Monitor:
    """'principal', 'todo' (escritorio completo) o el número de monitor (0, 1, ...)."""
    mons = monitores()
    if eleccion == "todo":
        x, y, w, h = escritorio_virtual()
        return Monitor(x, y, w, h, True)
    if isinstance(eleccion, int) or (isinstance(eleccion, str) and eleccion.isdigit()):
        i = int(eleccion)
        if 0 <= i < len(mons):
            return mons[i]
    for m in mons:
        if m.principal:
            return m
    return mons[0]


def descripcion(m: Monitor) -> str:
    return f"{m.ancho} x {m.alto}" + (" (principal)" if m.principal else "")
