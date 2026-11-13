"""'Abrir al encender el computador' (HKCU\\...\\Run, sin permisos de administrador)."""
from __future__ import annotations

import os
import sys

CLAVE = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE = "LycanMouseControl"


def comando() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimizado'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lanzador = os.path.join(os.path.dirname(raiz), "lycan_mouse_control.pyw")
    return f'"{exe}" "{lanzador}" --minimizado'


def activo() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE) as k:
            winreg.QueryValueEx(k, NOMBRE)
            return True
    except OSError:
        return False


def poner(si: bool) -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE, 0, winreg.KEY_SET_VALUE) as k:
            if si:
                winreg.SetValueEx(k, NOMBRE, 0, winreg.REG_SZ, comando())
            else:
                try:
                    winreg.DeleteValue(k, NOMBRE)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
