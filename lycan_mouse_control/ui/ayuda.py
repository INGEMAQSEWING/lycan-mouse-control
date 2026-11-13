"""Ayuda: chuleta de señas del modo actual con dibujos generados desde manos sintéticas
(sin archivos externos) y temas fijos (postura, luz, administrador, FreeCAD, "si algo quedó presionado")."""
from __future__ import annotations

import tkinter as tk

from ..sintetico import dibujo_postura
from .comun import FONDO, FONDO_2, LETRA, TEXTO, TEXTO_SUAVE
from .textos import t

FILAS_2D = [
    ("juntos", "ch_activar"), ("juntos", "ch_pausar"), ("apuntar", "ch_mover"), ("pellizco", "ch_clic"),
    ("pellizco", "ch_arrastrar"), ("puno", "ch_derecho"), ("pellizco", "ch_zoom"), ("pellizco", "ch_desplazar"),
]
FILAS_3D = [("puno", "ch_girar"), ("abierta", "as_soltar")]
TEMAS = ["tema_complemento", "tema_postura", "tema_luz", "tema_larga", "tema_admin", "tema_freecad",
         "tema_presionado", "ch_atajos"]


def dibujar_mano(canvas: tk.Canvas, postura: str, x: int, y: int, tam: int = 48, color="#9BC1FF", lado="Right"):
    for (x1, y1), (x2, y2) in dibujo_postura(postura, tam, lado):
        canvas.create_line(x + x1, y + y1, x + x2, y + y2, fill=color, width=2, capstyle="round")


class VentanaAyuda:
    def __init__(self, root, modo: str = "2D", zoom_una_mano: bool = False):
        self.win = tk.Toplevel(root)
        self.win.title("Ayuda — Lycan Mouse Control")
        self.win.configure(bg=FONDO)
        self.win.attributes("-topmost", True)
        self.win.geometry("560x640")
        tk.Label(self.win, text=t("chuleta_titulo", modo=t("modo_" + modo)), bg=FONDO, fg=TEXTO,
                 font=(LETRA, 14, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        lienzo = tk.Canvas(self.win, bg=FONDO, highlightthickness=0)
        barra = tk.Scrollbar(self.win, orient="vertical", command=lienzo.yview)
        cont = tk.Frame(lienzo, bg=FONDO)
        cont.bind("<Configure>", lambda e: lienzo.configure(scrollregion=lienzo.bbox("all")))
        lienzo.create_window((0, 0), window=cont, anchor="nw")
        lienzo.configure(yscrollcommand=barra.set)
        lienzo.pack(side="left", fill="both", expand=True, padx=(10, 0))
        barra.pack(side="right", fill="y")
        lienzo.bind_all("<MouseWheel>", lambda e: lienzo.yview_scroll(int(-e.delta / 120), "units"))

        filas = list(FILAS_2D)
        if zoom_una_mano:
            filas.append(("pellizco_corazon", "ch_zoom1"))
        if modo == "3D":
            filas += FILAS_3D
        for postura, clave in filas:
            f = tk.Frame(cont, bg=FONDO_2)
            f.pack(fill="x", pady=3, padx=2)
            c = tk.Canvas(f, width=56, height=56, bg=FONDO_2, highlightthickness=0)
            c.pack(side="left", padx=6, pady=4)
            dibujar_mano(c, postura, 4, 4)
            tk.Label(f, text=t(clave), bg=FONDO_2, fg=TEXTO, font=(LETRA, 10), wraplength=420,
                     justify="left").pack(side="left", padx=6)
        tk.Label(cont, text="Consejos", bg=FONDO, fg=TEXTO, font=(LETRA, 12, "bold")).pack(anchor="w", pady=(10, 2))
        for clave in TEMAS:
            tk.Label(cont, text="• " + t(clave), bg=FONDO, fg=TEXTO_SUAVE, font=(LETRA, 9), wraplength=500,
                     justify="left").pack(anchor="w", pady=2)
        tk.Button(cont, text="Cerrar", command=self.win.destroy).pack(pady=10)
