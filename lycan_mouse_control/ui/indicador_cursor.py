"""Indicador junto al cursor: 1-2 palabras ("CLIC", "ARRASTRE", "GIRAR", "PAUSADO") durante
700 ms después de cada cambio. Los clics lo atraviesan. En el modo ensayo (--simular) además
dibuja un anillo donde estaría el puntero, para ver lo que haría el programa.
"""
from __future__ import annotations

import time
import tkinter as tk

from .. import constantes as K
from .comun import LETRA

TRANSPARENTE = "#010101"

PALABRAS = {
    "clic_izquierdo": "CLIC", "arrastre_fin": "SOLTAR", "clic_derecho": "CLIC DERECHO",
    "acercar": "ACERCAR", "alejar": "ALEJAR", "girar": "GIRAR", "desplazar": "MOVER",
    "activado": "ACTIVO", "pausado": "PAUSADO", "soltar": "SOLTAR",
    "pasando": "PÁGINA", "barrido_der": "SIGUIENTE", "barrido_izq": "ANTERIOR",    # 1.0.2 paquete C
}
PALABRAS_ESTADO = {K.ARRASTRANDO: "ARRASTRE", K.GIRANDO_3D: "GIRAR", K.DESPLAZANDO: "MOVER",
                   K.PASANDO_PAGINA: "PÁGINA",
                   K.PAUSA: "PAUSADO", K.SIN_MANO: "SIN MANO"}


class Indicador:
    def __init__(self, root: tk.Tk, obtener_cursor, simulado: bool = False):
        self.root = root
        self.obtener_cursor = obtener_cursor
        self.simulado = simulado
        self.activo = True
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENTE)
        except tk.TclError:
            pass
        self.win.configure(bg=TRANSPARENTE)
        self.canvas = tk.Canvas(self.win, width=200, height=60, bg=TRANSPARENTE, highlightthickness=0)
        self.canvas.pack()
        self.win.withdraw()
        self._texto = ""
        self._hasta = 0.0
        self._ult_estado = None
        self._ult_etiqueta = ""
        self._hecho_atravesable = False

    def _atravesable(self):
        if self._hecho_atravesable:
            return
        try:
            from ..sistema import ventanas_win as vw
            vw.atravesable(vw.raiz(self.win.winfo_id()))
            self._hecho_atravesable = True
        except Exception:  # noqa: BLE001
            pass

    def actualizar(self, vista):
        if not self.activo or vista is None:
            self.win.withdraw()
            return
        ahora = time.monotonic()
        palabra = None
        if vista.etiqueta and vista.etiqueta != self._ult_etiqueta:
            palabra = PALABRAS.get(vista.etiqueta)
        if vista.estado != self._ult_estado:
            palabra = palabra or PALABRAS_ESTADO.get(vista.estado)
        self._ult_estado = vista.estado
        self._ult_etiqueta = vista.etiqueta
        if palabra:
            self._texto = palabra
            self._hasta = ahora + 0.7
            self._color = K.COLORES_ESTADO.get(vista.estado, "#2F6FEB")
        mostrar_texto = ahora < self._hasta
        anillo = self.simulado and vista.cursor is not None and vista.estado != K.PAUSA
        if not mostrar_texto and not anillo:
            self.win.withdraw()
            return
        try:
            x, y = (vista.cursor if self.simulado and vista.cursor else self.obtener_cursor())
        except Exception:  # noqa: BLE001
            self.win.withdraw()
            return
        c = self.canvas
        c.delete("all")
        if anillo:
            c.create_oval(2, 2, 22, 22, outline=K.COLORES_ESTADO.get(vista.estado, "#FFFFFF"), width=3)
            c.create_oval(10, 10, 14, 14, fill="#FFFFFF", outline="")
        if mostrar_texto:
            ancho = 10 + 9 * len(self._texto)
            c.create_rectangle(24, 24, 24 + ancho, 46, fill=self._color, outline="")
            c.create_text(29, 35, text=self._texto, anchor="w", fill="white", font=(LETRA, 10, "bold"))
        self.win.geometry(f"+{int(x) - 12}+{int(y) - 12}")
        self.win.deiconify()
        self._atravesable()

    def destruir(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
