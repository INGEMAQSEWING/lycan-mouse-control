"""Piezas comunes de la interfaz: colores, letras y el globo de ayuda "?"."""
from __future__ import annotations

import os
import sys
import tkinter as tk

FONDO = "#15181D"
FONDO_2 = "#1F242B"
TEXTO = "#F2F4F7"
TEXTO_SUAVE = "#A9B0BA"
ACENTO = "#2F6FEB"
LETRA = "Segoe UI"


def ruta_recurso(nombre: str) -> str:
    """Ruta de un archivo de recursos/ (funciona en desarrollo y dentro del .exe)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "recursos", nombre)


def poner_icono(ventana):
    ruta = ruta_recurso("lycan-mouse.ico")
    if os.path.exists(ruta):
        try:
            ventana.iconbitmap(ruta)
        except tk.TclError:
            pass


def boton(padre, texto, comando, ancho=None, **kw):
    b = tk.Button(padre, text=texto, command=comando, bg=FONDO_2, fg=TEXTO, activebackground="#2B323B",
                  activeforeground=TEXTO, relief="flat", bd=0, padx=8, pady=3, font=(LETRA, 10),
                  cursor="hand2", **kw)
    if ancho:
        b.configure(width=ancho)
    return b


class Globo:
    """Globo de ayuda que aparece al pasar o hacer clic sobre un widget (botón "?")."""

    def __init__(self, widget, texto: str, al_clic: bool = False):
        self.widget = widget
        self.texto = texto
        self.tip = None
        if al_clic:
            widget.bind("<Button-1>", self.alternar, add="+")
        else:
            widget.bind("<Enter>", self.mostrar, add="+")
            widget.bind("<Leave>", self.ocultar, add="+")

    def alternar(self, _e=None):
        if self.tip:
            self.ocultar()
        else:
            self.mostrar()

    def mostrar(self, _e=None):
        if self.tip or not self.texto:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self.texto, justify="left", wraplength=300, bg="#FFF8DC", fg="#222",
                 relief="solid", bd=1, font=(LETRA, 9), padx=6, pady=4).pack()
        tw.update_idletasks()
        sw = tw.winfo_screenwidth()
        w = tw.winfo_reqwidth()
        if x + w > sw:
            x = sw - w - 8
        h = tw.winfo_reqheight()
        if y + h > tw.winfo_screenheight():
            y = self.widget.winfo_rooty() - h - 4
        tw.wm_geometry(f"+{x}+{y}")
        tw.after(8000, self.ocultar)

    def ocultar(self, _e=None):
        if self.tip:
            try:
                self.tip.destroy()
            except tk.TclError:
                pass
            self.tip = None


def boton_ayuda(padre, texto: str):
    b = tk.Label(padre, text="?", bg=ACENTO, fg="white", font=(LETRA, 9, "bold"), width=2, cursor="hand2")
    Globo(b, texto, al_clic=True)
    return b
