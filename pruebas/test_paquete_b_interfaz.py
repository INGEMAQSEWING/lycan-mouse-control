"""1.0.2 paquete B «Girar con un puño»: interfaz (pestaña Girar de Opciones, asistente, ayuda y textos).

Sin cámara: los cambios se revisan en la configuración de la ventana y en la falsa app.
"""
import tkinter as tk
from tkinter import ttk

import numpy as np

from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Aviso
from lycan_mouse_control.motor import Vista
from test_interfaz import bombear
from test_paquete_a_interfaz import _textos
from test_ronda1_interfaz import AppModo, root  # noqa: F401 - fixture


def _abrir_girar(root, app):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    op = VentanaOpciones(root, app)
    nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
    nombres = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
    i = nombres.index(t("op_girar"))
    nb.select(i)
    bombear(root, 80)
    op.win.update_idletasks()
    return op, nb.nametowidget(nb.tabs()[i]), i, nombres


def _combos(w, out=None):
    out = [] if out is None else out
    for h in w.winfo_children():
        if isinstance(h, ttk.Combobox):
            out.append(h)
        _combos(h, out)
    return out


def test_pestana_girar_en_su_lugar_y_con_sus_textos(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "3D")
    op, f, i, nombres = _abrir_girar(root, app)
    try:
        assert i == nombres.index(t("op_clic")) + 1           # justo después de «Clic»
        textos = _textos(f)
        for clave in ("op_girar_con", "op_k_un_puno", "op_inercia", "op_friccion", "op_golpe", "op_programa",
                      "op_abrir_golpe", "op_cerrar_golpe", "ay_edwin3d_desdoblar"):
            assert t(clave) in textos, clave
        nota = next(h for h in f.winfo_children() if isinstance(h, tk.Label)
                    and h.cget("text") == t("ay_edwin3d_desdoblar"))
        assert nota.winfo_ismapped()
        # cabe entera en la pestaña (nada cortado por abajo)
        assert nota.winfo_y() + nota.winfo_height() <= f.winfo_height() + 1, (nota.winfo_y(), f.winfo_height())
        valores = [tuple(c.cget("values")) for c in _combos(f)]
        assert (t("gi_un_puno"), t("gi_dos_punos"), t("gi_ambos")) in valores
    finally:
        op.cancelar()


def test_pestana_girar_cabe_en_1024x768(root, tmp_path):
    app = AppModo(tmp_path, "3D")
    op, f, _i, _n = _abrir_girar(root, app)
    try:
        assert op.win.winfo_reqwidth() <= 1024 and op.win.winfo_reqheight() <= 768 - 60
        assert f.winfo_reqheight() <= f.winfo_height() + 1, (f.winfo_reqheight(), f.winfo_height())
        cortadas = [h.cget("text") for h in f.winfo_children() if isinstance(h, tk.Label) and h.winfo_ismapped()
                    and h.winfo_width() + 2 < h.winfo_reqwidth()]
        assert not cortadas, cortadas
    finally:
        op.cancelar()


def test_girar_con_y_casillas_cambian_la_config(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "3D")
    op, f, _i, _n = _abrir_girar(root, app)
    try:
        cb = next(c for c in _combos(f) if t("gi_ambos") in c.cget("values"))
        assert cb.get() == t("gi_un_puno")
        cb.set(t("gi_dos_punos"))
        cb.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op.cfg["orbita"]["girar"] == "dos_punos"
        op.guardar()
        assert app.cfg.datos["orbita"]["girar"] == "dos_punos"
        assert app.ordenes[-1][0] == "config" and app.ordenes[-1][1]["orbita"]["girar"] == "dos_punos"
    finally:
        try:
            op.win.destroy()
        except tk.TclError:
            pass


def test_atajos_de_golpe_por_programa(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "3D")
    op, f, _i, _n = _abrir_girar(root, app)
    try:
        assert op._programa_golpe() == "edwin3d"
        assert op._ent_golpe["abrir_golpe"].get() == "" and op._ent_golpe["cerrar_golpe"].get() == ""
        op._ent_golpe["abrir_golpe"].set("Ctrl+Alt+U")
        op._poner_atajo_golpe("abrir_golpe")
        assert op.cfg["gestos"]["por_programa"]["edwin3d"]["abrir_golpe"] == "Ctrl+Alt+U"
        assert op.lbl_golpe.cget("text") == ""
        # un atajo que no se entiende no se guarda y se avisa
        op._ent_golpe["cerrar_golpe"].set("Ctrl+Patata")
        op._poner_atajo_golpe("cerrar_golpe")
        assert op.lbl_golpe.cget("text") == t("op_atajo_malo")
        assert "cerrar_golpe" not in op.cfg["gestos"]["por_programa"]["edwin3d"]
        # otro programa muestra lo suyo
        cbp = next(c for c in _combos(f) if "SketchUp" in c.cget("values"))
        cbp.set("SketchUp")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op._programa_golpe() == "sketchup" and op._ent_golpe["abrir_golpe"].get() == ""
        op._ent_golpe["cerrar_golpe"].set("Ctrl+G")
        op._poner_atajo_golpe("cerrar_golpe")
        cbp.set("EDWIN CNC 3D")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op._ent_golpe["abrir_golpe"].get() == "Ctrl+Alt+U"
        op.guardar()
        pp = app.cfg.datos["gestos"]["por_programa"]
        assert pp["edwin3d"] == {"abrir_golpe": "Ctrl+Alt+U"} and pp["sketchup"] == {"cerrar_golpe": "Ctrl+G"}
    finally:
        try:
            op.win.destroy()
        except tk.TclError:
            pass


def test_manejadores_de_girar_aceptan_llamarse_sin_evento(root, tmp_path):
    app = AppModo(tmp_path, "3D")
    op, f, _i, _n = _abrir_girar(root, app)
    try:
        botones = []

        def buscar(w):
            for h in w.winfo_children():
                if isinstance(h, (tk.Button, tk.Radiobutton, tk.Checkbutton)):
                    botones.append(h)
                buscar(h)
        buscar(f)
        assert len(botones) >= 2
        for b in botones:
            b.invoke()
        for c in _combos(f):
            c.event_generate("<<ComboboxSelected>>")
        for e in [h for h in f.winfo_children() for h in h.winfo_children() if isinstance(h, tk.Entry)]:
            e.event_generate("<KeyRelease>")
            e.event_generate("<FocusOut>")
        bombear(root, 30)
        op._mostrar_atajos_golpe()
        op._poner_atajo_golpe("abrir_golpe")
    finally:
        op.cancelar()


def test_asistente_paso_girar_segun_la_opcion(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente, pasos_para
    from lycan_mouse_control.ui.textos import t
    for modo, n in (("2D", 13), ("3D", 16)):
        for girar in ("un_puno", "dos_punos", "ambos"):
            assert len(pasos_para(modo, girar)) == n
    por = {p.clave: p for p in pasos_para("3D")}
    assert por["girar"].texto == "as_girar_un_puno" and por["girar"].pista == "pista_girar_un_puno"
    assert {p.clave: p for p in pasos_para("3D", "ambos")}["girar"].texto == "as_girar_un_puno"
    assert {p.clave: p for p in pasos_para("3D", "dos_punos")}["girar"].texto == "as_girar"
    for girar, texto, ancho in (("un_puno", "as_girar_un_puno", 120), ("dos_punos", "as_girar", 230)):
        app = AppModo(tmp_path, "3D")
        app.root = root
        app.cfg.datos["orbita"]["girar"] = girar
        a = Asistente(root, app)
        try:
            a.i = [p.clave for p in a.pasos].index("girar")
            a._mostrar()
            bombear(root, 30)
            assert a.lbl_texto.cget("text") == t(texto)
            assert int(a.dibujo.cget("width")) == ancho      # un puño: se dibuja una sola mano
        finally:
            a.cerrar()


def test_asistente_cuenta_el_giro_con_un_puno():
    from lycan_mouse_control.ui.asistente import contar_logros
    ev = [(0, ("boton", "medio", True))] + [(0, ("mover", 10 * k, 0)) for k in range(12)]
    assert contar_logros("girar", ev, Vista(modo="3D"), {}) == 1


def test_ayuda_de_3d_segun_la_opcion(root):
    from lycan_mouse_control.ui.ayuda import VentanaAyuda, filas_3d
    from lycan_mouse_control.ui.textos import t
    claves = [c for _, c in filas_3d()]
    assert "ch_girar_un_puno" in claves and "ch_girar" not in claves and "ch_lanzar" not in claves
    assert "ch_lanzar" in [c for _, c in filas_3d("un_puno", True)]
    claves = [c for _, c in filas_3d("dos_punos", True)]
    assert "ch_girar" in claves and "ch_girar_un_puno" not in claves and "ch_lanzar" not in claves
    claves = [c for _, c in filas_3d("ambos")]
    assert "ch_girar" in claves and "ch_girar_un_puno" in claves
    v = VentanaAyuda(root, "3D", False, girar="un_puno", inercia=True)
    textos = _textos(v.win)
    v.win.destroy()
    assert t("ch_girar_un_puno") in textos and t("ch_lanzar") in textos
    assert any(t("ch_golpe") in x for x in textos)
    v = VentanaAyuda(root, "2D", False)
    textos = _textos(v.win)
    v.win.destroy()
    assert t("ch_girar_un_puno") not in textos and any(t("ch_golpe") in x for x in textos)


def test_ventana_principal_muestra_las_etiquetas_nuevas(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    app = AppModo(tmp_path, "3D")
    v = VentanaPrincipal(root, app)
    for etiqueta in ("girar", "lanzar", "despiezar", "armar", "soltar"):
        assert t("sena_" + etiqueta) != "sena_" + etiqueta
        app.motor.vistas.put(Vista(estado=K.GIRANDO_3D, modo="3D", etiqueta=etiqueta,
                                   imagen=np.zeros((240, 320, 3), np.uint8)))
        bombear(root, 120)
        assert t("sena_" + etiqueta) in _textos(root), etiqueta
    app.cerrando = True


def test_textos_nuevos_sin_jerga_y_avisos():
    from lycan_mouse_control.ui.textos import PALABRAS_PROHIBIDAS, TXT, texto_aviso
    nuevos = [k for k in TXT if k.startswith(("op_girar", "gi_", "op_k_un_puno", "op_inercia", "op_friccion",
                                              "op_golpe", "op_programa", "op_abrir_golpe", "op_cerrar_golpe",
                                              "ay_girar", "ay_inercia", "ay_atajo", "ay_edwin3d", "op_atajo_malo",
                                              "ch_girar_un_puno", "ch_lanzar", "ch_golpe", "as_girar_un_puno",
                                              "pista_girar_un_puno", "aviso_girando", "aviso_inercia",
                                              "aviso_frenado", "aviso_golpe", "sena_girar_un_puno"))]
    assert len(nuevos) >= 25
    for k in nuevos:
        assert not any(p in TXT[k].lower() for p in PALABRAS_PROHIBIDAS), k
    assert texto_aviso(Aviso("golpe_abrir", "Ctrl+Alt+U")) == "Despiezar: Ctrl+Alt+U"
    assert texto_aviso(Aviso("golpe_cerrar", "Ctrl+G")) == "Armar: Ctrl+G"
    assert texto_aviso(Aviso("inercia")) == TXT["aviso_inercia"]
    assert texto_aviso(Aviso("frenado")) == TXT["aviso_frenado"]
    assert "puño" in TXT["aviso_modo_3D"]
