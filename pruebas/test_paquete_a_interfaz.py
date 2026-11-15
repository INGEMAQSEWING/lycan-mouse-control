"""1.0.2 paquete A «Clics»: interfaz (pestaña Clic de Opciones, asistente, ayuda y textos).

Sin cámara y sin gancho de teclado: las respuestas del gancho se simulan llamando a los
manejadores directamente.
"""
import tkinter as tk
from tkinter import ttk

import numpy as np
import pytest

from lycan_mouse_control import constantes as K
from lycan_mouse_control.motor import Vista
from test_interfaz import bombear
from test_ronda1_interfaz import AppModo, root  # noqa: F401 - fixture


def _textos(w, out=None):
    out = [] if out is None else out
    for h in w.winfo_children():
        try:
            txt = h.cget("text")
            if txt:
                out.append(str(txt))
        except tk.TclError:
            pass
        _textos(h, out)
    return out


def test_opciones_tiene_la_pestana_clic_en_su_lugar(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    try:
        nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
        nombres = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
        # (1.0.2 paquete B: «Girar» entra después de «Clic»)
        assert nombres == [t("op_general"), t("op_puntero"), t("op_senas"), t("op_clic"), t("op_girar"),
                           t("op_comodidad"), t("op_atajos")]
        bombear(root, 80)
        op.win.update_idletasks()
        assert op.win.geometry().startswith("600x520"), op.win.geometry()
        nb.select(3)
        bombear(root, 80)
        textos = _textos(nb.nametowidget(nb.tabs()[3]))
        for clave in ("op_clic_indice", "op_clic_anular", "op_menique", "op_tecla_activa", "op_cambiar_tecla"):
            assert t(clave) in textos, clave
        assert t("op_tecla_nombre", nombre="5 del teclado numérico") in textos
    finally:
        op.cancelar()


def test_opciones_cabe_en_1024x768(root, tmp_path):
    """La ventana de Opciones (600x520) no pide más que una pantalla de 1024x768."""
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    try:
        nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
        for i in range(len(nb.tabs())):
            nb.select(i)
            bombear(root, 40)
        op.win.update_idletasks()
        assert op.win.winfo_width() >= 600
        assert op.win.winfo_reqwidth() <= 1024 and op.win.winfo_reqheight() <= 768 - 60
        assert op.win.winfo_width() <= 1024 and op.win.winfo_height() <= 768 - 60
    finally:
        op.cancelar()


def test_opciones_menique_y_casillas_cambian_la_config(root, tmp_path):
    from lycan_mouse_control.clics import ORDEN_MENIQUE
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    try:
        combos = []

        def buscar(w):
            for h in w.winfo_children():
                if isinstance(h, ttk.Combobox) and t("mq_doble_clic") in h.cget("values"):
                    combos.append(h)
                buscar(h)
        buscar(op.win)
        assert len(combos) == 1
        cb = combos[0]
        assert tuple(cb.cget("values")) == tuple(t("mq_" + k) for k in ORDEN_MENIQUE)
        cb.set(t("mq_deshacer"))
        cb.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op.cfg["senas"]["menique"] == "deshacer"
        op.guardar()
        assert app.cfg.datos["senas"]["menique"] == "deshacer"
    finally:
        try:
            op.win.destroy()
        except tk.TclError:
            pass


def test_opciones_grabar_tecla_sin_gancho_y_con_respuestas(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    try:
        # sin gancho (AppModo no lo tiene): lo dice y no cambia la tecla
        op._grabar_tecla()
        assert op.lbl_tecla_estado.cget("text") == t("op_tecla_sin_gancho")
        op._tecla_numerico(False)
        assert op.cfg["tecla_clic"]["numerico"] is True and op._v_numerico.get() is True
        # respuestas del gancho
        op._al_grabar_tecla(("rechazada", 0x11))
        assert op.lbl_tecla_estado.cget("text") == t("op_tecla_no_sirve")
        op._al_grabar_tecla(("grabada", 0x7A, 0x57, False))
        tc = op.cfg["tecla_clic"]
        assert tc["numerico"] is False and tc["vk"] == 0x7A and tc["scan"] == 0x57 and tc["preguntado"]
        assert tc["nombre"] in op.lbl_tecla_nombre.cget("text")
        assert op._v_numerico.get() is False
        op._tecla_numerico(True)
        assert op.cfg["tecla_clic"]["numerico"] is True and op.cfg["tecla_clic"]["vk"] == 0x65
        assert "5 del teclado numérico" in op.lbl_tecla_nombre.cget("text")
    finally:
        op.cancelar()


def test_opciones_grabar_con_gancho_falso(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t

    class AppConGancho(AppModo):
        def __init__(self, tmp_path):
            super().__init__(tmp_path, "2D")
            self.grabando = None
            self.cancelado = 0

        def grabar_tecla(self, cb):
            self.grabando = cb
            return True

        def cancelar_grabar(self):
            self.cancelado += 1

    app = AppConGancho(tmp_path)
    op = VentanaOpciones(root, app)
    op._tecla_numerico(False)
    assert op.lbl_tecla_estado.cget("text") == t("op_grabando")
    app.grabando(("grabada", 0x7B, 0x58, False))
    assert op.cfg["tecla_clic"]["vk"] == 0x7B
    op.cancelar()
    assert app.cancelado >= 1


def test_asistente_pasos_nuevos_en_su_orden():
    from lycan_mouse_control.ui.asistente import PASOS_ACTIVOS, pasos_para
    for modo, n in (("2D", 13), ("3D", 16)):
        claves = [p.clave for p in pasos_para(modo)]
        assert len(claves) == n
        assert claves.index("clic_anular") == claves.index("clic") + 1
        assert claves.index("tecla") == claves.index("derecho") + 1
        assert claves[-1] == "pausar"
    assert "clic_anular" in PASOS_ACTIVOS and "tecla" in PASOS_ACTIVOS


def test_asistente_cuenta_con_las_cuentas_de_la_maquina():
    from lycan_mouse_control.ui.asistente import contar_logros
    extra = {}
    assert contar_logros("clic_anular", [], Vista(cuentas={"anular": 5}), extra) == 0
    assert contar_logros("clic_anular", [], Vista(cuentas={"anular": 6}), extra) == 1
    assert contar_logros("clic_anular", [], Vista(cuentas={"anular": 1}), extra) == 2   # el motor se rearmó
    # los botones que salen no cuentan para la tecla (con el asistente al frente no salen)
    ev = [(0, ("boton", "izq", True))] * 3
    extra = {}
    assert contar_logros("tecla", ev, Vista(cuentas={"tecla": 0}), extra) == 0
    assert contar_logros("tecla", ev, Vista(cuentas={"tecla": 2}), extra) == 2


def test_asistente_paso_tecla_si_no_y_no_quiero(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("tecla")
        a._mostrar()
        bombear(root, 30)
        assert a.lbl_texto.cget("text") == t("as_tecla")
        assert str(a.b_sig.cget("state")) == "disabled"
        textos = _textos(a.extra)
        assert t("op_si") in textos and t("op_no") in textos and t("as_tecla_saltar") in textos
        a._tecla_si()
        tc = app.cfg.datos["tecla_clic"]
        assert tc["numerico"] is True and tc["preguntado"] is True and tc["activa"] is True
        assert a.lbl_tecla.cget("text") == t("as_tecla_si")
        assert app.ordenes[-1][0] == "config"
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"tecla": 0}, imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 120)
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"tecla": 2}, imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 150)
        assert str(a.b_sig.cget("state")) == "normal"
        # «No»: sin gancho lo dice
        a._mostrar()
        a._tecla_no()
        assert a.lbl_tecla.cget("text") == t("op_tecla_sin_gancho")
        a._al_grabar_tecla(("grabada", 0x7A, 0x57, False))
        assert app.cfg.datos["tecla_clic"]["vk"] == 0x7A
        # «No quiero»: apaga la tecla y deja seguir
        a._mostrar()
        a._tecla_no_quiero()
        assert app.cfg.datos["tecla_clic"]["activa"] is False
        assert str(a.b_sig.cget("state")) == "normal"
    finally:
        a.cerrar()


def test_asistente_paso_clic_anular_dibuja_y_cuenta(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("clic_anular")
        a._mostrar()
        assert a.lbl_texto.cget("text") == t("as_clic_anular")
        assert a.dibujo.find_all()
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"anular": 3}, imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 120)
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"anular": 5}, imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 150)
        assert str(a.b_sig.cget("state")) == "normal"
    finally:
        a.cerrar()


def test_ayuda_muestra_anular_menique_y_tecla(root):
    from lycan_mouse_control.ui.ayuda import VentanaAyuda
    from lycan_mouse_control.ui.textos import t
    for modo in ("2D", "3D"):
        v = VentanaAyuda(root, modo, False)
        textos = _textos(v.win)
        v.win.destroy()
        assert t("ch_anular") in textos and t("ch_menique") in textos
        assert sum(1 for x in textos if x == t("ch_anular")) == 1      # sin repetir en 3D
        assert any(t("tema_tecla") in x for x in textos)


def test_textos_nuevos_sin_jerga_y_avisos():
    from lycan_mouse_control.acciones import Aviso
    from lycan_mouse_control.ui.textos import PALABRAS_PROHIBIDAS, TXT, texto_aviso
    nuevos = [k for k in TXT if k.startswith(("op_clic", "op_tecla", "op_menique", "mq_", "as_tecla", "ch_anular",
                                              "ch_menique", "ch_tecla", "aviso_tecla", "aviso_gancho",
                                              "aviso_menique", "sena_PELLIZCO_", "sena_menique"))]
    assert len(nuevos) > 20
    for k in nuevos:
        assert not any(p in TXT[k].lower() for p in PALABRAS_PROHIBIDAS), k
    assert texto_aviso(Aviso("menique", "deshacer")) == "Meñique: Deshacer (Ctrl+Z)"
    assert texto_aviso(Aviso("tecla_suelta")) == TXT["aviso_tecla_suelta"]
    assert texto_aviso(Aviso("gancho_perdido")) == TXT["aviso_gancho_perdido"]


def test_manejadores_aceptan_llamarse_sin_evento(root, tmp_path):
    """Los comandos de la pestaña Clic y del paso de la tecla se pueden llamar sin evento."""
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "2D")
    app.root = root
    op = VentanaOpciones(root, app)
    try:
        botones = []

        def buscar(w):
            for h in w.winfo_children():
                if isinstance(h, (tk.Button, tk.Radiobutton, tk.Checkbutton)):
                    botones.append(h)
                buscar(h)
        nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
        buscar(nb.nametowidget(nb.tabs()[3]))
        assert botones
        for b in botones:
            b.invoke()
    finally:
        op.cancelar()
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("tecla")
        a._mostrar()
        bs = [h for h in a.extra.winfo_children()[0].winfo_children() if isinstance(h, tk.Button)]
        assert len(bs) == 3
        for b in bs:
            b.invoke()
    finally:
        a.cerrar()
