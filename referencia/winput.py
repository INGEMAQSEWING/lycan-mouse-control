"""winput.py - Inyeccion de raton/teclado en Windows con ctypes (sin pynput).
Probado con Python 3.10 64 bits en Windows 11.
"""
import ctypes
import ctypes.wintypes as wt
import threading

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------- constantes ----------
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0001, 0x0002, 0x0008
WHEEL_DELTA = 120
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LSHIFT, VK_LCONTROL = 0x10, 0x11, 0x12, 0xA0, 0xA2
MAPVK_VK_TO_VSC = 0
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SM_SWAPBUTTON = 23
# Firma reconocible para filtrar nuestros propios eventos (dwExtraInfo)
LYCAN_EXTRA = 0x4C59434E  # 'LYCN'

ULONG_PTR = ctypes.c_size_t  # 8 bytes en 64 bits, 4 en 32


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

user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wt.UINT
user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetCursorPos.argtypes = (ctypes.POINTER(wt.POINT),)
user32.MapVirtualKeyW.argtypes = (wt.UINT, wt.UINT)
user32.MapVirtualKeyW.restype = wt.UINT
user32.RegisterHotKey.argtypes = (wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = (wt.HWND, ctypes.c_int)
user32.GetMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
user32.GetMessageW.restype = wt.BOOL
user32.PostThreadMessageW.argtypes = (wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM)
user32.PostThreadMessageW.restype = wt.BOOL
user32.PeekMessageW.argtypes = (ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))


# ---------- DPI ----------
def set_dpi_awareness():
    """Llamar ANTES de crear ventanas (tkinter) y antes de leer metricas.
    Devuelve el nivel conseguido."""
    try:  # Win10 1703+: Per-Monitor v2
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except AttributeError:
        pass
    try:  # Win 8.1+
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    user32.SetProcessDPIAware()
    return "system"


# ---------- pantallas ----------
def virtual_screen():
    """(x, y, ancho, alto) del escritorio virtual (todas las pantallas)."""
    return (user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


MONITORENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


def monitors():
    """Lista de dicts {rect:(l,t,r,b), work:(...), primary:bool} en pixeles fisicos (si DPI-aware)."""
    out = []

    def cb(hmon, hdc, lprc, lparam):
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r, w = mi.rcMonitor, mi.rcWork
        out.append({"rect": (r.left, r.top, r.right, r.bottom),
                    "work": (w.left, w.top, w.right, w.bottom), "primary": bool(mi.dwFlags & 1)})
        return True
    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return out


# ---------- envio ----------
def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    n = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if n != len(inputs):
        # Menos eventos de los pedidos = otro hilo bloqueo la entrada, o escritorio seguro
        # (UAC, Ctrl+Alt+Supr, pantalla bloqueada). OJO: el bloqueo por UIPI (ventana de
        # administrador) NO se detecta aqui: SendInput devuelve exito igual. Usar
        # foreground_is_elevated() para avisar.
        raise OSError(ctypes.get_last_error(), "SendInput bloqueado (UIPI o escritorio seguro)")
    return n


def _mouse(flags, dx=0, dy=0, data=0):
    i = INPUT(type=INPUT_MOUSE)
    i.mi = MOUSEINPUT(dx, dy, ctypes.c_uint32(data).value, flags, 0, LYCAN_EXTRA)
    return i


def _key(vk, up=False, extended=False):
    i = INPUT(type=INPUT_KEYBOARD)
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if extended else 0)
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    i.ki = KEYBDINPUT(vk, scan, flags, 0, LYCAN_EXTRA)
    return i


def to_absolute(x, y):
    """Pixel del escritorio virtual -> coordenada normalizada 0..65535 (VIRTUALDESK).
    Windows convierte de vuelta con pixel = floor(n * ancho / 65536), asi que hay que
    usar TECHO (ceil); el redondeo normal falla en ~50 % de los pixeles (medido)."""
    vx, vy, vw, vh = virtual_screen()
    nx = ((x - vx) * 65536 + vw - 1) // vw
    ny = ((y - vy) * 65536 + vh - 1) // vh
    return max(0, min(65535, nx)), max(0, min(65535, ny))


class Injector:
    """Lleva la cuenta de lo que esta sostenido para poder soltarlo SIEMPRE."""

    def __init__(self):
        self._lock = threading.Lock()
        self.held_buttons = set()   # {'left','right','middle'}
        self.held_keys = set()      # {vk}
        self._wheel_acc = 0.0
        self.swapped = bool(user32.GetSystemMetrics(SM_SWAPBUTTON))  # zurdos (ver nota)

    # --- mover ---
    def move_to(self, x, y):
        nx, ny = to_absolute(int(round(x)), int(round(y)))
        _send(_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))

    # --- botones ---
    _FLAGS = {"left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
              "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
              "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)}

    def down(self, button):
        with self._lock:
            if button in self.held_buttons:
                return
            _send(_mouse(self._FLAGS[button][0]))
            self.held_buttons.add(button)

    def up(self, button):
        with self._lock:
            if button not in self.held_buttons:
                return
            self.held_buttons.discard(button)
            _send(_mouse(self._FLAGS[button][1]))

    def click(self, button="left"):
        d, u = self._FLAGS[button]
        _send(_mouse(d), _mouse(u))  # un solo SendInput: no se intercala con otra entrada

    def double_click(self, button="left"):
        d, u = self._FLAGS[button]
        _send(_mouse(d), _mouse(u), _mouse(d), _mouse(u))

    # --- rueda ---
    def wheel(self, notches=1.0, horizontal=False):
        """notches>0 = hacia adelante (acercar en la mayoria de CAD). Admite fracciones:
        se acumula y se envia en multiplos de 1 (rueda fina) - ver nota sobre apps
        que solo entienden 120."""
        delta = int(round(notches * WHEEL_DELTA))
        if delta:
            _send(_mouse(MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL, data=delta))

    def wheel_smooth(self, notches, min_step=WHEEL_DELTA):
        """Acumula fracciones y solo envia cuando junta min_step (120 = clic clasico,
        30 = rueda fina; 120 es lo seguro para LibreCAD/SketchUp)."""
        self._wheel_acc += notches * WHEEL_DELTA
        sent = 0
        while abs(self._wheel_acc) >= min_step:
            step = min_step if self._wheel_acc > 0 else -min_step
            _send(_mouse(MOUSEEVENTF_WHEEL, data=step))
            self._wheel_acc -= step
            sent += step
        return sent

    # --- teclas ---
    def key_down(self, vk):
        with self._lock:
            if vk in self.held_keys:
                return
            _send(_key(vk))
            self.held_keys.add(vk)

    def key_up(self, vk):
        with self._lock:
            if vk not in self.held_keys:
                return
            self.held_keys.discard(vk)
            _send(_key(vk, up=True))

    # --- 3D: orbitar y desplazar ---
    def begin_orbit(self):
        self.down("middle")

    def begin_pan(self):          # Shift + medio (SketchUp / Blender)
        self.key_down(VK_LSHIFT)
        self.down("middle")

    def end_drag(self):
        self.up("middle")
        self.key_up(VK_LSHIFT)

    # --- seguridad ---
    def release_all(self):
        """Suelta TODO lo que este sostenido. Llamar al pausar, al perder manos,
        al salir (try/finally + atexit) y si la ventana cambia de proceso."""
        with self._lock:
            ins = []
            for b in list(self.held_buttons):
                ins.append(_mouse(self._FLAGS[b][1]))
            for vk in list(self.held_keys):
                ins.append(_key(vk, up=True))
            self.held_buttons.clear(); self.held_keys.clear()
            self._wheel_acc = 0.0
            if ins:
                try:
                    _send(*ins)
                except OSError:
                    pass


def cursor_pos():
    p = wt.POINT(); user32.GetCursorPos(ctypes.byref(p)); return p.x, p.y


# ---------- atajos globales ----------
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT, WM_USER = 0x0312, 0x0012, 0x0400
PM_NOREMOVE = 0


class HotkeyThread(threading.Thread):
    """RegisterHotKey en un hilo propio con bucle GetMessage.
    IMPORTANTE: el registro y el bucle deben estar en EL MISMO hilo (los
    WM_HOTKEY llegan a la cola del hilo que registro con hWnd=NULL)."""

    def __init__(self, bindings):
        """bindings: lista de (mods, vk, callback). Ej: (MOD_CONTROL|MOD_ALT, ord('M'), pausar)"""
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = bindings
        self.tid = None
        self.failed = []            # [(mods, vk, winerror)] p.ej. 1409 = ya registrado por otro
        self.ready = threading.Event()

    def run(self):
        self.tid = kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, WM_USER, WM_USER, PM_NOREMOVE)  # crea la cola
        ok = {}
        for i, (mods, vk, cb) in enumerate(self.bindings, start=1):
            if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                ok[i] = cb
            else:
                self.failed.append((mods, vk, ctypes.get_last_error()))
        self.ready.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in ok:
                    try:
                        ok[msg.wParam]()   # mantener corto; delegar trabajo pesado a otro hilo/cola
                    except Exception as e:  # noqa
                        print("error en atajo:", e)
        finally:
            for i in ok:
                user32.UnregisterHotKey(None, i)

    def stop(self):
        if self.tid:
            user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)


# ---------- UIPI ----------
class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wt.DWORD)]


def is_elevated(pid=None):
    """True si el proceso (por defecto el actual) corre como administrador.
    Para otro pid necesita PROCESS_QUERY_LIMITED_INFORMATION (0x1000); devuelve None si no se puede."""
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wt.DWORD, wt.BOOL, wt.DWORD)
    kernel32.OpenProcess.restype = wt.HANDLE
    kernel32.GetCurrentProcess.restype = wt.HANDLE
    kernel32.CloseHandle.argtypes = (wt.HANDLE,)
    advapi32.OpenProcessToken.argtypes = (wt.HANDLE, wt.DWORD, ctypes.POINTER(wt.HANDLE))
    advapi32.GetTokenInformation.argtypes = (wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                             ctypes.POINTER(wt.DWORD))
    h = kernel32.GetCurrentProcess() if pid is None else kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    tok = wt.HANDLE()
    try:
        if not advapi32.OpenProcessToken(h, 0x0008, ctypes.byref(tok)):  # TOKEN_QUERY
            return None
        te = TOKEN_ELEVATION(); ret = wt.DWORD()
        if not advapi32.GetTokenInformation(tok, 20, ctypes.byref(te), ctypes.sizeof(te), ctypes.byref(ret)):
            return None
        return bool(te.TokenIsElevated)
    finally:
        if tok:
            kernel32.CloseHandle(tok)
        if pid is not None:
            kernel32.CloseHandle(h)


def foreground_is_elevated():
    """Para avisar: 'La ventana activa es de administrador; el control por gestos no puede manejarla'."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wt.DWORD(); user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return is_elevated(pid.value)
