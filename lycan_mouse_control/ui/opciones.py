"""Opciones (5 pestañas). Los cambios se ven en vivo; "Cancelar" los revierte."""
from __future__ import annotations

import copy
import math
import tkinter as tk
from tkinter import ttk

from .. import perfiles as P
from ..config import FABRICA, por_defecto
from ..senas import UMBRALES_FABRICA
from ..sistema import atajos as A
from .comun import LETRA, boton_ayuda
from .textos import t


def _mapear(v, a0, a1, b0, b1):
    f = (v - a0) / (a1 - a0)
    return b0 + f * (b1 - b0)


class VentanaOpciones:
    def __init__(self, root, app):
        self.app = app
        self.original = copy.deepcopy(app.cfg.datos)
        self.cfg = copy.deepcopy(app.cfg.datos)
        self.win = tk.Toplevel(root)
        self.win.title(t("op_titulo"))
        self.win.geometry("540x500")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.cancelar)
        self._pend = None
        self._vars = []
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._general(self._pestana(nb, "op_general"))
        self._puntero(self._pestana(nb, "op_puntero"))
        self._senas(self._pestana(nb, "op_senas"))
        self._comodidad(self._pestana(nb, "op_comodidad"))
        self._atajos(self._pestana(nb, "op_atajos"))
        abajo = tk.Frame(self.win)
        abajo.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(abajo, text=t("op_practicar"), command=self.practicar).pack(side="left")
        tk.Button(abajo, text=t("op_fabrica"), command=self.fabrica).pack(side="left", padx=6)
        tk.Button(abajo, text=t("op_cancelar"), command=self.cancelar).pack(side="right")
        tk.Button(abajo, text=t("op_guardar"), command=self.guardar).pack(side="right", padx=6)
        self._refrescar_barras()

    # ------------------------------------------------------------ utilidades
    def _pestana(self, nb, clave):
        f = tk.Frame(nb, padx=10, pady=8)
        nb.add(f, text=t(clave))
        return f

    def _fila(self, padre, clave_texto, ayuda=None):
        f = tk.Frame(padre)
        f.pack(fill="x", pady=3)
        tk.Label(f, text=t(clave_texto), font=(LETRA, 10), anchor="w", width=34).pack(side="left")
        if ayuda:
            boton_ayuda(f, ayuda).pack(side="right")
        return f

    def _get(self, ruta):
        d = self.cfg
        for k in ruta[:-1]:
            d = d[k]
        return d[ruta[-1]]

    def _set(self, ruta, valor):
        d = self.cfg
        for k in ruta[:-1]:
            d = d[k]
        d[ruta[-1]] = valor
        self._en_vivo()

    def _check(self, padre, clave, ruta, ayuda=None):
        v = tk.BooleanVar(value=bool(self._get(ruta)))
        f = self._fila(padre, clave, ayuda)
        tk.Checkbutton(f, variable=v, command=lambda: self._set(ruta, bool(v.get()))).pack(side="left")
        self._vars.append(v)
        return v

    def _escala(self, padre, clave, ruta, desde, hasta, ayuda=None, conv=lambda x: x, inv=lambda x: x, paso=1):
        v = tk.DoubleVar(value=inv(self._get(ruta)))
        f = self._fila(padre, clave, ayuda)
        tk.Scale(f, from_=desde, to=hasta, orient="horizontal", variable=v, resolution=paso, length=180,
                 command=lambda _x: self._set(ruta, conv(v.get()))).pack(side="left")
        self._vars.append(v)
        return v

    def _en_vivo(self):
        """Aplica los cambios en vivo (con una pequeña espera para no rearmar a cada movimiento)."""
        if self._pend:
            self.win.after_cancel(self._pend)
        self._pend = self.win.after(400, lambda: self.app.orden("config", copy.deepcopy(self.cfg)))

    # ------------------------------------------------------------ pestañas
    def _general(self, f):
        fila = self._fila(f, "op_modo", "2D para dibujo plano; 3D agrega girar y mover el modelo con dos manos.")
        vm = tk.StringVar(value=self.cfg["modo"])
        for m in ("2D", "3D"):
            tk.Radiobutton(fila, text=m, value=m, variable=vm, command=lambda: self._set(["modo"], vm.get())).pack(side="left")
        fila = self._fila(f, "op_mano", "La mano que mueve el puntero y hace los clics. Si solo se ve una mano, "
                                         "esa manda.")
        vh = tk.StringVar(value=self.cfg["mano_principal"])
        for clave, val in (("as_mano_der", "derecha"), ("as_mano_izq", "izquierda")):
            tk.Radiobutton(fila, text=t(clave), value=val, variable=vh,
                           command=lambda: self._set(["mano_principal"], vh.get())).pack(side="left")
        fila = self._fila(f, "op_camara", "Si tiene varias cámaras, pruebe 0, 1, 2...")
        vc = tk.IntVar(value=self.cfg["camara"]["indice"])
        tk.Spinbox(fila, from_=0, to=3, width=4, textvariable=vc,
                   command=lambda: self._set(["camara", "indice"], int(vc.get()))).pack(side="left")
        fila = self._fila(f, "op_resolucion", "La rápida usa menos el procesador pero es menos precisa.")
        vr = tk.IntVar(value=self.cfg["camara"]["ancho"])

        def poner_res():
            w = int(vr.get())
            self.cfg["camara"]["alto"] = 480 if w == 640 else 240
            self._set(["camara", "ancho"], w)
        tk.Radiobutton(fila, text=t("op_res_640"), value=640, variable=vr, command=poner_res).pack(anchor="w")
        tk.Radiobutton(fila, text=t("op_res_320"), value=320, variable=vr, command=poner_res).pack(anchor="w")
        fila = self._fila(f, "op_monitor", "El puntero se mueve en una sola pantalla para que no sea muy sensible.")
        from ..sistema import pantallas
        mons = pantallas.monitores()
        opciones = ["principal"] + [str(i) for i in range(len(mons))] + ["todo"]
        nombres = ([t("op_monitor") + ": principal"] + [f"{i}: {pantallas.descripcion(m)}" for i, m in enumerate(mons)]
                   + [t("op_monitor_todo")])
        actual = str(self.cfg["pantalla"]["monitor"])
        vmon = tk.StringVar(value=nombres[opciones.index(actual)] if actual in opciones else nombres[0])
        cb = ttk.Combobox(fila, values=nombres, textvariable=vmon, state="readonly", width=24)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._set(["pantalla", "monitor"], opciones[nombres.index(vmon.get())]))
        fila = self._fila(f, "op_perfil", "Automático elige el perfil según el programa activo (SketchUp, FreeCAD...).")
        claves = ["auto"] + list(P.PERFILES.keys())
        nom_p = [t("op_perfil_auto")] + [p.nombre for p in P.PERFILES.values()]
        act = "auto" if self.cfg["perfiles"]["automatico"] else self.cfg["perfiles"]["manual"]
        vp = tk.StringVar(value=nom_p[claves.index(act)] if act in claves else nom_p[0])
        cbp = ttk.Combobox(fila, values=nom_p, textvariable=vp, state="readonly", width=28)
        cbp.pack(side="left")

        def poner_perfil(_e=None):
            k = claves[nom_p.index(vp.get())]
            if k == "auto":
                self.cfg["perfiles"]["automatico"] = True
                self.app.orden("perfil", None)
            else:
                self.cfg["perfiles"]["automatico"] = False
                self.cfg["perfiles"]["manual"] = k
                self.app.orden("perfil", k)
        cbp.bind("<<ComboboxSelected>>", poner_perfil)
        from ..sistema import inicio
        vi = tk.BooleanVar(value=inicio.activo())
        fila = self._fila(f, "op_inicio", "Arranca en pausa y en ventana pequeña.")
        tk.Checkbutton(fila, variable=vi, command=lambda: inicio.poner(bool(vi.get()))).pack(side="left")
        self._vars += [vm, vh, vc, vr, vmon, vp, vi]

    def _puntero(self, f):
        p = self.cfg["puntero"]
        val = _mapear(p["mincutoff"], 0.3, 1.5, 0, 100)
        v = tk.DoubleVar(value=max(0, min(100, val)))
        fila = self._fila(f, "op_estable_rapido", "Más estable: el puntero tiembla menos pero sigue la mano un poco "
                                                  "más tarde. Más rápido: lo contrario.")

        def poner(_x=None):
            x = float(v.get())
            p["mincutoff"] = round(_mapear(x, 0, 100, 0.3, 1.5), 3)
            p["beta"] = round(_mapear(x, 0, 100, 0.005, 0.05), 4)
            self._en_vivo()
        tk.Scale(fila, from_=0, to=100, orient="horizontal", variable=v, length=180, command=poner).pack(side="left")
        z = self.cfg["zona"]
        ancho = round((z["x1"] - z["x0"]) * 100)
        vz = tk.IntVar(value=max(30, min(80, ancho)))
        fila = self._fila(f, "op_tam_zona", "Zona más pequeña: basta mover poco la mano (cansa menos), "
                                            "pero es menos precisa.")

        def poner_zona(_x=None):
            w = int(vz.get()) / 100.0
            cx = (z["x0"] + z["x1"]) / 2
            z["x0"], z["x1"] = round(max(0.0, cx - w / 2), 3), round(min(1.0, cx + w / 2), 3)
            self._en_vivo()
        tk.Scale(fila, from_=30, to=80, orient="horizontal", variable=vz, length=180, command=poner_zona).pack(side="left")
        vrel = tk.BooleanVar(value=p["modo"] == "relativo")
        fila = self._fila(f, "op_relativo", "El puntero se mueve según cuánto mueve la mano, como un touchpad. "
                                            "Con la mano relajada se puede reacomodar.")
        tk.Checkbutton(fila, variable=vrel,
                       command=lambda: self._set(["puntero", "modo"], "relativo" if vrel.get() else "absoluto")).pack(side="left")
        self._check(f, "op_fino", ["puntero", "dibujo_fino"], "Más suave para trazos finos (Ctrl+Alt+P).")
        self._vars += [v, vz, vrel]

    def _senas(self, f):
        self._barras = []
        for nombre, grupo, k_in, k_out, medida, mayor in (
                ("Pellizco (clic)", "pellizco", "entrar", "salir", "p", False),
                ("Índice y corazón juntos (activar)", "juntos", "s_entrar", "s_salir", "s", False),
                ("V (separados)", "v", "s_entrar", "s_salir", "s", True)):
            fr = tk.LabelFrame(f, text=nombre, padx=6, pady=2)
            fr.pack(fill="x", pady=3)
            c = tk.Canvas(fr, width=300, height=18, bg="#222", highlightthickness=0)
            c.pack(side="left")
            fab_in = UMBRALES_FABRICA[grupo][k_in]
            fab_out = UMBRALES_FABRICA[grupo][k_out]
            actual = self.cfg["senas"][grupo][k_in] / fab_in
            sens = (1 / actual - 1) * 100 if mayor else (actual - 1) * 100
            vs = tk.DoubleVar(value=round(max(-40, min(40, sens))))

            def poner(_x=None, grupo=grupo, k_in=k_in, k_out=k_out, fab_in=fab_in, fab_out=fab_out, vs=vs, mayor=mayor):
                fac = 1 + float(vs.get()) / 100.0
                if mayor:
                    fac = 1 / fac
                self.cfg["senas"][grupo][k_in] = round(fab_in * fac, 3)
                self.cfg["senas"][grupo][k_out] = round(fab_out * fac, 3)
                self._en_vivo()
            tk.Label(fr, text=t("op_sensibilidad")).pack(side="left", padx=4)
            tk.Scale(fr, from_=-40, to=40, orient="horizontal", variable=vs, length=110, command=poner,
                     showvalue=False).pack(side="left")
            self._barras.append((c, grupo, k_in, k_out, medida))
            self._vars.append(vs)
        tm = self.cfg["senas"]["tiempos_ms"]
        self._escala(f, "op_tiempo_confirmar", ["senas", "tiempos_ms", "puno"], 150, 600,
                     "Cuánto tiempo hay que sostener el puño para el clic derecho.", conv=int)
        self._escala(f, "op_doble", ["senas", "tiempos_ms", "doble_ventana"], 400, 1200,
                     "Tiempo máximo entre las dos señas para pausar.", conv=int)
        self._check(f, "op_invertir", ["zoom", "invertir"])
        self._check(f, "op_zoom1", ["zoom", "una_mano"], "Pellizco del pulgar con el corazón y subir o bajar la mano.")
        self._check(f, "op_desplazar", ["senas", "desplazar_dos_manos"],
                    "Si lo apaga, el pellizco con dos manos solo acerca y aleja.")
        _ = tm

    def _comodidad(self, f):
        self._check(f, "op_codo", ["zona", "codo_apoyado"], t("tema_postura"))
        self._escala(f, "op_pausa_sin_mano", ["senas", "tiempos_ms", "pausa_sin_mano_s"], 3, 60, conv=int)
        self._escala(f, "op_descanso", ["comodidad", "descanso_min"], 0, 60, conv=int)
        self._check(f, "op_sonidos", ["comodidad", "sonidos"])
        self._check(f, "op_aviso_cursor", ["comodidad", "aviso_cursor"])
        self._escala(f, "op_opacidad", ["comodidad", "opacidad"], 60, 100, conv=lambda x: round(x / 100, 2),
                     inv=lambda x: x * 100)

    def _atajos(self, f):
        self._entradas = {}
        self.lbl_atajo = tk.Label(f, text="", fg="#B00020", wraplength=480, justify="left")
        for nombre, clave in (("pausar", "op_atajo_pausar"), ("salir", "op_atajo_salir"),
                              ("ventana", "op_atajo_ventana"), ("modo", "op_atajo_modo"),
                              ("dibujo_fino", "op_atajo_fino")):
            fila = self._fila(f, clave)
            v = tk.StringVar(value=self.cfg["atajos"][nombre])
            e = tk.Entry(fila, textvariable=v, width=18)
            e.pack(side="left")
            e.bind("<FocusOut>", lambda _e, n=nombre, v=v: self._validar_atajo(n, v))
            e.bind("<Return>", lambda _e, n=nombre, v=v: self._validar_atajo(n, v))
            self._entradas[nombre] = v
        tk.Button(f, text=t("op_atajo_restablecer"), command=self._atajos_fabrica).pack(anchor="w", pady=6)
        tk.Label(f, text="Los atajos nuevos se usan al volver a abrir el programa.", fg="#555").pack(anchor="w")
        self.lbl_atajo.pack(anchor="w", pady=4)

    def _validar_atajo(self, nombre, var) -> bool:
        texto = var.get().strip()
        try:
            mods, vk = A.interpretar(texto)
        except A.AtajoInvalido as e:
            self.lbl_atajo.configure(text=t("op_atajo_invalido", texto=texto, motivo=str(e)))
            return False
        car = A.produce_caracter(mods, vk)
        if car:
            self.lbl_atajo.configure(text=t("op_atajo_caracter", texto=texto, car=car))
            return False
        self.lbl_atajo.configure(text="")
        self.cfg["atajos"][nombre] = A.texto_atajo(mods, vk)
        return True

    def _atajos_fabrica(self):
        for n, v in self._entradas.items():
            v.set(FABRICA["atajos"][n])
            self.cfg["atajos"][n] = FABRICA["atajos"][n]

    # ------------------------------------------------------------ barras en vivo
    def _refrescar_barras(self):
        try:
            if not self.win.winfo_exists():
                return
        except tk.TclError:
            return
        v = getattr(self.app, "ultima_vista", None)
        m = (v.medidas if v is not None else {}) or {}
        for c, grupo, k_in, k_out, medida in getattr(self, "_barras", []):
            c.delete("all")
            maximo = 3.0 if medida == "s" else 1.2
            def x(val):
                return 4 + 292 * min(max(val / maximo, 0), 1)
            e = self.cfg["senas"][grupo][k_in]
            s = self.cfg["senas"][grupo][k_out]
            val = m.get(medida)
            if val is not None and isinstance(val, float) and math.isfinite(val):
                c.create_rectangle(4, 4, x(val), 14, fill="#2F6FEB", outline="")
            c.create_line(x(e), 0, x(e), 18, fill="#1FA34A", width=2)
            c.create_line(x(s), 0, x(s), 18, fill="#FF9F1C", width=2)
        self.win.after(100, self._refrescar_barras)

    # ------------------------------------------------------------ botones
    def guardar(self):
        for n, v in getattr(self, "_entradas", {}).items():
            if v.get().strip() != self.cfg["atajos"][n]:
                if not self._validar_atajo(n, v):
                    return
        self.app.cfg.datos = self.cfg
        try:
            self.app.cfg.guardar(self.cfg)
        except OSError:
            pass
        self.app.orden("config", copy.deepcopy(self.app.cfg.datos))
        self.app.aplicar_comodidad()
        self.win.destroy()

    def cancelar(self):
        self.app.cfg.datos = self.original
        self.app.orden("config", copy.deepcopy(self.original))
        self.win.destroy()

    def fabrica(self):
        nuevo = self.app.cfg.restablecer_fabrica()
        self.cfg = copy.deepcopy(nuevo)
        self.app.orden("config", copy.deepcopy(nuevo))
        self.win.destroy()
        self.app.abrir_opciones()

    def practicar(self):
        self.win.destroy()
        self.app.abrir_asistente()


_ = por_defecto
