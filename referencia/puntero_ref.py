# Codigo de referencia: suavizado y precision del puntero (Lycan Mouse Control)
import ctypes, math, time
from collections import deque
from ctypes import wintypes

# ---------- 1) DPI: llamar ANTES de crear Tk() o ventanas de cv2 ----------
def activar_dpi():
    u32 = ctypes.windll.user32
    try:  # Win10 1703+: PER_MONITOR_AWARE_V2 = -4
        if u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR
        return "per-monitor"
    except Exception:
        pass
    u32.SetProcessDPIAware()
    return "system"

# ---------- 2) One Euro Filter (Casiez 2012) con tiempo real ----------
class LowPass:
    def __init__(s): s.y = None
    def __call__(s, x, a):
        s.y = x if s.y is None else a * x + (1 - a) * s.y
        return s.y

def _alpha(cutoff, dt):
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)

class OneEuro:
    def __init__(s, mincutoff=1.0, beta=0.007, dcutoff=1.0):
        s.mincutoff, s.beta, s.dcutoff = mincutoff, beta, dcutoff
        s.x, s.dx, s.t, s.prev = LowPass(), LowPass(), None, None
    def reset(s):
        s.x, s.dx, s.t, s.prev = LowPass(), LowPass(), None, None
    def __call__(s, value, t):
        if s.t is None:
            s.t, s.prev = t, value
            s.dx(0.0, 1.0)
            return s.x(value, 1.0)
        dt = max(t - s.t, 1e-3); s.t = t
        edx = s.dx((value - s.prev) / dt, _alpha(s.dcutoff, dt))
        s.prev = value
        cutoff = s.mincutoff + s.beta * abs(edx)
        return s.x(value, _alpha(cutoff, dt))

# ---------- 3) Pantallas: escritorio virtual y monitor elegido ----------
SM_XV, SM_YV, SM_CXV, SM_CYV = 76, 77, 78, 79
def escritorio_virtual():
    g = ctypes.windll.user32.GetSystemMetrics
    return g(SM_XV), g(SM_YV), g(SM_CXV), g(SM_CYV)

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

def monitores():
    res = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                              ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def cb(h, hdc, r, lp):
        mi = MONITORINFO(); mi.cbSize = ctypes.sizeof(mi)
        ctypes.windll.user32.GetMonitorInfoW(h, ctypes.byref(mi))
        rc = mi.rcMonitor
        res.append(dict(x=rc.left, y=rc.top, w=rc.right - rc.left,
                        h=rc.bottom - rc.top, principal=bool(mi.dwFlags & 1)))
        return 1
    ctypes.windll.user32.EnumDisplayMonitors(None, None, PROC(cb), 0)
    return res

# ---------- 4) SendInput absoluto sobre escritorio virtual ----------
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]
class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("_pad", ctypes.c_byte * 32)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

MOVE, ABSOLUTE, VIRTUALDESK = 0x0001, 0x8000, 0x4000
def mover_a(x, y):
    vx, vy, vw, vh = escritorio_virtual()
    nx = int(round((x - vx) * 65535 / max(vw - 1, 1)))
    ny = int(round((y - vy) * 65535 / max(vh - 1, 1)))
    i = INPUT(type=0); i.u.mi = MOUSEINPUT(nx, ny, 0, MOVE | ABSOLUTE | VIRTUALDESK, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))

# ---------- 5) Mapeo region activa -> monitor (con espejo) ----------
class Mapeo:
    """Region activa en coordenadas normalizadas de la camara (0..1).
    Se ajusta al aspecto del monitor para que un circulo con la mano sea un circulo."""
    def __init__(s, mon, ancho_region=0.60, cx=0.5, cy=0.45, aspecto_cam=640/480, espejo=True):
        s.mon, s.espejo = mon, espejo
        aspecto_mon = mon["w"] / mon["h"]
        s.rw = ancho_region
        s.rh = ancho_region * aspecto_cam / aspecto_mon  # alto en unidades normalizadas
        s.x0, s.y0 = cx - s.rw / 2, cy - s.rh / 2
    def a_pantalla(s, nx, ny):
        if s.espejo: nx = 1.0 - nx          # si NO volteo el cuadro con cv2.flip
        u = min(max((nx - s.x0) / s.rw, 0.0), 1.0)
        v = min(max((ny - s.y0) / s.rh, 0.0), 1.0)
        m = s.mon
        return m["x"] + u * (m["w"] - 1), m["y"] + v * (m["h"] - 1)

# ---------- 6) Puntero: filtro + zona muerta + congelar al pellizcar ----------
class Puntero:
    def __init__(s, mapeo, mincutoff=1.0, beta=0.007, dcutoff=1.0,
                 zona_muerta_px=1.5, rebobinar_s=0.10, umbral_arrastre_px=14):
        s.map = mapeo
        s.fx, s.fy = OneEuro(mincutoff, beta, dcutoff), OneEuro(mincutoff, beta, dcutoff)
        s.zm, s.rebobinar, s.umbral = zona_muerta_px, rebobinar_s, umbral_arrastre_px
        s.hist = deque(maxlen=12)      # (t, x, y) ~400 ms a 30 fps
        s.ult = None                   # ultima posicion enviada
        s.congelado = None             # punto anclado mientras se pellizca
        s.arrastrando = False
    def reset(s):  # al perder la mano o pausar
        s.fx.reset(); s.fy.reset(); s.hist.clear(); s.congelado = None; s.arrastrando = False
    def actualizar(s, nx, ny, t, pellizco):
        x, y = s.map.a_pantalla(nx, ny)
        x, y = s.fx(x, t), s.fy(y, t)
        s.hist.append((t, x, y))
        if pellizco:
            if s.congelado is None:          # inicio del pellizco: rebobinar ~100 ms
                obj = t - s.rebobinar
                px, py = next(((hx, hy) for ht, hx, hy in s.hist if ht >= obj), (x, y))
                s.congelado = (px, py)
                s.arrastrando = False
            cx, cy = s.congelado
            if not s.arrastrando and math.hypot(x - cx, y - cy) < s.umbral:
                return s._enviar(cx, cy)     # clic quieto: el punto no se mueve
            s.arrastrando = True             # paso el umbral: es arrastre
            # sin salto: desplazar relativo al ancla
            return s._enviar(x, y)
        s.congelado = None; s.arrastrando = False
        return s._enviar(x, y)
    def _enviar(s, x, y):
        if s.ult is not None and math.hypot(x - s.ult[0], y - s.ult[1]) < s.zm:
            return s.ult
        s.ult = (x, y); mover_a(int(round(x)), int(round(y)))
        return s.ult

# ---------- 7) Pellizco con histeresis normalizado por tamano de mano ----------
class DetectorPellizco:
    def __init__(s, cerrar=0.28, abrir=0.42, cuadros_min=2):
        s.cerrar, s.abrir, s.n, s.cont, s.activo = cerrar, abrir, cuadros_min, 0, False
    def __call__(s, lm):  # lm: hand_landmarks.landmark de mediapipe
        d = math.dist((lm[4].x, lm[4].y), (lm[8].x, lm[8].y))
        escala = math.dist((lm[0].x, lm[0].y), (lm[9].x, lm[9].y)) or 1e-6
        r = d / escala
        if not s.activo:
            s.cont = s.cont + 1 if r < s.cerrar else 0
            if s.cont >= s.n: s.activo, s.cont = True, 0
        elif r > s.abrir:
            s.activo = False
        return s.activo, r

if __name__ == "__main__":
    print("DPI:", activar_dpi())
    print("Escritorio virtual:", escritorio_virtual())
    print("Monitores:", monitores())
    # prueba del filtro con senal ruidosa a 30 fps (sin mover el raton)
    import random
    f = OneEuro(1.0, 0.007, 1.0); t = 0.0; err_raw = err_f = 0.0
    for k in range(300):
        t += 1/30; real = 960.0; med = real + random.gauss(0, 6)
        err_raw += abs(med - real); err_f += abs(f(med, t) - real)
    print("Temblor quieto  crudo %.2f px  filtrado %.2f px" % (err_raw/300, err_f/300))
    f = OneEuro(1.0, 0.007, 1.0); t = 0.0; lag = []
    for k in range(60):
        t += 1/30; real = 2000.0 * t; lag.append(real - f(real + random.gauss(0, 6), t))
    print("Retraso a 2000 px/s: %.1f px (~%.0f ms)" % (sum(lag[30:])/30, sum(lag[30:])/30/2000*1000))
