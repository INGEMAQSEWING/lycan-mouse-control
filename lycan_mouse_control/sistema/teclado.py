"""Clic con una tecla o un pedal (1.0.2 paquete A): gancho de teclado de bajo nivel.

- Hilo propio con SetWindowsHookExW(WH_KEYBOARD_LL) + GetMessageW (el gancho tiene que vivir en
  el hilo que recibe los mensajes).
- El callback SOLO llama a ``decidir`` (pura, se prueba sin Windows) y encola el evento. Nunca
  hace SendInput ni toca tkinter.
- Se reconoce la tecla elegida y nada más: no se guarda ni se anota ninguna otra tecla.
- Perro guardián: si pasan 60 s sin recibir nada, se vuelve a poner el gancho (Windows quita
  en silencio los ganchos que tardan). Si ponerlo falla, se reintenta y se avisa al volver.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import sys
import threading
import time
from dataclasses import dataclass

from ..constantes import LYCAN_EXTRA

log = logging.getLogger("lycan")

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
WM_QUIT, WM_TIMER = 0x0012, 0x0113
LLKHF_EXTENDED, LLKHF_INJECTED, LLKHF_UP = 0x01, 0x10, 0x80
SPI_GETKEYBOARDDELAY, SPI_GETKEYBOARDSPEED = 0x0016, 0x000A

VK_NUMPAD5, VK_CLEAR = 0x65, 0x0C          # 5 numérico con y sin Bloq Num
SCAN_NUMPAD5 = 0x4C
# Ctrl, Shift, Alt y Windows (izquierda, derecha y genéricas) no sirven como tecla de clic
MODIFICADORES = frozenset({0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C})

VIGILAR_S = 60.0        # sin recibir nada en este tiempo: se vuelve a poner el gancho
REVISAR_MS = 5000       # cada cuánto despierta el hilo para revisar


@dataclass
class EstadoGancho:
    """Lo que el gancho necesita saber para decidir. Lo actualiza el motor (y Opciones)."""
    activa: bool = True              # tecla_clic.activa
    vk: int = VK_NUMPAD5
    scan: int = SCAN_NUMPAD5
    extendida: bool = False
    numerico: bool = True            # el «5 del teclado numérico» (con y sin Bloq Num)
    motor_activo: bool = False       # la máquina está en ACTIVO (en pausa la tecla pasa normal)
    inercia_activa: bool = False     # paquetes B y C: cualquier tecla frena la inercia
    grabando: bool = False           # Opciones o el asistente esperan la tecla nueva
    # internos
    abajo_suprimido: bool = False    # el bajar de esta pulsación se tragó (el subir también)
    tragar_subir_vk: int | None = None   # al grabar: el subir de la tecla grabada no llega al programa

    @classmethod
    def desde_config(cls, cfg_tecla: dict | None) -> "EstadoGancho":
        e = cls()
        e.poner_config(cfg_tecla)
        return e

    def poner_config(self, cfg_tecla: dict | None):
        c = cfg_tecla or {}
        self.activa = c.get("activa", True) is not False
        self.numerico = c.get("numerico", True) is not False
        try:
            self.vk = int(c.get("vk", VK_NUMPAD5))
            self.scan = int(c.get("scan", SCAN_NUMPAD5))
        except (TypeError, ValueError):
            self.vk, self.scan = VK_NUMPAD5, SCAN_NUMPAD5
        self.extendida = bool(c.get("extendida", False))


def es_la_tecla(vk: int, scan: int, extendida: bool, estado: EstadoGancho) -> bool:
    if estado.numerico:
        return vk in (VK_NUMPAD5, VK_CLEAR) and scan == SCAN_NUMPAD5 and not extendida
    return vk == estado.vk and scan == estado.scan and bool(extendida) == bool(estado.extendida)


def decidir(vk: int, scan: int, extendida: bool, abajo: bool, inyectada: bool, extra: int,
            estado: EstadoGancho, t: float = 0.0):
    """Decide qué hacer con una tecla. Devuelve (suprimir, evento o None).

    Eventos: ("tecla_clic", True/False, t), ("tecla_repite", t), ("frenar",),
    ("grabada", vk, scan, extendida), ("rechazada", vk)."""
    # nuestras propias teclas (y las de otros programas que inyectan) pasan siempre
    if inyectada or extra == LYCAN_EXTRA:
        return False, None
    if estado.grabando:
        if not abajo:
            return False, None
        if vk in MODIFICADORES:
            return True, ("rechazada", vk)
        estado.grabando = False
        estado.tragar_subir_vk = vk
        return True, ("grabada", vk, scan, bool(extendida))
    if estado.tragar_subir_vk is not None and vk == estado.tragar_subir_vk:
        if not abajo:
            estado.tragar_subir_vk = None
            return True, None
        return True, None            # repeticiones de la tecla que se acaba de grabar
    if es_la_tecla(vk, scan, extendida, estado):
        if abajo:
            if estado.abajo_suprimido:
                return True, ("tecla_repite", t)     # repetición del teclado: se traga
            if estado.activa and estado.motor_activo:
                estado.abajo_suprimido = True
                return True, ("tecla_clic", True, t)
            return False, None                       # en pausa la tecla escribe normal
        if estado.abajo_suprimido:
            # el subir se traga SOLO si el bajar se tragó (si no, quedaría pegada en el programa)
            estado.abajo_suprimido = False
            return True, ("tecla_clic", False, t)
        return False, None
    if abajo and estado.inercia_activa:
        return False, ("frenar",)
    return False, None


def nombre_tecla(vk: int, scan: int, extendida: bool) -> str:
    """Nombre de la tecla para mostrar (el que da Windows, o uno armado)."""
    if vk in (VK_NUMPAD5, VK_CLEAR) and scan == SCAN_NUMPAD5 and not extendida:
        return "5 del teclado numérico"
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(64)
            lparam = (int(scan) & 0xFF) << 16 | (1 << 24 if extendida else 0)
            n = ctypes.windll.user32.GetKeyNameTextW(lparam, buf, 64)
            if n > 0 and buf.value.strip():
                return buf.value.strip()
        except (OSError, AttributeError):
            pass
    from ..teclas import TECLAS
    for nombre, vk_t in TECLAS.values():
        if vk_t == vk:
            return nombre
    return f"Tecla {vk}"


def datos_tecla_grabada(vk: int, scan: int, extendida: bool) -> dict:
    """Lo que se guarda en tecla_clic al grabar una tecla (el 5 numérico vuelve a «numérico»)."""
    if vk in (VK_NUMPAD5, VK_CLEAR) and scan == SCAN_NUMPAD5 and not extendida:
        return {"numerico": True, "vk": VK_NUMPAD5, "scan": SCAN_NUMPAD5, "extendida": False,
                "nombre": "5 del teclado numérico"}
    return {"numerico": False, "vk": int(vk), "scan": int(scan), "extendida": bool(extendida),
            "nombre": nombre_tecla(vk, scan, extendida)}


def limite_repeticion_s() -> float:
    """Límite de la seguridad de la tecla con los valores de repetición de Windows."""
    from ..clics import LIMITE_TECLA_PRUEBAS_S, limite_tecla_s
    if sys.platform != "win32":
        return LIMITE_TECLA_PRUEBAS_S
    try:
        spi = ctypes.windll.user32.SystemParametersInfoW
        r, v = wt.UINT(), wt.DWORD()
        ok1 = spi(SPI_GETKEYBOARDDELAY, 0, ctypes.byref(r), 0)
        ok2 = spi(SPI_GETKEYBOARDSPEED, 0, ctypes.byref(v), 0)
        if ok1 and ok2:
            return limite_tecla_s(r.value, v.value)
    except (OSError, AttributeError):
        pass
    return LIMITE_TECLA_PRUEBAS_S


# ---------------------------------------------------------------- Windows
if sys.platform == "win32":
    LRESULT = ctypes.c_ssize_t
    ULONG_PTR = ctypes.c_size_t

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                    ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]

    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _u32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD)
    _u32.SetWindowsHookExW.restype = wt.HHOOK
    _u32.UnhookWindowsHookEx.argtypes = (wt.HHOOK,)
    _u32.UnhookWindowsHookEx.restype = wt.BOOL
    _u32.CallNextHookEx.argtypes = (wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    _u32.CallNextHookEx.restype = LRESULT
    _u32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
    _u32.GetMessageW.restype = wt.BOOL
    _u32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
    _u32.PostThreadMessageW.restype = wt.BOOL
    _u32.SetTimer.argtypes = (wt.HWND, ULONG_PTR, wt.UINT, ctypes.c_void_p)
    _u32.SetTimer.restype = ULONG_PTR
    _u32.KillTimer.argtypes = (wt.HWND, ULONG_PTR)
    _u32.KillTimer.restype = wt.BOOL
    _k32.GetModuleHandleW.argtypes = (wt.LPCWSTR,)
    _k32.GetModuleHandleW.restype = wt.HMODULE
    _k32.GetCurrentThreadId.restype = wt.DWORD


class GanchoTeclado(threading.Thread):
    """Hilo del gancho. ``al_evento(evento)`` se llama desde ESTE hilo: tiene que ser rápido
    (poner en una cola). ``estado`` lo comparte con el motor."""

    def __init__(self, estado: EstadoGancho, al_evento):
        super().__init__(daemon=True, name="gancho-teclado")
        self.estado = estado
        self.al_evento = al_evento
        self._hook = None
        self._proc = None            # referencia al HOOKPROC (si se pierde, Windows llama a basura)
        self._tid = None
        self._ult = time.monotonic()
        self._fallo = False
        self.listo = threading.Event()
        self.error: str | None = None

    # ---- callback (hilo del gancho) ----
    def _callback(self, n_code, w_param, l_param):
        try:
            if n_code >= 0:
                self._ult = time.monotonic()
                k = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                abajo = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                suprimir, evento = decidir(int(k.vkCode), int(k.scanCode), bool(k.flags & LLKHF_EXTENDED),
                                           abajo, bool(k.flags & LLKHF_INJECTED), int(k.dwExtraInfo),
                                           self.estado, time.perf_counter())
                if evento is not None:
                    try:
                        self.al_evento(evento)
                    except Exception:  # noqa: BLE001 - nunca romper el teclado del usuario
                        pass
                if suprimir:
                    return 1
        except Exception:  # noqa: BLE001
            pass
        return _u32.CallNextHookEx(None, n_code, w_param, l_param)

    def _poner(self) -> bool:
        mod = _k32.GetModuleHandleW(None)
        nuevo = _u32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, mod, 0)
        if not nuevo:
            log.warning("No se pudo poner el gancho de teclado (error %s)", ctypes.get_last_error())
            return False
        viejo, self._hook = self._hook, nuevo     # primero el nuevo, después se quita el viejo
        if viejo:
            _u32.UnhookWindowsHookEx(viejo)
        self._ult = time.monotonic()
        return True

    def run(self):  # pragma: no cover - necesita Windows y un teclado de verdad
        if sys.platform != "win32":
            self.error = "solo Windows"
            self.listo.set()
            return
        self._tid = _k32.GetCurrentThreadId()
        self._proc = HOOKPROC(self._callback)
        if not self._poner():
            self._fallo = True
            self.error = "no se pudo poner el gancho"
        timer = _u32.SetTimer(None, 0, REVISAR_MS, None)
        self.listo.set()
        msg = wt.MSG()
        try:
            while True:
                r = _u32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r == 0 or r == -1:
                    break
                if msg.message == WM_TIMER:
                    self._vigilar()
        finally:
            if timer:
                _u32.KillTimer(None, timer)
            if self._hook:
                _u32.UnhookWindowsHookEx(self._hook)
                self._hook = None

    def _vigilar(self):  # pragma: no cover
        if self._fallo or time.monotonic() - self._ult > VIGILAR_S:
            estaba_mal = self._fallo
            if self._poner():
                if estaba_mal:
                    self._fallo = False
                    self.error = None
                    try:
                        self.al_evento(("gancho_perdido",))
                    except Exception:  # noqa: BLE001
                        pass
            else:
                self._fallo = True

    def detener(self):
        if self._tid:
            try:
                _u32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except OSError:
                pass

    def grabar(self, si: bool = True):
        """Opciones / asistente: la próxima tecla (que no sea Ctrl, Shift, Alt ni Windows) se graba."""
        self.estado.grabando = bool(si)
