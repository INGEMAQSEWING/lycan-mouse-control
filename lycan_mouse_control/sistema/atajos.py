"""Atajos de teclado globales: RegisterHotKey + GetMessageW en un hilo propio.

- El registro y el bucle van en EL MISMO hilo (los WM_HOTKEY llegan a la cola de ese hilo).
- Antes de registrar se comprueba con ToUnicodeEx que la combinación no produzca un carácter
  en el teclado actual (AltGr = Ctrl+Alt: Ctrl+Alt+Q es "@" en el teclado latinoamericano).
- Las órdenes salen por una cola; nunca se toca tkinter desde este hilo.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import queue
import threading

log = logging.getLogger("lycan")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT, WM_USER = 0x0312, 0x0012, 0x0400
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LCONTROL, VK_LMENU = 0x10, 0x11, 0x12, 0xA2, 0xA4

TECLAS_ESPECIALES = {
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
    "ESPACIO": 0x20, "SPACE": 0x20, "INICIO": 0x24, "HOME": 0x24, "FIN": 0x23, "END": 0x23,
    "PAUSA": 0x13, "PAUSE": 0x13, "INSERT": 0x2D, "SUPR": 0x2E, "DELETE": 0x2E,
}
MODS = {"CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL, "ALT": MOD_ALT, "SHIFT": MOD_SHIFT,
        "MAYUS": MOD_SHIFT, "MAYÚS": MOD_SHIFT, "WIN": MOD_WIN}

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32.RegisterHotKey.argtypes = (wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
_user32.RegisterHotKey.restype = wt.BOOL
_user32.UnregisterHotKey.argtypes = (wt.HWND, ctypes.c_int)
_user32.UnregisterHotKey.restype = wt.BOOL
_user32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
_user32.GetMessageW.restype = wt.BOOL
_user32.PeekMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
_user32.PeekMessageW.restype = wt.BOOL
_user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
_user32.PostThreadMessageW.restype = wt.BOOL
_user32.ToUnicodeEx.argtypes = (wt.UINT, wt.UINT, ctypes.POINTER(ctypes.c_ubyte), wt.LPWSTR, ctypes.c_int,
                                wt.UINT, wt.HKL)
_user32.ToUnicodeEx.restype = ctypes.c_int
_user32.MapVirtualKeyExW.argtypes = (wt.UINT, wt.UINT, wt.HKL)
_user32.MapVirtualKeyExW.restype = wt.UINT
_user32.GetKeyboardLayout.argtypes = (wt.DWORD,)
_user32.GetKeyboardLayout.restype = wt.HKL
_user32.GetKeyboardLayoutList.argtypes = (ctypes.c_int, ctypes.POINTER(wt.HKL))
_user32.GetKeyboardLayoutList.restype = ctypes.c_int
_user32.GetForegroundWindow.restype = wt.HWND
_user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
_user32.GetWindowThreadProcessId.restype = wt.DWORD


class AtajoInvalido(ValueError):
    pass


def interpretar(texto: str) -> tuple[int, int]:
    """'Ctrl+Alt+M' -> (MOD_CONTROL|MOD_ALT, ord('M'))."""
    if not isinstance(texto, str) or not texto.strip():
        raise AtajoInvalido("atajo vacío")
    mods, vk = 0, None
    for parte in (p.strip() for p in texto.split("+")):
        up = parte.upper()
        if up in MODS:
            mods |= MODS[up]
        elif up in TECLAS_ESPECIALES:
            vk = TECLAS_ESPECIALES[up]
        elif len(up) == 1 and (up.isalnum()):
            vk = ord(up)
        else:
            raise AtajoInvalido(f"tecla desconocida: {parte}")
    if vk is None:
        raise AtajoInvalido("falta la tecla")
    if not mods & (MOD_CONTROL | MOD_ALT | MOD_WIN):
        raise AtajoInvalido("el atajo debe llevar Ctrl o Alt")
    return mods, vk


def texto_atajo(mods: int, vk: int) -> str:
    partes = []
    if mods & MOD_CONTROL:
        partes.append("Ctrl")
    if mods & MOD_ALT:
        partes.append("Alt")
    if mods & MOD_SHIFT:
        partes.append("Shift")
    if mods & MOD_WIN:
        partes.append("Win")
    inv = {v: k for k, v in TECLAS_ESPECIALES.items() if k.startswith("F") or k in ("INICIO", "FIN", "PAUSA")}
    partes.append(inv.get(vk, chr(vk) if 0x30 <= vk <= 0x5A else hex(vk)))
    return "+".join(partes)


def teclado_actual() -> int:
    hwnd = _user32.GetForegroundWindow()
    tid = _user32.GetWindowThreadProcessId(hwnd, None) if hwnd else 0
    return _user32.GetKeyboardLayout(tid) or 0


def teclados_instalados() -> list[int]:
    n = _user32.GetKeyboardLayoutList(0, None)
    if n <= 0:
        return []
    arr = (wt.HKL * n)()
    n = _user32.GetKeyboardLayoutList(n, arr)
    return [int(arr[i] or 0) for i in range(n)]


def teclado_latinoamericano() -> int | None:
    """HKL instalado del teclado latinoamericano (idioma 0x080A), o None."""
    for hkl in teclados_instalados():
        if (hkl & 0xFFFF) == 0x080A or ((hkl >> 16) & 0xFFFF) == 0x080A:
            return hkl
    return None


def produce_caracter(mods: int, vk: int, hkl: int | None = None) -> str | None:
    """Carácter que produce la combinación en el teclado dado (None si no produce ninguno)."""
    hkl = teclado_actual() if hkl is None else hkl
    estado = (ctypes.c_ubyte * 256)()
    if mods & MOD_CONTROL:
        estado[VK_CONTROL] = 0x80
        estado[VK_LCONTROL] = 0x80
    if mods & MOD_ALT:
        estado[VK_MENU] = 0x80
        estado[VK_LMENU] = 0x80
    if mods & MOD_SHIFT:
        estado[VK_SHIFT] = 0x80
    buf = ctypes.create_unicode_buffer(8)
    scan = _user32.MapVirtualKeyExW(vk, 0, hkl)
    # 0x4: no cambia el estado del teclado (Windows 10 1607+)
    n = _user32.ToUnicodeEx(vk, scan, estado, buf, 8, 0x4, hkl)
    if n == 0:
        return None
    if n < 0:
        return "(tecla muerta)"
    txt = buf.value[:n]
    return txt if any(ord(c) >= 0x20 for c in txt) else None


def texto_error_registro(nombre_atajo: str, codigo: int) -> str:
    if codigo == ERROR_HOTKEY_ALREADY_REGISTERED:
        return (f"El atajo {nombre_atajo} ya lo usa otro programa. "
                f"Puede cambiarlo en Opciones > Atajos.")
    return f"No se pudo usar el atajo {nombre_atajo} (código {codigo}). Puede cambiarlo en Opciones > Atajos."


class HiloAtajos(threading.Thread):
    """atajos: {'pausar': 'Ctrl+Alt+M', ...}. Cada pulsación pone el nombre en ``cola``.
    ``directos``: {nombre: función} que se llaman EN este hilo (deben ser cortas y seguras,
    p. ej. salida.soltar_todo al salir)."""

    def __init__(self, atajos: dict, cola: queue.Queue, directos: dict | None = None):
        super().__init__(daemon=True, name="atajos")
        self.atajos = dict(atajos)
        self.cola = cola
        self.directos = directos or {}
        self.tid = None
        self.fallidos: list[tuple[str, str]] = []   # (nombre, texto para el usuario)
        self.registrados: dict[int, str] = {}
        self.listo = threading.Event()

    def run(self):
        self.tid = _kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        _user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, 0)  # crea la cola
        for i, (nombre, texto) in enumerate(self.atajos.items(), start=1):
            try:
                mods, vk = interpretar(texto)
            except AtajoInvalido as e:
                self.fallidos.append((nombre, f"El atajo «{texto}» no es válido: {e}."))
                continue
            car = produce_caracter(mods, vk)
            if car:
                self.fallidos.append((nombre, f"El atajo {texto} escribe «{car}» en su teclado; no se usó. "
                                              f"Puede cambiarlo en Opciones > Atajos."))
                continue
            if _user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                self.registrados[i] = nombre
            else:
                self.fallidos.append((nombre, texto_error_registro(texto, ctypes.get_last_error())))
        for nombre, txt in self.fallidos:
            log.warning("Atajo %s: %s", nombre, txt)
        self.listo.set()
        try:
            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in self.registrados:
                    nombre = self.registrados[msg.wParam]
                    f = self.directos.get(nombre)
                    if f:
                        try:
                            f()
                        except Exception:  # noqa: BLE001
                            log.exception("Error en el atajo %s", nombre)
                    self.cola.put(nombre)
        finally:
            for i in self.registrados:
                _user32.UnregisterHotKey(None, i)

    def detener(self):
        if self.tid:
            _user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
