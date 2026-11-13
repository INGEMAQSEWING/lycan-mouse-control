"""Ventana principal (siempre visible, abajo a la derecha). Solo pinta lo que deja el motor."""
from __future__ import annotations

import logging
import queue
import time
import tkinter as tk

import numpy as np

from .. import constantes as K
from ..acciones import Aviso, Sonido
from .comun import FONDO, FONDO_2, LETRA, TEXTO, TEXTO_SUAVE, Globo, boton, poner_icono
from .textos import t, texto_aviso

log = logging.getLogger("lycan")

ANCHO, ALTO = 336, 356
REFRESCO_MS = 66


class VentanaPrincipal:
    def __init__(self, root: tk.Tk, app):
        self.root = root
        self.app = app
        self.mini = False
        self._ultima_vista = None
        self._ult_sena = ""
        self._ult_sena_t = 0.0
        self._aviso_hasta = 0.0
        self._diag = False
        self._foto = None
        self._foto_mini = None
        self._arr_x = self._arr_y = 0
        self._construir()
        self._posicionar()
        self.root.after(REFRESCO_MS, self._refrescar)

    # ------------------------------------------------------------ construcción
    def _construir(self):
        r = self.root
        r.title(K.NOMBRE_APP)
        poner_icono(r)
        r.configure(bg=K.COLORES_ESTADO[K.PAUSA])
        r.resizable(False, False)
        r.attributes("-topmost", True)
        try:
            r.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        r.attributes("-alpha", float(self.app.cfg.datos["comodidad"].get("opacidad", 0.94)))
        self.marco = tk.Frame(r, bg=FONDO)
        self.marco.pack(fill="both", expand=True, padx=3, pady=3)

        # 1. barra de estado
        self.barra = tk.Frame(self.marco, bg=FONDO, height=28)
        self.barra.pack(fill="x")
        self.lbl_estado = tk.Label(self.barra, text=t("estado_PAUSA"), bg=FONDO, fg=K.COLORES_ESTADO[K.PAUSA],
                                   font=(LETRA, 11, "bold"), anchor="w")
        self.lbl_estado.pack(side="left", padx=(6, 4))
        self.lbl_modo = tk.Label(self.barra, text="2D", bg="#3A4250", fg=TEXTO, font=(LETRA, 9, "bold"), padx=5)
        self.lbl_modo.pack(side="left", padx=2)
        self.lbl_perfil = tk.Label(self.barra, text="", bg=FONDO, fg=TEXTO_SUAVE, font=(LETRA, 9), anchor="e")
        self.lbl_perfil.pack(side="right", padx=6)
        for w in (self.barra, self.lbl_estado, self.lbl_perfil):
            w.bind("<ButtonPress-1>", self._arrastre_ini)
            w.bind("<B1-Motion>", self._arrastre)

        # 2. video
        from PIL import Image, ImageTk
        self._Image = Image
        self._foto = ImageTk.PhotoImage(Image.new("RGB", (320, 240), (20, 22, 26)))
        self._foto_mini = ImageTk.PhotoImage(Image.new("RGB", (160, 120), (20, 22, 26)))
        self.video = tk.Label(self.marco, image=self._foto, bg="black", bd=0)
        self.video.pack(padx=5)
        self.video.bind("<Double-Button-1>", lambda e: self.alternar_mini())
        self.lbl_fps = tk.Label(self.video, text="", bg="black", fg="#DDD", font=(LETRA, 8), cursor="hand2")
        self.lbl_fps.place(relx=1.0, rely=1.0, anchor="se")
        self.lbl_fps.bind("<Button-1>", lambda e: self._alternar_diag())

        # 3. franja de la seña / avisos
        self.franja = tk.Frame(self.marco, bg=FONDO, height=44)
        self.franja.pack(fill="x")
        self.franja.pack_propagate(False)
        self.lbl_sena = tk.Label(self.franja, text="", bg=FONDO, fg=TEXTO, font=(LETRA, 20, "bold"))
        self.lbl_sena.pack(expand=True)
        self.lbl_aviso = tk.Label(self.franja, text="", bg="#3B2F10", fg="#FFE6A6", font=(LETRA, 9),
                                  wraplength=310, justify="center")

        # diagnóstico (oculto)
        self.lbl_diag = tk.Label(self.marco, text="", bg=FONDO_2, fg=TEXTO_SUAVE, font=("Consolas", 8),
                                 justify="left", anchor="w")

        # 4. botones
        self.botones = tk.Frame(self.marco, bg=FONDO)
        self.botones.pack(fill="x", pady=(0, 4))
        self.b_pausa = boton(self.botones, t("btn_activar"), lambda: self.app.orden("pausar"), ancho=9)
        self.b_pausa.pack(side="left", padx=(5, 2))
        self.b_modo = boton(self.botones, t("btn_modo"), lambda: self.app.orden("modo"), ancho=5)
        self.b_modo.pack(side="left", padx=2)
        Globo(self.b_modo, "Cambiar entre Mouse Control 2D y 3D (Ctrl+Alt+D). Al cambiar queda en pausa.")
        b_op = boton(self.botones, t("btn_opciones"), self.app.abrir_opciones, ancho=3)
        b_op.pack(side="left", padx=2)
        Globo(b_op, "Opciones: puntero, señas, atajos y comodidad.")
        self.b_ayuda = boton(self.botones, t("btn_ayuda"), self._menu_ayuda, ancho=3)
        self.b_ayuda.pack(side="left", padx=2)
        b_mini = boton(self.botones, t("btn_mini"), self.alternar_mini, ancho=3)
        b_mini.pack(side="left", padx=2)
        Globo(b_mini, "Ventana pequeña. Doble clic sobre el video para volver.")
        b_salir = boton(self.botones, "✕", self.app.salir_seguro, ancho=3)
        b_salir.pack(side="right", padx=(2, 5))
        Globo(b_salir, t("aviso_cerrar"))

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label=t("menu_chuleta"), command=self.app.abrir_ayuda)
        self.menu.add_command(label=t("menu_practicar"), command=self.app.abrir_asistente)
        self.menu.add_command(label=t("menu_opciones"), command=self.app.abrir_opciones)
        self.menu.add_separator()
        self.menu.add_command(label=t("menu_registros"), command=self.app.abrir_registros)
        self.menu.add_command(label=t("menu_admin"), command=self.app.reiniciar_admin)
        self.menu.add_separator()
        self.menu.add_command(label=t("menu_salir"), command=self.app.salir_seguro)
        self.root.protocol("WM_DELETE_WINDOW", self.app.salir_seguro)

    def _menu_ayuda(self):
        x = self.b_ayuda.winfo_rootx()
        y = self.b_ayuda.winfo_rooty() + self.b_ayuda.winfo_height()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def _posicionar(self):
        r = self.root
        r.update_idletasks()
        v = self.app.cfg.datos.get("ventana") or {}
        x, y = v.get("x"), v.get("y")
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x < sw - 50 and 0 <= y < sh - 50):
            x = sw - ANCHO - 16
            y = sh - ALTO - 16 - 40   # deja libre la barra de tareas
        r.geometry(f"{ANCHO}x{ALTO}+{x}+{y}")
        if v.get("mini"):
            self.alternar_mini()

    def aplicar_no_activar(self):
        """WS_EX_NOACTIVATE: hacer clic aquí no le quita el foco al programa de dibujo."""
        try:
            from ..sistema import ventanas_win as vw
            self.hwnd = vw.raiz(self.root.winfo_id())
            vw.no_activar(self.hwnd)
        except Exception:  # noqa: BLE001
            self.hwnd = None

    # ------------------------------------------------------------ interacción
    def _arrastre_ini(self, e):
        self._arr_x, self._arr_y = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _arrastre(self, e):
        self.root.geometry(f"+{e.x_root - self._arr_x}+{e.y_root - self._arr_y}")

    def _alternar_diag(self):
        self._diag = not self._diag
        if self._diag:
            self.lbl_diag.pack(fill="x", padx=5, before=self.botones)
            self.root.geometry(f"{ANCHO}x{ALTO + 70}")
        else:
            self.lbl_diag.pack_forget()
            self.root.geometry(f"{ANCHO}x{ALTO}")

    def alternar_mini(self):
        self.mini = not self.mini
        if self.mini:
            self.barra.pack_forget()
            self.franja.pack_forget()
            self.botones.pack_forget()
            self.lbl_diag.pack_forget()
            self.video.configure(image=self._foto_mini)
            self.root.geometry("172x132")
        else:
            self.video.pack_forget()
            self.barra.pack(fill="x")
            self.video.configure(image=self._foto)
            self.video.pack(padx=5)
            self.franja.pack(fill="x")
            self.botones.pack(fill="x", pady=(0, 4))
            self.root.geometry(f"{ANCHO}x{ALTO}")
        self.app.cfg.datos["ventana"]["mini"] = self.mini

    def mostrar_aviso(self, texto: str, segundos: float = 5.0):
        if not texto:
            return
        self.lbl_aviso.configure(text=texto)
        self.lbl_aviso.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._aviso_hasta = time.monotonic() + segundos
        log.info("Aviso: %s", texto)

    # ------------------------------------------------------------ refresco
    def _refrescar(self):
        try:
            self._atender_atajos()
            self._atender_avisos()
            vista = None
            try:
                vista = self.app.motor.vistas.get_nowait()
            except queue.Empty:
                pass
            if vista is not None:
                self.app.ultima_vista = vista
                self._pintar(vista)
                self.app.al_pintar(vista)
            if self._aviso_hasta and time.monotonic() > self._aviso_hasta:
                self._aviso_hasta = 0.0
                self.lbl_aviso.place_forget()
            self._actualizar_rect_propio()
        except Exception:  # noqa: BLE001
            log.exception("Error al refrescar la ventana")
        finally:
            if not self.app.cerrando:
                self.root.after(REFRESCO_MS, self._refrescar)

    def _actualizar_rect_propio(self):
        try:
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            w, h = self.root.winfo_width(), self.root.winfo_height()
            if self.root.state() == "withdrawn":
                self.app.salida_actual().rect_propio = None
            else:
                self.app.salida_actual().rect_propio = (x - 3, y - 30, x + w + 3, y + h + 3)
        except tk.TclError:
            pass

    def _atender_atajos(self):
        while True:
            try:
                nombre = self.app.cola_atajos.get_nowait()
            except queue.Empty:
                return
            if nombre == "salir":
                self.app.salir_seguro()
                return
            if nombre == "ventana":
                self.app.alternar_ventana()
            elif nombre == "pausar":
                self.app.orden("pausar")
            elif nombre == "modo":
                self.app.orden("modo")
            elif nombre == "dibujo_fino":
                self.app.orden("dibujo_fino")

    def _atender_avisos(self):
        for _ in range(20):
            try:
                a = self.app.motor.avisos.get_nowait()
            except queue.Empty:
                return
            if isinstance(a, Sonido):
                self.app.sonidos.tocar(a.nombre)
            elif isinstance(a, Aviso):
                if a.clave == "fatal":
                    self.mostrar_aviso(t("aviso_fatal"), 10)
                    self.root.after(4000, self.app.salir_seguro)
                elif a.clave in ("desbloqueado",):
                    self.mostrar_aviso(texto_aviso(a), 3)
                else:
                    self.mostrar_aviso(texto_aviso(a))
                self.app.indicador_aviso(a)

    def _pintar(self, v):
        self._ultima_vista = v
        color = K.COLORES_ESTADO.get(v.estado, "#8A8F98")
        self.root.configure(bg=color)
        texto_estado = t("estado_" + v.estado)
        if v.simulada:
            texto_estado += "  (ensayo)"
        self.lbl_estado.configure(text=texto_estado, fg=color)
        self.lbl_modo.configure(text=v.modo)
        self.lbl_perfil.configure(text=v.perfil)
        self.b_pausa.configure(text=t("btn_pausar") if v.estado not in (K.PAUSA, K.BLOQUEADO) else t("btn_activar"))
        if v.imagen is not None:
            img = self._Image.fromarray(np.ascontiguousarray(v.imagen))
            if self.mini:
                self._foto_mini.paste(img.resize((160, 120)))
            else:
                self._foto.paste(img)
        self.lbl_fps.configure(text=f"{v.fps:.0f} c/s" if v.fps else "")
        # franja de la seña
        ahora = time.monotonic()
        if v.etiqueta:
            texto, gris = t("sena_" + v.etiqueta), False
        elif v.sena and v.sena not in ("NINGUNA",) and v.estado != K.PAUSA:
            texto, gris = t("sena_" + v.sena), False
        elif v.estado == K.PAUSA and v.sena == "ACTIVAR":
            texto, gris = t("sena_sostenga"), False
        else:
            texto, gris = "", True
        if texto:
            self._ult_sena, self._ult_sena_t = texto, ahora
            self.lbl_sena.configure(text=texto, fg=TEXTO)
        elif ahora - self._ult_sena_t < 0.8:
            self.lbl_sena.configure(text=self._ult_sena, fg="#6B7280")
        else:
            ayuda = t("ayuda_" + v.estado)
            self.lbl_sena.configure(text=ayuda, fg=TEXTO_SUAVE, font=(LETRA, 9), wraplength=310)
            return self._diag_texto(v)
        self.lbl_sena.configure(font=(LETRA, 20, "bold"), wraplength=0)
        self._diag_texto(v)

    def _diag_texto(self, v):
        if not self._diag:
            return
        m = v.medidas or {}
        d = m.get("doblez", {})
        txt = (f"seña {v.sena or '-'}  manos {v.manos}  {v.sub}\n"
               f"p {m.get('p', float('nan')):.2f}  s {m.get('s', float('nan')):.2f}  "
               f"a {m.get('a', float('nan')):.0f}°  retraso {v.latencia_ms:.0f} ms\n"
               f"doblez i{d.get('indice', 0):.0f} c{d.get('corazon', 0):.0f} "
               f"a{d.get('anular', 0):.0f} m{d.get('menique', 0):.0f}\n"
               f"última acción: {v.ultima_accion}")
        self.lbl_diag.configure(text=txt)

    def posicion(self):
        return self.root.winfo_x(), self.root.winfo_y()
