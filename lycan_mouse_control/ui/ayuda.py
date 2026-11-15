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
    # 1.0.2 paquete A (en 3D se ven también: las filas de 3D se suman a estas)
    ("pellizco_anular", "ch_anular"), ("pellizco_menique", "ch_menique"),
    # 1.0.2 paquete C
    ("abierta", "ch_palma"), ("abierta", "ch_barrido"),
]
FILAS_3D = [("puno", "ch_girar"), ("abierta", "as_soltar"), ("puno", "ch_puno_3d")]
# 1.0.2 paquete B: girar con un puño y lanzar (se muestran según orbita.girar y orbita.inercia)
FILA_UN_PUNO = ("puno", "ch_girar_un_puno")
FILA_LANZAR = ("abierta", "ch_lanzar")
TEMAS = ["tema_complemento", "tema_postura", "tema_luz", "tema_larga", "tema_admin", "tema_freecad",
         "tema_presionado", "tema_tecla", "ch_golpe", "ch_mano_baja", "ch_atajos"]


def filas_3d(girar: str = "un_puno", inercia: bool = False) -> list:
    """Filas de 3D según la opción de girar: un puño, dos puños (1.0.1) o los dos."""
    out = []
    if girar != "dos_punos":
        out.append(FILA_UN_PUNO)
        if inercia:
            out.append(FILA_LANZAR)
    if girar != "un_puno":
        out.append(FILAS_3D[0])
    return out + FILAS_3D[1:]


def dibujar_mano(canvas: tk.Canvas, postura: str, x: int, y: int, tam: int = 48, color="#9BC1FF", lado="Right"):
    for (x1, y1), (x2, y2) in dibujo_postura(postura, tam, lado):
        canvas.create_line(x + x1, y + y1, x + x2, y + y2, fill=color, width=2, capstyle="round")


def texto_atajos(atajos: dict | None = None) -> str:
    """La línea de atajos se arma con los atajos configurados (no escritos a mano)."""
    from ..config import FABRICA
    fab = FABRICA["atajos"]
    a = dict(fab)
    for k, v in (atajos or {}).items():
        if isinstance(v, str) and v.strip():
            a[k] = v
    return t("ch_atajos", **{k: a.get(k, fab.get(k, "")) for k in ("pausar", "salir", "ventana", "modo",
                                                                    "dibujo_fino")})


class VentanaAyuda:
    def __init__(self, root, modo: str = "2D", zoom_una_mano: bool = False, atajos: dict | None = None,
                 girar: str = "un_puno", inercia: bool = False):
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
        # La rueda se engancha SOLO a esta ventana (bind_all la dejaba enganchada a toda la app y,
        # al cerrar la ayuda, cada giro de rueda en otra ventana daba error).
        def rueda(e):
            try:
                lienzo.yview_scroll(int(-e.delta / 120), "units")
            except tk.TclError:
                pass
        self.win.bind("<MouseWheel>", rueda)
        self.lienzo = lienzo

        filas = list(FILAS_2D)
        if modo == "3D":
            filas = [(p, "ch_desplazar_3D" if c == "ch_desplazar" else c) for p, c in filas]
        if zoom_una_mano:
            filas.append(("pellizco_corazon", "ch_zoom1"))
        if modo == "3D":
            filas += filas_3d(girar, inercia)
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
            txt = texto_atajos(atajos) if clave == "ch_atajos" else t(clave)
            tk.Label(cont, text="• " + txt, bg=FONDO, fg=TEXTO_SUAVE, font=(LETRA, 9), wraplength=500,
                     justify="left").pack(anchor="w", pady=2)
        tk.Button(cont, text="Cerrar", command=self.win.destroy).pack(pady=10)
