"""Asistente de primera vez (modo ensayo: usa la salida simulada, el ratón no hace nada).

Barra "Paso N de M", botón "?" en cada paso y botones Atrás / Repetir / Saltar / Siguiente.
Siguiente se habilita al lograr la seña las veces pedidas. A los 15 s sin lograrla, aparece una pista.
"""
from __future__ import annotations

import copy
import math
import time
import tkinter as tk

import numpy as np

from .. import constantes as K
from ..salida.simulada import SalidaSimulada
from .ayuda import dibujar_mano
from .calibracion import Calibracion
from .comun import LETRA, boton_ayuda
from .textos import t


class Paso:
    def __init__(self, clave, texto, meta=0, pista=None, postura=None, ayuda=None, tipo="info"):
        self.clave, self.texto, self.meta, self.pista, self.postura = clave, texto, meta, pista, postura
        self.ayuda = ayuda or texto
        self.tipo = tipo


def pasos_para(modo: str, girar: str = "un_puno", cfg: dict | None = None) -> list[Paso]:
    """Pasos del asistente. ``girar`` es la opción orbita.girar (1.0.2 paquete B): con un puño (o
    «los dos») el paso «girar» enseña el puño que se mueve; con dos puños, el volante de antes.
    Revisión 1.0.2: con ``cfg`` se quitan los pasos de las señas que el usuario apagó."""
    un_puno = girar != "dos_punos"
    p = [
        Paso("bienvenida", "as_bienvenida", ayuda="tema_complemento"),
        # 1.0.2 paquete C: dos botones (brazo apoyado / mano baja cerca del teclado)
        Paso("postura", "as_postura", ayuda="tema_postura", postura="apuntar", tipo="postura"),
        Paso("camara", "as_camara", ayuda="tema_luz", tipo="camara"),
        Paso("mano", "as_mano", tipo="mano"),
        Paso("calibrar", "as_calibrar", tipo="calibrar"),
        Paso("activar", "as_activar", 1, "pista_activar", "juntos", tipo="logro"),
        Paso("mover", "as_mover", 4, "pista_mover", "apuntar", tipo="mover"),
        Paso("clic", "as_clic", 4, "pista_clic", "pellizco", tipo="logro"),
        # 1.0.2 paquete A
        Paso("clic_anular", "as_clic_anular", 2, "pista_clic_anular", "pellizco_anular", tipo="logro"),
        Paso("derecho", "as_derecho", 3, "pista_derecho", "puno", tipo="logro"),
        Paso("tecla", "as_tecla", 2, "pista_tecla", None, ayuda="tema_tecla", tipo="tecla"),
        Paso("zoom", "as_zoom", 3, "pista_zoom", "pellizco", tipo="logro"),
        # 1.0.2 paquete C
        Paso("scroll", "as_scroll", 1, "pista_scroll", "abierta", ayuda="ch_palma", tipo="logro"),
    ]
    if modo == "3D":
        pista = "pista_girar_un_puno" if un_puno else "pista_girar"
        p += [Paso("girar", "as_girar_un_puno" if un_puno else "as_girar", 1, pista, "puno", tipo="logro"),
              Paso("desplazar", "as_desplazar_3D", 1, "pista_zoom", "pellizco", tipo="logro"),
              Paso("soltar", "as_soltar_un_puno" if girar == "un_puno" else "as_soltar", 1, pista,
                   "abierta", tipo="logro")]
    if isinstance(cfg, dict):
        senas = cfg.get("senas") or {}
        apagados = set()
        if senas.get("clic_indice", True) is False:
            apagados.add("clic")
        if senas.get("clic_anular", True) is False:
            apagados.add("clic_anular")
        if (cfg.get("scroll") or {}).get("palma", True) is False:
            apagados.add("scroll")
        p = [x for x in p if x.clave not in apagados]
    # «Pausar» va de ÚLTIMO: el paso se logra justamente dejando el programa en pausa, y en
    # pausa no se puede practicar nada más (en 3D, girar y mover el modelo quedaban imposibles).
    p.append(Paso("pausar", "as_pausar", 1, "pista_activar", "juntos", tipo="logro"))
    return p


# pasos que se practican con el control ACTIVO (en pausa no pasa nada)
PASOS_ACTIVOS = ("mover", "clic", "derecho", "zoom", "girar", "desplazar", "soltar", "clic_anular", "tecla",
                 "scroll")
# pasos que se cuentan con lo que decide la máquina (con el asistente en primer plano la salida
# no deja pasar los clics): clave del paso -> clave de Vista.cuentas
CUENTAS_MAQUINA = {"clic_anular": "anular", "tecla": "tecla", "scroll": "scroll"}


def contar_maquina(clave: str, vista, extra: dict) -> int:
    """Cuántas veces lo hizo desde que empezó el paso, según las cuentas de la máquina. Si el
    motor se rearmó (cambio de opciones) las cuentas vuelven a 0: lo nuevo se suma."""
    return contar_maquina_clave(CUENTAS_MAQUINA[clave], vista, extra)


def contar_maquina_clave(k: str, vista, extra: dict) -> int:
    total = extra.get("total_" + k, 0)
    if vista is None:
        return total
    actual = int((getattr(vista, "cuentas", None) or {}).get(k, 0))
    ult = extra.get("ult_" + k)
    if ult is not None:
        total += actual - ult if actual >= ult else actual
    extra["ult_" + k] = actual
    extra["total_" + k] = total
    return total


def texto_sin_imagen(camara: str) -> str:
    """Qué decir en el paso «Cámara y luz» cuando no llega imagen, según el estado de la cámara."""
    return {"OCUPADA": t("aviso_camara_ocupada"), "NO_ABRE": t("aviso_no_camara"),
            "PERDIDA": t("aviso_camara_perdida")}.get(camara or "", t("as_sin_imagen"))


def contar_logros(clave: str, eventos: list, vista=None, extra: dict | None = None) -> int:
    """Cuenta cuántas veces se logró la seña del paso a partir de los eventos simulados."""
    extra = extra if extra is not None else {}
    if clave in CUENTAS_MAQUINA:
        return contar_maquina(clave, vista, extra)
    if clave == "zoom" and vista is not None and "zoom" in (getattr(vista, "cuentas", None) or {}):
        # revisión 1.0.2: solo cuenta acercar/alejar de verdad (la palma también manda rueda)
        extra.setdefault("_zoom", True)
        return contar_maquina_clave("zoom", vista, extra)
    evs = [ev for _, ev in eventos]
    if clave == "activar":
        return 1 if (vista is not None and vista.estado not in (K.PAUSA, K.BLOQUEADO)) else 0
    if clave == "clic":
        clics = sum(1 for e in evs if e[0] == "boton" and e[1] == "izq" and e[2])
        # arrastre: botón izquierdo abajo, el puntero se mueve más de 50 px y se suelta
        arrastres, abajo, origen = 0, False, None
        cursor = None
        for e in evs:
            if e[0] == "mover":
                cursor = (e[1], e[2])
            elif e[0] == "boton" and e[1] == "izq":
                if e[2]:
                    abajo, origen = True, cursor
                elif abajo:
                    abajo = False
                    if origen and cursor and math.hypot(cursor[0] - origen[0], cursor[1] - origen[1]) > 50:
                        arrastres += 1
        return min(clics, 3) + (1 if arrastres else 0)
    if clave == "derecho":
        return sum(1 for e in evs if e[0] == "boton" and e[1] == "der" and e[2])
    if clave == "zoom":
        return sum(1 for e in evs if e[0] == "rueda")
    if clave == "pausar":
        if vista is not None and vista.estado not in (K.PAUSA, K.BLOQUEADO):
            extra["estuvo_activo"] = True
        return 1 if (extra.get("estuvo_activo") and vista is not None and vista.estado == K.PAUSA) else 0
    if clave == "girar":
        medio = any(e[0] == "boton" and e[1] == "medio" and e[2] for e in evs)
        movs = sum(1 for e in evs if e[0] == "mover")
        return 1 if medio and movs >= 10 else 0
    if clave == "desplazar":
        shift = any(e[0] == "tecla" and e[1] == "shift" and e[2] for e in evs)
        medio = any(e[0] == "boton" and e[1] == "medio" and e[2] for e in evs)
        dos_manos_medio = medio and (shift or (vista is not None and vista.modo == "3D"))
        return 1 if dos_manos_medio else 0
    if clave == "soltar":
        return 1 if any(e[0] == "boton" and e[1] == "medio" and not e[2] for e in evs) else 0
    return 0


class Asistente:
    def __init__(self, root, app):
        self.app = app
        # el modo VIGENTE (el botón 2D/3D o Ctrl+Alt+D lo cambian sin pasar por la configuración)
        vigente = getattr(app, "modo_vigente", None)
        self.modo = vigente() if callable(vigente) else app.cfg.datos.get("modo", "2D")
        datos = getattr(app.cfg, "datos", None) or {}
        orbita = datos.get("orbita") or {}
        self.pasos = pasos_para(self.modo, orbita.get("girar", "un_puno"), datos)
        self.i = 0
        self.win = tk.Toplevel(root)
        self.win.title(t("as_titulo"))
        self.win.geometry("720x580")
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.salida = SalidaSimulada()
        app.orden("ensayo", True, self.salida)

        arriba = tk.Frame(self.win)
        arriba.pack(fill="x", padx=12, pady=(10, 0))
        self.lbl_paso = tk.Label(arriba, text="", font=(LETRA, 10))
        self.lbl_paso.pack(side="left")
        self.barra = tk.Canvas(arriba, width=300, height=8, bg="#DDD", highlightthickness=0)
        self.barra.pack(side="left", padx=10)
        self.btn_ayuda_marco = tk.Frame(arriba)
        self.btn_ayuda_marco.pack(side="right")
        tk.Label(self.win, text=t("as_ensayo"), fg="#2F6FEB", font=(LETRA, 9)).pack(anchor="w", padx=12)

        # Los botones de abajo se empaquetan ANTES que el cuerpo: así tkinter les reserva su
        # espacio y nunca quedan cortados aunque el contenido pida más alto que la ventana.
        abajo = tk.Frame(self.win)
        abajo.pack(side="bottom", fill="x", padx=12, pady=10)
        self.abajo = abajo
        self.b_atras = tk.Button(abajo, text=t("as_atras"), command=self.atras)
        self.b_atras.pack(side="left")
        tk.Button(abajo, text=t("as_repetir"), command=self.repetir).pack(side="left", padx=6)
        tk.Button(abajo, text=t("as_saltar"), command=self.siguiente).pack(side="left")
        self.b_sig = tk.Button(abajo, text=t("as_siguiente"), command=self.siguiente)
        self.b_sig.pack(side="right")

        cuerpo = tk.Frame(self.win)
        cuerpo.pack(fill="both", expand=True, padx=12, pady=6)
        izq = tk.Frame(cuerpo, width=380)
        izq.pack(side="left", fill="both", expand=True)
        self.izq = izq
        self.lbl_texto = tk.Label(izq, text="", font=(LETRA, 13), wraplength=370, justify="left")
        self.lbl_texto.pack(anchor="w")
        self.dibujo = tk.Canvas(izq, width=120, height=120, highlightthickness=0, bg="#1F242B")
        self.dibujo.pack(anchor="w", pady=8)
        self.lbl_logro = tk.Label(izq, text="", font=(LETRA, 12, "bold"), fg="#1FA34A")
        self.lbl_logro.pack(anchor="w")
        self.lbl_pista = tk.Label(izq, text="", font=(LETRA, 10), fg="#B26A00", wraplength=370, justify="left")
        self.lbl_pista.pack(anchor="w", pady=4)
        self.extra = tk.Frame(izq)
        self.extra.pack(anchor="w", fill="x")
        der = tk.Frame(cuerpo)
        der.pack(side="right", fill="y")
        from PIL import Image, ImageTk
        self._Image = Image
        self._foto = ImageTk.PhotoImage(Image.new("RGB", (320, 240), (20, 22, 26)))
        tk.Label(der, image=self._foto).pack()
        self.lbl_estado = tk.Label(der, text="", font=(LETRA, 11, "bold"))
        self.lbl_estado.pack(pady=4)
        self.pantalla = tk.Canvas(der, width=320, height=120, bg="#0F1115", highlightthickness=0)
        self.pantalla.pack()
        self._mostrar()
        self._ajustar_tamano()
        self._listo_tamano = True
        self._tick()

    def _ajustar_tamano(self):
        """La ventana nunca queda más pequeña que lo que pide su contenido (con letras grandes
        de Windows al 125 % o 150 % pide más)."""
        try:
            self.win.update_idletasks()
            w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
            self.win.minsize(w, h)
            if self.win.winfo_height() < h or self.win.winfo_width() < w:
                self.win.geometry(f"{max(w, self.win.winfo_width())}x{max(h, self.win.winfo_height())}")
        except tk.TclError:
            pass

    # ------------------------------------------------------------ pasos
    @property
    def paso(self) -> Paso:
        return self.pasos[self.i]

    def _mostrar(self):
        # revisión 1.0.2: al cambiar de paso (Atrás, Siguiente, Repetir) se deja de esperar la
        # tecla nueva; si no, la próxima tecla en cualquier programa se tragaba
        self._cancelar_grabar()
        p = self.paso
        n, m = self.i + 1, len(self.pasos)
        self.lbl_paso.configure(text=t("as_paso", n=n, m=m))
        self.barra.delete("all")
        self.barra.create_rectangle(0, 0, 300 * n / m, 8, fill="#2F6FEB", outline="")
        for w in self.btn_ayuda_marco.winfo_children():
            w.destroy()
        boton_ayuda(self.btn_ayuda_marco, t(p.ayuda)).pack()
        self.lbl_texto.configure(text=t(p.texto))
        self.dibujo.delete("all")
        if p.postura:
            dibujar_mano(self.dibujo, p.postura, 10, 10, tam=100)
            # el giro con un puño se enseña con una sola mano (1.0.2 paquete B)
            if p.clave in ("zoom", "desplazar") or (p.clave == "girar" and p.texto == "as_girar"):
                self.dibujo.configure(width=230)
                dibujar_mano(self.dibujo, p.postura, 120, 10, tam=100, lado="Left")
            else:
                self.dibujo.configure(width=120)
        self.lbl_pista.configure(text="")
        self.lbl_logro.configure(text="")
        for w in self.extra.winfo_children():
            w.destroy()
        self.t_inicio = time.monotonic()
        self.ev_inicio = len(self.salida.eventos)
        self.extra_estado = {}
        self.dianas = []
        if p.tipo == "mano":
            v = tk.StringVar(value=self.app.cfg.datos["mano_principal"])
            for clave, val in (("as_mano_der", "derecha"), ("as_mano_izq", "izquierda")):
                tk.Radiobutton(self.extra, text=t(clave), value=val, variable=v, font=(LETRA, 11),
                               command=lambda: self._poner_mano(v.get())).pack(anchor="w")
            self._var_mano = v
        elif p.tipo == "calibrar":
            Calibracion(self.extra, self.app, self._fin_calibracion).pack(anchor="w", fill="x")
        elif p.tipo == "mover":
            rng = np.random.default_rng(int(time.time()) % 1000)
            self.dianas = [(float(x), float(y)) for x, y in rng.uniform(0.15, 0.85, (4, 2))]
            self.alcanzadas = set()
        elif p.tipo == "tecla":
            self._paso_tecla()
        elif p.tipo == "postura":
            self._paso_postura()
        if p.tipo in ("logro", "mover", "tecla"):
            self.b_sig.configure(state="disabled")
        else:
            self.b_sig.configure(state="normal")
        self.b_atras.configure(state="normal" if self.i > 0 else "disabled")
        self.b_sig.configure(text=t("as_terminar") if self.i == len(self.pasos) - 1 else t("as_siguiente"))
        if getattr(self, "_listo_tamano", False):
            self._ajustar_tamano()            # revisión 1.0.2: cada paso pide su alto

    # ------------------------------------------------ 1.0.2 paquete A: paso de la tecla
    def _paso_tecla(self):
        fila = tk.Frame(self.extra)
        fila.pack(anchor="w", pady=4)
        tk.Button(fila, text=t("op_si"), width=6, command=lambda e=None: self._tecla_si()).pack(side="left")
        tk.Button(fila, text=t("op_no"), width=6, command=lambda e=None: self._tecla_no()).pack(side="left", padx=6)
        tk.Button(fila, text=t("as_tecla_saltar"), command=lambda e=None: self._tecla_no_quiero()).pack(side="left")
        self.lbl_tecla = tk.Label(self.extra, text="", font=(LETRA, 11), wraplength=370, justify="left")
        self.lbl_tecla.pack(anchor="w", pady=4)

    # ------------------------------------------------ 1.0.2 paquete C: paso de la postura
    def _paso_postura(self):
        tk.Label(self.extra, text=t("as_postura_elegir"), font=(LETRA, 11, "bold"), wraplength=370,
                 justify="left").pack(anchor="w", pady=(4, 2))
        fila = tk.Frame(self.extra)
        fila.pack(anchor="w", pady=2)
        tk.Button(fila, text=t("as_postura_apoyado"), command=lambda e=None: self._poner_postura(False)
                  ).pack(side="left")
        tk.Button(fila, text=t("as_postura_baja"), command=lambda e=None: self._poner_postura(True)
                  ).pack(side="left", padx=6)
        self.lbl_postura = tk.Label(self.extra, text="", font=(LETRA, 10), wraplength=370, justify="left")
        self.lbl_postura.pack(anchor="w", pady=4)
        baja = bool((self.app.cfg.datos.get("zona") or {}).get("mano_baja", False))
        self.lbl_postura.configure(text=t("as_consejo_baja") if baja else "")

    def _poner_postura(self, baja: bool):
        """Brazo apoyado o mano baja (zona.mano_baja). Con la mano baja se muestra el consejo."""
        cfg = copy.deepcopy(self.app.cfg.datos)
        cfg.setdefault("zona", {})["mano_baja"] = bool(baja)
        self.app.cfg.datos = cfg
        self.app.orden("config", copy.deepcopy(cfg))
        self.lbl_postura.configure(text=t("as_consejo_baja") if baja else "")
        self.extra_estado["postura"] = "baja" if baja else "apoyado"
        self._ajustar_tamano()

    def _cfg_tecla(self, cambios: dict):
        cfg = copy.deepcopy(self.app.cfg.datos)
        tc = cfg.setdefault("tecla_clic", {})
        tc.update(cambios)
        tc["preguntado"] = True
        self.app.cfg.datos = cfg
        self.app.orden("config", copy.deepcopy(cfg))

    def _tecla_si(self):
        from ..config import FABRICA
        self._cancelar_grabar()
        fab = FABRICA["tecla_clic"]
        self._cfg_tecla({"activa": True, "numerico": True, "vk": fab["vk"], "scan": fab["scan"],
                         "extendida": False, "nombre": fab["nombre"]})
        self.lbl_tecla.configure(text=t("as_tecla_si"))
        self.extra_estado["elegido"] = True

    def _tecla_no(self):
        grabar = getattr(self.app, "grabar_tecla", None)
        if callable(grabar) and grabar(self._al_grabar_tecla):
            self.lbl_tecla.configure(text=t("as_tecla_no"))
        else:
            self.lbl_tecla.configure(text=t("op_tecla_sin_gancho"))

    def _al_grabar_tecla(self, ev):
        try:
            if not self.win.winfo_exists() or self.paso.tipo != "tecla":
                return
        except tk.TclError:
            return
        if ev[0] == "rechazada":
            self.lbl_tecla.configure(text=t("op_tecla_no_sirve"))
            return
        if ev[0] == "rechazada_mod":
            self.lbl_tecla.configure(text=t("op_tecla_con_mod"))
            return
        if ev[0] == "cancelada":
            self.lbl_tecla.configure(text=t("op_grabar_cancelada"))
            return
        from ..sistema.teclado import VK_COMUNES, datos_tecla_grabada
        datos = datos_tecla_grabada(ev[1], ev[2], ev[3])
        datos["activa"] = True
        self._cfg_tecla(datos)
        texto = t("as_tecla_listo", nombre=datos["nombre"])
        if ev[1] in VK_COMUNES:
            texto += " " + t("op_tecla_comun", nombre=datos["nombre"])
        self.lbl_tecla.configure(text=texto)
        self.extra_estado["elegido"] = True

    def _tecla_no_quiero(self):
        self._cancelar_grabar()
        self._cfg_tecla({"activa": False})
        self.lbl_tecla.configure(text="")
        self.extra_estado["no_quiere"] = True
        self.b_sig.configure(state="normal")

    def _cancelar_grabar(self):
        cancelar = getattr(self.app, "cancelar_grabar", None)
        if callable(cancelar):
            try:
                cancelar()
            except Exception:  # noqa: BLE001
                pass

    def _poner_mano(self, mano):
        cfg = copy.deepcopy(self.app.cfg.datos)
        cfg["mano_principal"] = mano
        self.app.cfg.datos = cfg
        self.app.orden("config", copy.deepcopy(cfg))

    def _fin_calibracion(self, ok):
        self.b_sig.configure(state="normal")

    def atras(self):
        if self.i > 0:
            self.i -= 1
            self._mostrar()

    def repetir(self):
        self._mostrar()

    def siguiente(self):
        if self.i >= len(self.pasos) - 1:
            self.terminar()
            return
        self.i += 1
        self._mostrar()

    def terminar(self):
        self.app.cfg.datos["primera_vez"] = False
        listo = self._guardar()
        if listo:
            self.app.mostrar_aviso(t("as_listo"))
        self.cerrar()

    def _guardar(self) -> bool:
        guardar = getattr(self.app, "guardar_config", None)
        if callable(guardar):
            return bool(guardar())
        try:
            self.app.cfg.guardar()
            return True
        except OSError:
            return False

    def cerrar(self):
        self._cancelar_grabar()
        self.app.orden("ensayo", False)
        if self.app.cfg.datos.get("primera_vez"):
            self.app.cfg.datos["primera_vez"] = False
            self._guardar()
        cerrado = getattr(self.app, "asistente_cerrado", None)
        if callable(cerrado):
            cerrado(self)
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ refresco
    def _tick(self):
        try:
            if not self.win.winfo_exists():
                return
        except tk.TclError:
            return
        v = getattr(self.app, "ultima_vista", None)
        if v is not None:
            if v.imagen is not None:
                self._foto.paste(self._Image.fromarray(np.ascontiguousarray(v.imagen)))
            self.lbl_estado.configure(text=t("estado_" + v.estado), fg=K.COLORES_ESTADO.get(v.estado, "#333"))
        self._pintar_pantalla(v)
        p = self.paso
        if p.tipo == "tecla" and self.extra_estado.get("no_quiere"):
            self.lbl_logro.configure(text="")
        elif p.tipo in ("logro", "mover", "tecla"):
            if p.tipo == "mover":
                k = len(self.alcanzadas)
            else:
                k = contar_logros(p.clave, self.salida.eventos[self.ev_inicio:], v, self.extra_estado)
            k = min(k, p.meta)
            self.lbl_logro.configure(text=t("as_logrado", k=k, n=p.meta) if k else "")
            if k >= p.meta:
                self.b_sig.configure(state="normal")
                self.lbl_pista.configure(text="")
            elif p.clave in PASOS_ACTIVOS and v is not None and v.estado == K.PAUSA:
                # en pausa la seña de este paso no hace nada: se dice de una vez qué hacer
                self.lbl_pista.configure(text=t("as_reactivar"))
            elif time.monotonic() - self.t_inicio > 15 and p.pista:
                self.lbl_pista.configure(text=t("as_pista", texto=t(p.pista)))
            else:
                self.lbl_pista.configure(text="")
        elif p.tipo == "camara":
            self.lbl_pista.configure(text=self.texto_camara(v))
        self.win.after(66, self._tick)

    def texto_camara(self, v, ahora: float | None = None) -> str:
        """Texto del paso «Cámara y luz». Si no llega imagen NO dice que la luz está bien."""
        from ..calibracion import evaluar_luz
        ahora = time.monotonic() if ahora is None else ahora
        brillo = getattr(v, "brillo", float("nan")) if v is not None else float("nan")
        if brillo is not None and math.isfinite(brillo):
            self._t_ult_imagen = ahora
            self._ult_brillo = brillo
        brillo = getattr(self, "_ult_brillo", float("nan"))
        camara = getattr(v, "camara", "") if v is not None else ""
        # una vista suelta sin cuadro nuevo (cada 0,25 s) no cuenta: hace falta 1 s sin imagen
        sin_imagen = (v is None or camara in ("OCUPADA", "NO_ABRE", "PERDIDA", "DETENIDA")
                      or ahora - getattr(self, "_t_ult_imagen", -1e9) > 1.0)
        if sin_imagen:
            return texto_sin_imagen(camara)
        e = evaluar_luz(brillo)
        txt = {"poca": t("cal_luz_poca"), "mucha": t("cal_luz_mucha"), "ok": t("cal_luz_ok"),
               "sin_dato": t("as_sin_imagen")}[e]
        if not v.manos:
            txt += "  " + t("cal_sin_mano")
        return txt

    def _pintar_pantalla(self, v):
        c = self.pantalla
        c.delete("all")
        W, H = 320, 120
        c.create_rectangle(1, 1, W - 1, H - 1, outline="#444")
        cur = v.cursor if v is not None else None
        ex, ey, ew, eh = self.salida.escritorio
        if self.paso.tipo == "mover":
            for i, (fx, fy) in enumerate(self.dianas):
                x, y = fx * W, fy * H
                hecho = i in self.alcanzadas
                c.create_oval(x - 10, y - 10, x + 10, y + 10, outline="#1FA34A" if hecho else "#FF9F1C", width=2)
                if cur is not None and not hecho:
                    cx, cy = (cur[0] - ex) / ew * W, (cur[1] - ey) / eh * H
                    if math.hypot(cx - x, cy - y) < 12 and v.estado != K.PAUSA:
                        self.alcanzadas.add(i)
        if cur is not None:
            cx, cy = (cur[0] - ex) / ew * W, (cur[1] - ey) / eh * H
            c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill="white", outline="")
