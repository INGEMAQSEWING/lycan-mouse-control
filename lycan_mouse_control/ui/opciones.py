"""Opciones (General, Puntero, Señas, Clic, Girar, Comodidad, Atajos; el paquete C de la 1.0.2 suma
Palma después de Girar). Los cambios se ven en vivo; "Cancelar" los revierte."""
from __future__ import annotations

import copy
import math
import tkinter as tk
from tkinter import messagebox, ttk

from .. import perfiles as P
from ..clics import ORDEN_MENIQUE
from ..gestos_puno import GIROS
from ..config import FABRICA, por_defecto
from ..senas import UMBRALES_FABRICA
from ..sistema import atajos as A
from ..teclas import interpretar_envio
from .comun import LETRA, boton_ayuda
from .textos import t


def _mapear(v, a0, a1, b0, b1):
    f = (v - a0) / (a1 - a0)
    return b0 + f * (b1 - b0)


# Velocidad del puntero 1 (lento) a 10 (rápido). En modo absoluto la velocidad la da el tamaño
# de la zona de la mano: zona grande = hay que mover más la mano = puntero más lento.
ZONA_LENTO, ZONA_RAPIDO = 0.95, 0.30     # ancho de la zona (fracción de la imagen)
ZONA_ALTO_POR_ANCHO = 0.75               # la zona de fábrica es 0.60 x 0.45
ZONA_ANCHO_FABRICA = 0.60
GIRO_LENTO, GIRO_RAPIDO = 0.2, 2.0       # orbita.ganancia
GIRO_TOPE_POR_GANANCIA = 60              # orbita.max_px_cuadro = 60 x ganancia


def velocidad_de_zona(zona: dict) -> int:
    ancho = zona["x1"] - zona["x0"]
    return max(1, min(10, round(_mapear(ancho, ZONA_LENTO, ZONA_RAPIDO, 1, 10))))


def poner_velocidad_puntero(cfg: dict, vel: int) -> None:
    """Ajusta la zona (modo absoluto) y la ganancia del modo relativo según la velocidad 1-10.
    La zona conserva su centro (el de la calibración) y no se sale de la imagen."""
    vel = max(1, min(10, int(vel)))
    ancho = _mapear(vel, 1, 10, ZONA_LENTO, ZONA_RAPIDO)
    alto = min(0.95, ancho * ZONA_ALTO_POR_ANCHO)
    z = cfg["zona"]
    for a, b, w in (("x0", "x1", ancho), ("y0", "y1", alto)):
        c = (z[a] + z[b]) / 2
        lo = max(0.0, c - w / 2)
        hi = min(1.0, lo + w)
        lo = max(0.0, hi - w)
        z[a], z[b] = round(lo, 3), round(hi, 3)
    fac = ZONA_ANCHO_FABRICA / ancho
    rel = cfg["puntero"].setdefault("relativo", {})
    rel["gmin"] = round(0.6 * fac, 3)
    rel["gmax"] = round(3.0 * fac, 3)


def velocidad_de_giro(orbita: dict) -> int:
    g = float(orbita.get("ganancia", 1.0))
    return max(1, min(10, round(_mapear(g, GIRO_LENTO, GIRO_RAPIDO, 1, 10))))


def poner_velocidad_giro(cfg: dict, vel: int) -> None:
    vel = max(1, min(10, int(vel)))
    g = round(_mapear(vel, 1, 10, GIRO_LENTO, GIRO_RAPIDO), 3)
    cfg["orbita"]["ganancia"] = g
    cfg["orbita"]["max_px_cuadro"] = max(5, round(GIRO_TOPE_POR_GANANCIA * g))


NOMBRES_ATAJOS = (("pausar", "op_atajo_pausar"), ("salir", "op_atajo_salir"),
                  ("ventana", "op_atajo_ventana"), ("modo", "op_atajo_modo"),
                  ("dibujo_fino", "op_atajo_fino"))


def atajo_repetido(atajos: dict):
    """Busca dos funciones con la misma combinación (después de normalizar: «ctrl+alt+f10» y
    «Alt+Ctrl+F10» son la misma). Devuelve (texto, función ya asignada, función repetida) o None."""
    vistos = {}
    for nombre, _clave in NOMBRES_ATAJOS:
        texto = atajos.get(nombre)
        try:
            par = A.interpretar(texto)
        except A.AtajoInvalido:
            continue
        if par in vistos:
            return A.texto_atajo(*par), vistos[par], nombre
        vistos[par] = nombre
    return None


class VentanaOpciones:
    def __init__(self, root, app, cfg_inicial: dict | None = None, modo_tocado: bool = False):
        self.app = app
        self.original = copy.deepcopy(app.cfg.datos)
        # cfg_inicial: cambios sin guardar que esta ventana trae de antes (valores de fábrica)
        self.cfg = copy.deepcopy(cfg_inicial if cfg_inicial is not None else app.cfg.datos)
        # El modo VIGENTE: el botón 2D/3D y Ctrl+Alt+D lo cambian en el motor. Si el usuario no
        # toca el modo aquí, Guardar y Cancelar dejan el que esté en uso en ese momento.
        self._modo_tocado = bool(modo_tocado)
        self.original["modo"] = self._modo_vigente()
        if not self._modo_tocado:
            self.cfg["modo"] = self.original["modo"]
        self._inicio_original = None
        self._inicio_pedido = None
        self.win = tk.Toplevel(root)
        self.win.title(t("op_titulo"))
        self.win.geometry("600x520")       # 1.0.2: cabe en pantallas de 1024x768
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.cancelar)
        self._pend = None
        self._vars = []
        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._general(self._pestana(nb, "op_general"))
        self._puntero(self._pestana(nb, "op_puntero"))
        self._senas(self._pestana(nb, "op_senas"))
        self._pestana_clic(self._pestana(nb, "op_clic"))        # 1.0.2 paquete A
        self._pestana_girar(self._pestana(nb, "op_girar"))      # 1.0.2 paquete B
        # (aquí entra "Palma" del paquete C)
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
        tk.Label(f, text=t(clave_texto), font=(LETRA, 10), anchor="w", justify="left", width=30,
                 wraplength=230).pack(side="left")
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

    def _leer_camara(self) -> bool:
        """Pasa a la configuración el número de cámara de la casilla (flechitas o escrito a
        mano). Se limita a 0-3. Si no es un número, avisa y devuelve False."""
        vc = getattr(self, "_vc", None)
        if vc is None:
            return True
        texto = vc.get().strip()
        try:
            n = int(texto)
        except ValueError:
            self.lbl_camara.configure(text=t("op_camara_invalida"))
            return False
        n = min(max(n, 0), 3)
        if texto != str(n):
            vc.set(str(n))
        self.lbl_camara.configure(text="")
        if self.cfg["camara"]["indice"] != n:
            self._set(["camara", "indice"], n)
        return True

    def _modo_vigente(self) -> str:
        vig = getattr(self.app, "modo_vigente", None)
        if callable(vig):
            try:
                m = vig()
                if m in ("2D", "3D"):
                    return m
            except Exception:  # noqa: BLE001
                pass
        return self.app.cfg.datos.get("modo", "2D")

    def _con_modo(self, cfg: dict) -> dict:
        """Copia de cfg con el modo vigente si el usuario no eligió otro aquí."""
        c = copy.deepcopy(cfg)
        if not self._modo_tocado:
            c["modo"] = self._modo_vigente()
        return c

    def _en_vivo(self):
        """Aplica los cambios en vivo (con una pequeña espera para no rearmar a cada movimiento)."""
        if self._pend:
            self.win.after_cancel(self._pend)
        self._pend = self.win.after(400, lambda: self.app.orden("config", self._con_modo(self.cfg)))

    # ------------------------------------------------------------ pestañas
    def _general(self, f):
        fila = self._fila(f, "op_modo", "2D para dibujo plano; 3D agrega girar el modelo con el puño y moverlo "
                                         "con dos manos.")
        vm = tk.StringVar(value=self.cfg["modo"])
        for m in ("2D", "3D"):
            tk.Radiobutton(fila, text=m, value=m, variable=vm, command=lambda: self._poner_modo(vm.get())).pack(side="left")
        fila = self._fila(f, "op_mano", "La mano que mueve el puntero y hace los clics. Si solo se ve una mano, "
                                         "esa manda.")
        vh = tk.StringVar(value=self.cfg["mano_principal"])
        for clave, val in (("as_mano_der", "derecha"), ("as_mano_izq", "izquierda")):
            tk.Radiobutton(fila, text=t(clave), value=val, variable=vh,
                           command=lambda: self._set(["mano_principal"], vh.get())).pack(side="left")
        fila = self._fila(f, "op_camara", "Si tiene varias cámaras, pruebe 0, 1, 2...")
        # StringVar (no IntVar): lo que se escribe a mano puede no ser un número. El «command» del
        # Spinbox solo corre con las flechitas; lo escrito se lee al salir de la casilla, con
        # Enter y siempre al Guardar (antes se perdía).
        self._vc = tk.StringVar(value=str(self.cfg["camara"]["indice"]))
        sp = tk.Spinbox(fila, from_=0, to=3, width=4, textvariable=self._vc,
                        command=self._leer_camara)
        sp.pack(side="left")
        sp.bind("<FocusOut>", lambda _e: self._leer_camara())
        sp.bind("<Return>", lambda _e: self._leer_camara())
        self.lbl_camara = tk.Label(fila, text="", fg="#B00020", font=(LETRA, 9))
        self.lbl_camara.pack(side="left", padx=4)
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
        nombres = ([t("op_monitor_principal")] + [f"{i}: {pantallas.descripcion(m)}" for i, m in enumerate(mons)]
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
        cbp = ttk.Combobox(fila, values=nom_p, textvariable=vp, state="readonly", width=30)
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
        try:
            self._inicio_original = bool(inicio.activo())
        except Exception:  # noqa: BLE001
            self._inicio_original = False
        vi = tk.BooleanVar(value=self._inicio_original)
        fila = self._fila(f, "op_inicio", "Arranca en pausa y en ventana pequeña.")
        # Solo se escribe en Windows al pulsar Guardar (Cancelar no deja nada escrito).
        tk.Checkbutton(fila, variable=vi, command=lambda: setattr(self, "_inicio_pedido", bool(vi.get()))
                       ).pack(side="left")
        self._vars += [vm, vh, self._vc, vr, vmon, vp, vi]

    def _puntero(self, f):
        p = self.cfg["puntero"]
        val = _mapear(p["mincutoff"], 0.3, 1.5, 0, 100)
        v = tk.DoubleVar(value=max(0, min(100, val)))
        fila = self._fila(f, "op_estable_rapido", "Más estable: el puntero tiembla menos pero sigue la mano un poco "
                                                  "más tarde. Más ágil: lo contrario.")

        def poner(_x=None):
            x = float(v.get())
            p["mincutoff"] = round(_mapear(x, 0, 100, 0.3, 1.5), 3)
            p["beta"] = round(_mapear(x, 0, 100, 0.005, 0.05), 4)
            self._en_vivo()
        tk.Scale(fila, from_=0, to=100, orient="horizontal", variable=v, length=180, command=poner).pack(side="left")
        z = self.cfg["zona"]
        vz = tk.IntVar(value=velocidad_de_zona(z))
        fila = self._fila(f, "op_velocidad", "1 = lento: hay que mover más la mano y el puntero va despacio "
                                             "(más preciso). 10 = rápido: basta mover poco la mano.")

        def poner_velocidad(_x=None):
            poner_velocidad_puntero(self.cfg, int(vz.get()))
            self._en_vivo()
        tk.Label(fila, text=t("op_lento")).pack(side="left")
        tk.Scale(fila, from_=1, to=10, orient="horizontal", variable=vz, length=150,
                 command=poner_velocidad).pack(side="left")
        tk.Label(fila, text=t("op_rapido")).pack(side="left")
        vg = tk.IntVar(value=velocidad_de_giro(self.cfg["orbita"]))
        fila = self._fila(f, "op_velocidad_giro", "Qué tan rápido gira el modelo en Mouse Control 3D, "
                                                  "con uno o con dos puños.")

        def poner_giro(_x=None):
            poner_velocidad_giro(self.cfg, int(vg.get()))
            self._en_vivo()
        tk.Label(fila, text=t("op_lento")).pack(side="left")
        tk.Scale(fila, from_=1, to=10, orient="horizontal", variable=vg, length=150,
                 command=poner_giro).pack(side="left")
        tk.Label(fila, text=t("op_rapido")).pack(side="left")
        self._vars.append(vg)
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

    # ------------------------------------------------ 1.0.2 paquete A: pestaña "Clic"
    def _pestana_clic(self, f):
        self._check(f, "op_clic_indice", ["senas", "clic_indice"], t("ay_clic_indice"))
        self._check(f, "op_clic_anular", ["senas", "clic_anular"], t("ay_clic_anular"))
        fila = self._fila(f, "op_menique", t("ay_menique"))
        nombres = [t("mq_" + k) for k in ORDEN_MENIQUE]
        actual = self.cfg["senas"].get("menique", "doble_clic")
        vmq = tk.StringVar(value=nombres[ORDEN_MENIQUE.index(actual)] if actual in ORDEN_MENIQUE else nombres[0])
        cb = ttk.Combobox(fila, values=nombres, textvariable=vmq, state="readonly", width=22)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>",
                lambda e=None: self._set(["senas", "menique"], ORDEN_MENIQUE[nombres.index(vmq.get())]))
        self._vars.append(vmq)
        self._check(f, "op_tecla_activa", ["tecla_clic", "activa"], t("ay_tecla_activa"))
        tc = self.cfg["tecla_clic"]
        self.lbl_tecla_nombre = tk.Label(f, text=t("op_tecla_nombre", nombre=tc.get("nombre", "")),
                                         font=(LETRA, 10, "bold"), anchor="w", justify="left", wraplength=480)
        self.lbl_tecla_nombre.pack(fill="x", pady=(6, 2))
        fila = self._fila(f, "op_tecla_numerico", t("ay_tecla_aviso"))
        self._v_numerico = tk.BooleanVar(value=bool(tc.get("numerico", True)))
        tk.Radiobutton(fila, text=t("op_si"), value=True, variable=self._v_numerico,
                       command=lambda e=None: self._tecla_numerico(True)).pack(side="left")
        tk.Radiobutton(fila, text=t("op_no"), value=False, variable=self._v_numerico,
                       command=lambda e=None: self._tecla_numerico(False)).pack(side="left")
        self._vars.append(self._v_numerico)
        tk.Button(f, text=t("op_cambiar_tecla"), command=lambda e=None: self._grabar_tecla()).pack(anchor="w", pady=4)
        self.lbl_tecla_estado = tk.Label(f, text="", fg="#B26A00", font=(LETRA, 10), anchor="w", justify="left",
                                         wraplength=480)
        self.lbl_tecla_estado.pack(fill="x")
        tk.Label(f, text=t("ay_tecla_aviso"), fg="#555", font=(LETRA, 9), anchor="w", justify="left",
                 wraplength=480).pack(fill="x", pady=(6, 0))

    def _mostrar_tecla(self):
        tc = self.cfg["tecla_clic"]
        self.lbl_tecla_nombre.configure(text=t("op_tecla_nombre", nombre=tc.get("nombre", "")))
        self._v_numerico.set(bool(tc.get("numerico", True)))

    def _tecla_numerico(self, si: bool):
        """Sí: el 5 del teclado numérico. No: se graba la tecla que el usuario apriete."""
        if si:
            self._cancelar_grabar()
            fab = FABRICA["tecla_clic"]
            tc = self.cfg["tecla_clic"]
            tc["numerico"] = True
            tc["vk"], tc["scan"], tc["extendida"], tc["nombre"] = (fab["vk"], fab["scan"], fab["extendida"],
                                                                   fab["nombre"])
            tc["preguntado"] = True
            self.lbl_tecla_estado.configure(text="")
            self._mostrar_tecla()
            self._en_vivo()
        else:
            self._grabar_tecla()

    def _grabar_tecla(self):
        grabar = getattr(self.app, "grabar_tecla", None)
        if callable(grabar) and grabar(self._al_grabar_tecla):
            self.lbl_tecla_estado.configure(text=t("op_grabando"))
        else:
            self.lbl_tecla_estado.configure(text=t("op_tecla_sin_gancho"))
            self._mostrar_tecla()

    def _cancelar_grabar(self):
        cancelar = getattr(self.app, "cancelar_grabar", None)
        if callable(cancelar):
            try:
                cancelar()
            except Exception:  # noqa: BLE001
                pass

    def _al_grabar_tecla(self, ev):
        """Respuesta del gancho: ("grabada", vk, scan, extendida) o ("rechazada", vk)."""
        try:
            if not self.win.winfo_exists():
                return
        except tk.TclError:
            return
        if ev[0] == "rechazada":
            self.lbl_tecla_estado.configure(text=t("op_tecla_no_sirve"))
            return
        from ..sistema.teclado import datos_tecla_grabada
        tc = self.cfg["tecla_clic"]
        tc.update(datos_tecla_grabada(ev[1], ev[2], ev[3]))
        tc["preguntado"] = True
        self.lbl_tecla_estado.configure(text=t("op_tecla_grabada", nombre=tc["nombre"]))
        self._mostrar_tecla()
        self._en_vivo()

    # ------------------------------------------------ 1.0.2 paquete B: pestaña "Girar"
    def _pestana_girar(self, f):
        orb = self.cfg["orbita"]
        fila = self._fila(f, "op_girar_con", t("ay_girar_con"))
        nombres = [t("gi_" + k) for k in GIROS]
        actual = orb.get("girar", "un_puno")
        self._v_girar = tk.StringVar(value=nombres[GIROS.index(actual)] if actual in GIROS else nombres[0])
        cb = ttk.Combobox(fila, values=nombres, textvariable=self._v_girar, state="readonly", width=14)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>",
                lambda e=None: self._set(["orbita", "girar"], GIROS[nombres.index(self._v_girar.get())]))
        self._vars.append(self._v_girar)
        self._escala(f, "op_k_un_puno", ["orbita", "k_un_puno"], 0.3, 3.0, t("ay_k_un_puno"),
                     conv=lambda x: round(float(x), 2), paso=0.1)
        self._check(f, "op_inercia", ["orbita", "inercia"], t("ay_inercia"))
        # de izquierda a derecha: frena rápido (fricción alta) ↔ sigue girando (fricción baja)
        self._escala(f, "op_friccion", ["orbita", "friccion"], 6.0, 0.3, conv=lambda x: round(float(x), 2),
                     paso=0.1)
        self._check(f, "op_golpe", ["gestos", "golpe"], t("ch_golpe"))
        # atajos de abrir / cerrar de golpe, por programa
        self._perfiles_golpe = [(c, p.nombre) for c, p in P.PERFILES.items()]
        fila = self._fila(f, "op_programa")
        self._v_prog_golpe = tk.StringVar(value=self._perfiles_golpe[0][1])
        cbp = ttk.Combobox(fila, values=[n for _, n in self._perfiles_golpe], textvariable=self._v_prog_golpe,
                           state="readonly", width=24)
        cbp.pack(side="left")
        cbp.bind("<<ComboboxSelected>>", lambda e=None: self._mostrar_atajos_golpe())
        self._vars.append(self._v_prog_golpe)
        self._ent_golpe = {}
        for nombre, clave in (("abrir_golpe", "op_abrir_golpe"), ("cerrar_golpe", "op_cerrar_golpe")):
            fila = self._fila(f, clave, t("ay_atajo"))
            v = tk.StringVar()
            e = tk.Entry(fila, textvariable=v, width=18)
            e.pack(side="left")
            e.bind("<KeyRelease>", lambda ev=None, n=nombre: self._poner_atajo_golpe(n))
            e.bind("<FocusOut>", lambda ev=None, n=nombre: self._poner_atajo_golpe(n))
            self._ent_golpe[nombre] = v
            self._vars.append(v)
        self.lbl_golpe = tk.Label(f, text="", fg="#B00020", font=(LETRA, 9), anchor="w", justify="left",
                                  wraplength=480)
        self.lbl_golpe.pack(fill="x")
        tk.Label(f, text=t("ay_edwin3d_desdoblar"), fg="#555", font=(LETRA, 9), anchor="w", justify="left",
                 wraplength=480).pack(fill="x", pady=(4, 0))
        self._mostrar_atajos_golpe()

    def _programa_golpe(self) -> str:
        nombre = self._v_prog_golpe.get()
        for clave, n in self._perfiles_golpe:
            if n == nombre:
                return clave
        return self._perfiles_golpe[0][0]

    def _mostrar_atajos_golpe(self):
        """Muestra lo que manda cada golpe en el programa elegido (lo del usuario o lo de fábrica)."""
        clave = self._programa_golpe()
        perfil = P.PERFILES.get(clave, P.GENERICO)
        por = self.cfg.setdefault("gestos", {}).setdefault("por_programa", {})
        propio = por.get(clave) if isinstance(por.get(clave), dict) else {}
        for nombre, v in self._ent_golpe.items():
            if nombre in propio and isinstance(propio[nombre], str):
                v.set(propio[nombre])
            else:
                v.set(getattr(perfil, nombre, None) or "")
        self.lbl_golpe.configure(text="")

    def _poner_atajo_golpe(self, nombre: str):
        """Vacío = no hace nada. Un atajo que no se entiende no se guarda (y se avisa)."""
        txt = self._ent_golpe[nombre].get().strip()
        if txt and interpretar_envio(txt) is None:
            self.lbl_golpe.configure(text=t("op_atajo_malo"))
            return
        self.lbl_golpe.configure(text="")
        clave = self._programa_golpe()
        por = self.cfg.setdefault("gestos", {}).setdefault("por_programa", {})
        if not isinstance(por.get(clave), dict):
            por[clave] = {}
        if por[clave].get(nombre) == txt:
            return
        por[clave][nombre] = txt
        self._en_vivo()

    def _comodidad(self, f):
        self._check(f, "op_codo", ["zona", "codo_apoyado"], t("tema_postura"))
        self._escala(f, "op_pausa_sin_mano", ["senas", "tiempos_ms", "pausa_sin_mano_s"], 3, 60, conv=int)
        # 0 = nunca; si no, desde 5 minutos (de 1 a 4 se usa 5)
        self._escala(f, "op_descanso", ["comodidad", "descanso_min"], 0, 60,
                     conv=lambda x: 0 if int(x) == 0 else max(int(x), 5))
        self._check(f, "op_sonidos", ["comodidad", "sonidos"])
        self._check(f, "op_aviso_cursor", ["comodidad", "aviso_cursor"])
        self._escala(f, "op_opacidad", ["comodidad", "opacidad"], 60, 100, conv=lambda x: round(x / 100, 2),
                     inv=lambda x: x * 100)

    def _atajos(self, f):
        self._entradas = {}
        self.lbl_atajo = tk.Label(f, text="", fg="#B00020", wraplength=480, justify="left")
        for nombre, clave in NOMBRES_ATAJOS:
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

    def _poner_modo(self, modo):
        self._modo_tocado = True
        self._set(["modo"], modo)

    def _es_ensayo(self) -> bool:
        args = getattr(self.app, "args", None)
        return bool(getattr(args, "simular", False))

    def _aplicar_inicio(self):
        """Abrir al encender: se escribe en Windows SOLO al guardar y nunca en modo ensayo."""
        if self._inicio_pedido is None or self._inicio_pedido == self._inicio_original:
            return
        if self._es_ensayo():
            return
        from ..sistema import inicio
        try:
            inicio.poner(self._inicio_pedido)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ botones
    def guardar(self):
        if not self._leer_camara():
            return
        for n, v in getattr(self, "_entradas", {}).items():
            if v.get().strip() != self.cfg["atajos"][n]:
                if not self._validar_atajo(n, v):
                    return
        # Dos funciones con el mismo atajo: al volver a abrir solo funcionaría una (y podía
        # perderse «Salir», el atajo de seguridad). No se guarda hasta corregirlo.
        rep = atajo_repetido(self.cfg["atajos"])
        if rep is not None:
            texto, ya, otra = rep
            nombres = dict(NOMBRES_ATAJOS)
            self.lbl_atajo.configure(text=t("op_atajo_repetido", texto=texto, funcion=t(nombres[ya]),
                                            otra=t(nombres[otra])))
            return
        if self._pend:
            self.win.after_cancel(self._pend)
            self._pend = None
        self._cancelar_grabar()
        self.cfg = self._con_modo(self.cfg)
        self.app.cfg.datos = self.cfg
        guardar = getattr(self.app, "guardar_config", None)
        if callable(guardar):
            guardar(self.cfg)
        else:
            try:
                self.app.cfg.guardar(self.cfg)
            except OSError:
                pass
        self._aplicar_inicio()
        self.app.orden("config", copy.deepcopy(self.app.cfg.datos))
        self.app.aplicar_comodidad()
        self.win.destroy()

    def cancelar(self):
        self._cancelar_grabar()
        if self._pend:
            try:
                self.win.after_cancel(self._pend)
            except tk.TclError:
                pass
            self._pend = None
        # Se vuelve a la configuración GUARDADA EN ESTE MOMENTO (no a la copia de cuando se abrió
        # esta ventana): si mientras tanto se guardó algo (otra ventana, la calibración), Cancelar
        # no lo borra. Esta ventana nunca toca app.cfg.datos antes de Guardar; los cambios en
        # vivo solo fueron al motor, así que basta con mandarle otra vez lo guardado.
        actual = copy.deepcopy(self.app.cfg.datos)
        actual["modo"] = self._modo_vigente()       # el modo que esté en uso, no el de antes
        self.app.cfg.datos = actual
        self.app.orden("config", copy.deepcopy(actual))
        try:
            self.app.aplicar_comodidad()        # la ventana vuelve a la opacidad guardada
        except Exception:  # noqa: BLE001
            pass
        self.win.destroy()

    def _preguntar(self, texto: str) -> bool:
        return bool(messagebox.askyesno(t("op_fabrica"), texto, parent=self.win))

    def fabrica(self):
        """Carga los valores de fábrica SOLO en esta ventana (y en vivo en el motor). No toca la
        configuración guardada hasta pulsar «Guardar»: «Cancelar» los revierte como cualquier
        otro cambio. Los atajos y la posición de la ventana se conservan."""
        if not self._preguntar(t("op_fabrica_pregunta")):
            return None
        nuevo = por_defecto()
        nuevo["atajos"] = copy.deepcopy(self.cfg.get("atajos", nuevo["atajos"]))
        nuevo["ventana"] = copy.deepcopy(self.app.cfg.datos.get("ventana", nuevo["ventana"]))
        nuevo["primera_vez"] = False
        nuevo["modo"] = self.cfg.get("modo", nuevo["modo"])
        if self._pend:
            try:
                self.win.after_cancel(self._pend)
            except tk.TclError:
                pass
            self._pend = None
        self.app.orden("config", self._con_modo(nuevo))
        master = self.win.master
        self.win.destroy()
        # se vuelve a abrir la ventana mostrando los valores de fábrica (aún sin guardar)
        nueva = VentanaOpciones(master, self.app, cfg_inicial=nuevo, modo_tocado=self._modo_tocado)
        nueva._inicio_pedido = self._inicio_pedido
        if hasattr(self.app, "_opciones"):
            self.app._opciones = nueva
        return nueva

    def practicar(self):
        """Los cambios sin guardar NO siguen en uso al practicar: se revierten como con
        «Cancelar» (el motor vuelve a lo guardado) y luego se abre el asistente."""
        self.cancelar()
        self.app.abrir_asistente()


_ = por_defecto
