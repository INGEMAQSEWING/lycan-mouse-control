import sys, time, threading, ctypes
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import winput as w

print("python bits", ctypes.sizeof(ctypes.c_void_p) * 8, "sizeof(INPUT)", ctypes.sizeof(w.INPUT))
print("dpi:", w.set_dpi_awareness())
print("virtual:", w.virtual_screen())
print("monitors:", w.monitors())
print("elevated self:", w.is_elevated(), "foreground elevated:", w.foreground_is_elevated())
print("swap buttons:", w.Injector().swapped)

# 1) exactitud de to_absolute en todos los pixeles de borde
vx, vy, vw, vh = w.virtual_screen()
inj = w.Injector()
orig = w.cursor_pos()
errs = []
tests = [(vx, vy), (vx + vw - 1, vy + vh - 1), (vx + vw // 2, vy + vh // 2), (vx + 1, vy + 1),
         (vx + 123, vy + 457), (vx + vw - 2, vy + 3)]
for (x, y) in tests:
    inj.move_to(x, y); time.sleep(0.03)
    got = w.cursor_pos()
    if got != (x, y):
        errs.append(((x, y), got))
inj.move_to(*orig)
print("move tests:", len(tests), "errores:", errs, "restaurado:", w.cursor_pos() == orig)

# barrido completo de la formula (sin mover el raton): inversa que usa Windows
bad = 0
for x in range(vx, vx + vw):
    nx, _ = w.to_absolute(x, vy)
    back = vx + (nx * vw) // 65536
    if back != x:
        bad += 1
print("barrido formula X: pixeles mal mapeados =", bad, "de", vw)

# 2) Shift sostenido
GetAsync = w.user32.GetAsyncKeyState
inj.key_down(w.VK_LSHIFT); time.sleep(0.02)
s_down = bool(GetAsync(w.VK_SHIFT) & 0x8000)
inj.release_all(); time.sleep(0.02)
s_up = bool(GetAsync(w.VK_SHIFT) & 0x8000)
print("shift sostenido:", s_down, "tras release_all:", s_up, "held:", inj.held_keys)

# 3) boton del medio sostenido + release_all (en el escritorio/ventana actual)
inj.down("middle"); time.sleep(0.02)
m_down = bool(GetAsync(0x04) & 0x8000)
inj.release_all(); time.sleep(0.02)
m_up = bool(GetAsync(0x04) & 0x8000)
print("medio sostenido:", m_down, "tras release_all:", m_up)

# 4) atajo global: Ctrl+Alt+Shift+F12, disparado con SendInput
hit = threading.Event()
VK_F12 = 0x7B
ht = w.HotkeyThread([(w.MOD_CONTROL | w.MOD_ALT | w.MOD_SHIFT, VK_F12, hit.set)])
ht.start(); ht.ready.wait(2)
print("hotkey fallidos:", ht.failed)
t0 = time.perf_counter()
w._send(w._key(w.VK_LCONTROL), w._key(0xA4), w._key(w.VK_LSHIFT), w._key(VK_F12),
        w._key(VK_F12, up=True), w._key(w.VK_LSHIFT, up=True), w._key(0xA4, up=True),
        w._key(w.VK_LCONTROL, up=True))
print("hotkey recibido:", hit.wait(2), "ms:", round((time.perf_counter() - t0) * 1000, 1))
# registro duplicado -> error 1409
ht2 = w.HotkeyThread([(w.MOD_CONTROL | w.MOD_ALT | w.MOD_SHIFT, VK_F12, lambda: None)])
ht2.start(); ht2.ready.wait(2)
print("registro duplicado:", ht2.failed)
ht.stop(); ht2.stop(); ht.join(2); ht2.join(2)
print("hilos terminados:", not ht.is_alive(), not ht2.is_alive())

# 5) tiempo de SendInput
t0 = time.perf_counter()
p = w.cursor_pos()
for _ in range(200):
    inj.move_to(*p)
print("SendInput move us/llamada:", round((time.perf_counter() - t0) / 200 * 1e6, 1))
