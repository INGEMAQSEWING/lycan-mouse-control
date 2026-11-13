"""Ventana activa, nombre del .exe, elevación (UIPI), WS_EX_NOACTIVATE e instancia única."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ALREADY_EXISTS = 183

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetParent.argtypes = (wt.HWND,)
user32.GetParent.restype = wt.HWND
user32.GetAncestor.argtypes = (wt.HWND, wt.UINT)
user32.GetAncestor.restype = wt.HWND
user32.GetWindowRect.argtypes = (wt.HWND, ctypes.POINTER(wt.RECT))
user32.GetWindowRect.restype = wt.BOOL
user32.GetWindowLongW.argtypes = (wt.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = (wt.HWND, ctypes.c_int, ctypes.c_long)
user32.SetWindowLongW.restype = ctypes.c_long
user32.FindWindowW.argtypes = (wt.LPCWSTR, wt.LPCWSTR)
user32.FindWindowW.restype = wt.HWND
user32.SetForegroundWindow.argtypes = (wt.HWND,)
user32.ShowWindow.argtypes = (wt.HWND, ctypes.c_int)
user32.GetDoubleClickTime.restype = wt.UINT
kernel32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = (wt.HANDLE,)
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD))
kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wt.BOOL, wt.LPCWSTR)
kernel32.CreateMutexW.restype = wt.HANDLE
advapi32.OpenProcessToken.argtypes = (wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE))
advapi32.OpenProcessToken.restype = wt.BOOL
advapi32.GetTokenInformation.argtypes = (wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                         ctypes.POINTER(wt.DWORD))
advapi32.GetTokenInformation.restype = wt.BOOL


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wt.DWORD)]


def ventana_activa() -> int:
    return user32.GetForegroundWindow() or 0


def pid_de_ventana(hwnd) -> int:
    if not hwnd:
        return 0
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def ruta_exe(pid: int) -> str:
    if not pid:
        return ""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wt.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(h)


def exe_ventana_activa() -> str:
    return ruta_exe(pid_de_ventana(ventana_activa()))


def es_elevado(pid: int | None = None) -> bool | None:
    """True si el proceso corre como administrador; None si no se puede saber."""
    h = kernel32.GetCurrentProcess() if pid is None else kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    tok = wt.HANDLE()
    try:
        if not advapi32.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):  # TOKEN_QUERY
            return None
        te = TOKEN_ELEVATION()
        ret = wt.DWORD()
        if not advapi32.GetTokenInformation(tok, 20, ctypes.byref(te), ctypes.sizeof(te), ctypes.byref(ret)):
            return None
        return bool(te.TokenIsElevated)
    finally:
        if tok:
            kernel32.CloseHandle(tok)
        if pid is not None:
            kernel32.CloseHandle(h)


_YO_ELEVADO = None


def yo_elevado() -> bool:
    global _YO_ELEVADO
    if _YO_ELEVADO is None:
        _YO_ELEVADO = bool(es_elevado(None))
    return _YO_ELEVADO


def primer_plano_bloqueado() -> bool:
    """True si la ventana activa es de un proceso elevado y nosotros no (UIPI: SendInput falla
    en silencio). Si no se puede abrir el proceso, se asume que no lo está."""
    if yo_elevado():
        return False
    hwnd = ventana_activa()
    pid = pid_de_ventana(hwnd)
    if not pid or pid == os.getpid():
        return False
    return es_elevado(pid) is True


def es_propia(hwnd=None) -> bool:
    hwnd = ventana_activa() if hwnd is None else hwnd
    return pid_de_ventana(hwnd) == os.getpid()


def raiz(hwnd_tk: int) -> int:
    """HWND de nivel superior de una ventana de tkinter (winfo_id da el hijo interno)."""
    p = user32.GetParent(hwnd_tk)
    return p or hwnd_tk


def agregar_estilo(hwnd: int, estilo: int):
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | estilo)


def no_activar(hwnd: int):
    """WS_EX_NOACTIVATE: hacer clic en la ventana no le quita el foco al programa de dibujo."""
    agregar_estilo(hwnd, WS_EX_NOACTIVATE)


def atravesable(hwnd: int):
    """Los clics atraviesan la ventana (indicador junto al cursor)."""
    agregar_estilo(hwnd, WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


def rect(hwnd: int):
    r = wt.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return (r.left, r.top, r.right, r.bottom)
    return None


def tiempo_doble_clic_ms() -> int:
    try:
        return int(user32.GetDoubleClickTime())
    except OSError:
        return 500


_MUTEX = None


def instancia_unica(nombre: str) -> bool:
    """True si somos la única instancia. Mantiene el mutex abierto mientras viva el proceso."""
    global _MUTEX
    _MUTEX = kernel32.CreateMutexW(None, False, nombre)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def traer_al_frente(titulo: str) -> bool:
    hwnd = user32.FindWindowW(None, titulo)
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    return False


def reiniciar_como_admin(argumentos: list[str] | None = None) -> bool:
    """Vuelve a abrir el programa como administrador (aparece el aviso de Windows)."""
    shell32 = ctypes.WinDLL("shell32")
    shell32.ShellExecuteW.argtypes = (wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_int)
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, " ".join(argumentos or [])
    else:
        exe = sys.executable
        params = "-m lycan_mouse_control " + " ".join(argumentos or [])
    r = shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return (r or 0) > 32


def abrir_carpeta(ruta: str):
    try:
        os.startfile(ruta)  # noqa: S606
    except OSError:
        pass
