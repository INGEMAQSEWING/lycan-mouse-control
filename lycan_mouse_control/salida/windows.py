"""Salida real: SendInput con ctypes (a partir de referencia\\winput.py, probado en el portátil).

- INPUT de 40 bytes en 64 bits (assert).
- Mover: MOVE|ABSOLUTE|VIRTUALDESK con la fórmula que redondea HACIA ARRIBA.
- Botones en eventos separados; un clic (down+up) en una sola llamada.
- dwExtraInfo = 'LYCN' en todos los eventos propios.
- SM_SWAPBUTTON: con botones invertidos (zurdos) se intercambian izquierdo y derecho.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys

from ..constantes import LYCAN_EXTRA
from .base import ErrorEnvio, SalidaBase

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
VK_LSHIFT, VK_LCONTROL, VK_LMENU = 0xA0, 0xA2, 0xA4
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
SM_SWAPBUTTON = 23

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTunion)]


assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

FLAGS_BOTON = {
    "izq": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "der": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "medio": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}
VK_TECLA = {"shift": VK_LSHIFT, "ctrl": VK_LCONTROL, "alt": VK_LMENU}

if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wt.UINT
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wt.POINT),)
    user32.GetCursorPos.restype = wt.BOOL
    user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)
    user32.MapVirtualKeyW.restype = wt.UINT
else:  # pragma: no cover
    user32 = None


def a_absoluto(x: int, y: int, vx: int, vy: int, vw: int, vh: int):
    """Píxel del escritorio virtual -> 0..65535. Windows vuelve con floor(n*ancho/65536),
    así que se redondea HACIA ARRIBA (la fórmula con +w/2 corre 1 px la mitad de las veces)."""
    nx = ((x - vx) * 65536 + vw - 1) // vw
    ny = ((y - vy) * 65536 + vh - 1) // vh
    return max(0, min(65535, nx)), max(0, min(65535, ny))


def de_absoluto(nx: int, ny: int, vx: int, vy: int, vw: int, vh: int):
    """Lo que hace Windows con la coordenada normalizada (para las pruebas)."""
    return vx + (nx * vw) // 65536, vy + (ny * vh) // 65536


def evento_raton(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> INPUT:
    i = INPUT(type=INPUT_MOUSE)
    i.mi = MOUSEINPUT(dx, dy, ctypes.c_uint32(data).value, flags, 0, LYCAN_EXTRA)
    return i


def evento_tecla(vk: int, arriba: bool) -> INPUT:
    i = INPUT(type=INPUT_KEYBOARD)
    scan = user32.MapVirtualKeyW(vk, 0) if user32 else 0
    i.ki = KEYBDINPUT(vk, scan, KEYEVENTF_KEYUP if arriba else 0, 0, LYCAN_EXTRA)
    return i


def escritorio_virtual():
    g = user32.GetSystemMetrics
    return (g(SM_XVIRTUALSCREEN), g(SM_YVIRTUALSCREEN), g(SM_CXVIRTUALSCREEN), g(SM_CYVIRTUALSCREEN))


class SalidaWindows(SalidaBase):
    def __init__(self):
        super().__init__()
        self.actualizar_pantalla()

    def actualizar_pantalla(self):
        self.escritorio = escritorio_virtual()
        self.invertidos = bool(user32.GetSystemMetrics(SM_SWAPBUTTON))

    def posicion_cursor(self):
        p = wt.POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    def construir(self, eventos: list) -> list:
        """Convierte eventos primitivos en estructuras INPUT (separado para probarlo)."""
        vx, vy, vw, vh = self.escritorio
        out = []
        for ev in eventos:
            tipo = ev[0]
            if tipo == "mover":
                nx, ny = a_absoluto(ev[1], ev[2], vx, vy, max(vw, 1), max(vh, 1))
                out.append(evento_raton(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))
            elif tipo == "boton":
                b = ev[1]
                if self.invertidos and b in ("izq", "der"):
                    b = "der" if b == "izq" else "izq"
                down, up = FLAGS_BOTON[b]
                out.append(evento_raton(down if ev[2] else up))
            elif tipo == "rueda":
                out.append(evento_raton(MOUSEEVENTF_WHEEL, data=int(ev[1])))
            elif tipo == "tecla":
                out.append(evento_tecla(VK_TECLA[ev[1]], arriba=not ev[2]))
        return out

    def _enviar(self, eventos: list):
        ins = self.construir(eventos)
        if not ins:
            return 0
        arr = (INPUT * len(ins))(*ins)
        n = user32.SendInput(len(ins), arr, ctypes.sizeof(INPUT))
        if n != len(ins):
            # pantalla bloqueada, UAC o escritorio seguro. (La ventana de administrador NO se
            # detecta aquí: SendInput devuelve éxito igual; ver sistema.ventanas_win.)
            raise ErrorEnvio(ctypes.get_last_error(), "SendInput bloqueado")
        return n
