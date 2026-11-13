import sys, time, ctypes
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import winput as w
w.set_dpi_awareness()
print("DPI sistema:", w.user32.GetDpiForSystem(), "(96 = 100 %)")
import tkinter as tk

ev = []
root = tk.Tk(); root.geometry("400x300+200+200"); root.attributes("-topmost", True)
c = tk.Canvas(root, bg="white"); c.pack(fill="both", expand=True)
c.bind("<MouseWheel>", lambda e: ev.append(("wheel", e.delta)))
for b in (1, 2, 3):
    c.bind(f"<ButtonPress-{b}>", lambda e, b=b: ev.append(("down", b)))
    c.bind(f"<ButtonRelease-{b}>", lambda e, b=b: ev.append(("up", b)))
c.bind("<B2-Motion>", lambda e: ev.append(("drag2", e.x, e.y)) if len([x for x in ev if x[0]=="drag2"]) < 2 else None)
c.bind("<Shift-ButtonPress-2>", lambda e: ev.append(("shift+down", 2)))

inj = w.Injector()
orig = w.cursor_pos()

def run():
    root.update()
    x, y = c.winfo_rootx() + 200, c.winfo_rooty() + 150
    inj.move_to(x, y); time.sleep(0.05); root.update()
    inj.click("left"); inj.click("right"); root.update(); time.sleep(0.05)
    inj.wheel(1); inj.wheel(-1); root.update(); time.sleep(0.05)
    for _ in range(8):
        inj.wheel_smooth(0.25, min_step=30)  # rueda fina
    root.update(); time.sleep(0.05)
    inj.begin_orbit()
    for i in range(5):
        inj.move_to(x + i * 5, y); time.sleep(0.01); root.update()
    inj.end_drag(); root.update()
    inj.begin_pan(); root.update(); inj.end_drag(); root.update()
    time.sleep(0.1); root.update()
    inj.move_to(*orig)
    print(ev)
    root.destroy()

root.after(300, run)
root.mainloop()
