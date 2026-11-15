"""1.0.2 paquete C «Palma y comodidad»: interfaz (pestaña Palma y casilla de Comodidad en Opciones,
asistente, calibración con la mano baja, ayuda, ventana principal y textos).

Sin cámara: los cambios se revisan en la configuración de la ventana y en la falsa app.
"""
import tkinter as tk
from tkinter import ttk

import numpy as np
import pytest

from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Aviso
from lycan_mouse_control.motor import Vista
from test_interfaz import AppFalsa, bombear
from test_paquete_a_interfaz import _textos
from test_paquete_b_interfaz import _combos
from test_ronda1_interfaz import AppModo, root  # noqa: F401 - fixture


def _abrir_pestana(root, app, clave):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    op = VentanaOpciones(root, app)
    nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
    nombres = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
    i = nombres.index(t(clave))
    nb.select(i)
    bombear(root, 80)
    op.win.update_idletasks()
    return op, nb.nametowidget(nb.tabs()[i]), i, nombres


def _cerrar(op):
    try:
        op.win.destroy()
    except tk.TclError:
        pass


def _casilla(f, clave):
    """El Checkbutton de la fila cuyo texto es t(clave)."""
    from lycan_mouse_control.ui.textos import t
    for fila in f.winfo_children():
        hijos = fila.winfo_children()
        if any(isinstance(h, tk.Label) and h.cget("text") == t(clave) for h in hijos):
            return next(h for h in hijos if isinstance(h, tk.Checkbutton))
    raise AssertionError(clave)


# =============================================================== Opciones: pestaña «Palma»
def test_pestana_palma_en_su_lugar_y_con_sus_textos(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op, f, i, nombres = _abrir_pestana(root, app, "op_palma")
    try:
        assert nombres == [t("op_general"), t("op_puntero"), t("op_senas"), t("op_clic"), t("op_girar"),
                           t("op_palma"), t("op_comodidad"), t("op_atajos")]
        assert i == nombres.index(t("op_girar")) + 1
        textos = _textos(f)
        for clave in ("op_scroll_palma", "op_scroll_inercia", "op_scroll_friccion", "op_scroll_invertir",
                      "op_barrido", "op_programa", "op_barrido_der", "op_barrido_izq"):
            assert t(clave) in textos, clave
        assert op._ent_barrido["barrido_der"].get() == "Derecha"
        assert op._ent_barrido["barrido_izq"].get() == "Izquierda"
    finally:
        op.cancelar()


@pytest.mark.parametrize("clave", ["op_palma", "op_comodidad"])
@pytest.mark.parametrize("modo", ["2D", "3D"])
def test_pestanas_nuevas_caben_en_1024x768(root, tmp_path, clave, modo):
    app = AppModo(tmp_path, modo)
    op, f, _i, _n = _abrir_pestana(root, app, clave)
    try:
        assert op.win.winfo_reqwidth() <= 1024 and op.win.winfo_reqheight() <= 768 - 60
        assert f.winfo_reqheight() <= f.winfo_height() + 1, (f.winfo_reqheight(), f.winfo_height())
        cortadas = []

        def revisar(w):
            for h in w.winfo_children():
                if isinstance(h, tk.Label) and h.cget("text") and h.winfo_ismapped() \
                        and h.winfo_width() + 2 < h.winfo_reqwidth():
                    cortadas.append(h.cget("text"))
                revisar(h)
        revisar(f)
        assert not cortadas, cortadas
        ultimo = max((h for h in f.winfo_children() if h.winfo_ismapped()),
                     key=lambda h: h.winfo_y() + h.winfo_height())
        assert ultimo.winfo_y() + ultimo.winfo_height() <= f.winfo_height() + 1
    finally:
        op.cancelar()


def test_casillas_de_la_palma_cambian_la_config(root, tmp_path):
    app = AppModo(tmp_path, "2D")
    op, f, _i, _n = _abrir_pestana(root, app, "op_palma")
    try:
        for clave, ruta, antes in (("op_scroll_palma", ("scroll", "palma"), True),
                                   ("op_scroll_inercia", ("scroll", "inercia"), True),
                                   ("op_scroll_invertir", ("scroll", "invertir"), False),
                                   ("op_barrido", ("gestos", "barrido"), True)):
            assert op.cfg[ruta[0]][ruta[1]] is antes
            _casilla(f, clave).invoke()
            assert op.cfg[ruta[0]][ruta[1]] is (not antes), clave
        op.guardar()
        d = app.cfg.datos
        assert d["scroll"]["palma"] is False and d["scroll"]["invertir"] is True
        assert d["gestos"]["barrido"] is False
        assert app.ordenes[-1][0] == "config" and app.ordenes[-1][1]["scroll"]["inercia"] is False
    finally:
        _cerrar(op)


def test_teclas_del_barrido_por_programa(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op, f, _i, _n = _abrir_pestana(root, app, "op_palma")
    try:
        cbp = next(c for c in _combos(f) if "Navegador de internet" in c.cget("values"))
        assert op._programa_barrido() == "generico"
        # dejar lo de fábrica no guarda nada
        op._poner_atajo_barrido("barrido_der")
        assert "generico" not in op.cfg["gestos"]["por_programa"]
        cbp.set("Navegador de internet")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op._ent_barrido["barrido_der"].get() == "Alt+Derecha"
        cbp.set("EDWIN CNC CAD-CAM")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        assert op._ent_barrido["barrido_der"].get() == "" and op._ent_barrido["barrido_izq"].get() == ""
        op._ent_barrido["barrido_der"].set("Ctrl+Tab")
        op._poner_atajo_barrido("barrido_der")
        assert op.cfg["gestos"]["por_programa"]["edwin2d"] == {"barrido_der": "Ctrl+Tab"}
        # una tecla que no se entiende no se guarda y se avisa
        op._ent_barrido["barrido_izq"].set("Ctrl+Patata")
        op._poner_atajo_barrido("barrido_izq")
        assert op.lbl_barrido.cget("text") == t("op_atajo_malo")
        assert "barrido_izq" not in op.cfg["gestos"]["por_programa"]["edwin2d"]
        # vaciar la del genérico = el barrido no hace nada allí
        cbp.set("Genérico")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        op._ent_barrido["barrido_izq"].set("")
        op._poner_atajo_barrido("barrido_izq")
        op.guardar()
        pp = app.cfg.datos["gestos"]["por_programa"]
        assert pp["edwin2d"] == {"barrido_der": "Ctrl+Tab"} and pp["generico"] == {"barrido_izq": ""}
    finally:
        _cerrar(op)


def test_barrido_y_golpe_conviven_en_por_programa(root, tmp_path):
    """La pestaña Girar (golpe) y la pestaña Palma (barrido) escriben en el mismo diccionario."""
    app = AppModo(tmp_path, "3D")
    op, f, _i, _n = _abrir_pestana(root, app, "op_palma")
    try:
        op._ent_golpe["abrir_golpe"].set("Ctrl+Alt+U")
        op._poner_atajo_golpe("abrir_golpe")                    # programa: EDWIN CNC 3D
        cbp = next(c for c in _combos(f) if "EDWIN CNC 3D" in c.cget("values"))
        cbp.set("EDWIN CNC 3D")
        cbp.event_generate("<<ComboboxSelected>>")
        bombear(root, 30)
        op._ent_barrido["barrido_der"].set("AvPág")
        op._poner_atajo_barrido("barrido_der")
        op.guardar()
        assert app.cfg.datos["gestos"]["por_programa"]["edwin3d"] == {"abrir_golpe": "Ctrl+Alt+U",
                                                                     "barrido_der": "AvPág"}
    finally:
        _cerrar(op)


def test_manejadores_de_palma_y_comodidad_aceptan_llamarse_sin_evento(root, tmp_path):
    app = AppModo(tmp_path, "2D")
    for clave in ("op_palma", "op_comodidad"):
        op, f, _i, _n = _abrir_pestana(root, app, clave)
        try:
            botones = []

            def buscar(w):
                for h in w.winfo_children():
                    if isinstance(h, (tk.Button, tk.Radiobutton, tk.Checkbutton)):
                        botones.append(h)
                    buscar(h)
            buscar(f)
            assert botones
            for b in botones:
                b.invoke()
            for c in _combos(f):
                c.event_generate("<<ComboboxSelected>>")
            for e in [h for h in f.winfo_children() for h in h.winfo_children() if isinstance(h, tk.Entry)]:
                e.event_generate("<KeyRelease>")
                e.event_generate("<FocusOut>")
            bombear(root, 30)
            if clave == "op_palma":
                op._mostrar_atajos_barrido()
                op._poner_atajo_barrido("barrido_der")
                op._poner_atajo_barrido("barrido_izq")
        finally:
            op.cancelar()


def test_casilla_mano_baja_en_comodidad(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op, f, _i, _n = _abrir_pestana(root, app, "op_comodidad")
    try:
        assert t("op_mano_baja") in _textos(f)
        assert op.cfg["zona"]["mano_baja"] is False
        _casilla(f, "op_mano_baja").invoke()
        assert op.cfg["zona"]["mano_baja"] is True
        op.guardar()
        assert app.cfg.datos["zona"]["mano_baja"] is True
    finally:
        _cerrar(op)


def test_opciones_con_config_vieja_sin_claves_de_la_palma(root, tmp_path):
    """Una configuración en memoria sin las claves nuevas (por ejemplo, de antes de validar) no
    rompe la ventana."""
    app = AppModo(tmp_path, "2D")
    del app.cfg.datos["scroll"]
    del app.cfg.datos["gestos"]["barrido"]
    del app.cfg.datos["zona"]["mano_baja"]
    op, f, _i, _n = _abrir_pestana(root, app, "op_palma")
    try:
        assert op.cfg["scroll"]["palma"] is True and op.cfg["zona"]["mano_baja"] is False
    finally:
        op.cancelar()


# =============================================================== asistente
def test_asistente_paso_scroll_en_su_lugar():
    from lycan_mouse_control.ui.asistente import CUENTAS_MAQUINA, PASOS_ACTIVOS, pasos_para
    for modo, n in (("2D", 14), ("3D", 17)):
        for girar in ("un_puno", "dos_punos", "ambos"):
            claves = [p.clave for p in pasos_para(modo, girar)]
            assert len(claves) == n
            assert claves.index("scroll") == claves.index("zoom") + 1
            assert claves[-1] == "pausar"
    por = {p.clave: p for p in pasos_para("2D")}
    assert por["scroll"].meta == 1 and por["scroll"].texto == "as_scroll" and por["scroll"].pista == "pista_scroll"
    assert por["postura"].tipo == "postura"
    assert "scroll" in PASOS_ACTIVOS and CUENTAS_MAQUINA["scroll"] == "scroll"


def test_asistente_cuenta_el_scroll_con_la_maquina():
    from lycan_mouse_control.ui.asistente import contar_logros
    extra = {}
    assert contar_logros("scroll", [(0, ("rueda", -120))] * 5, Vista(cuentas={"scroll": 2}), extra) == 0
    assert contar_logros("scroll", [], Vista(cuentas={"scroll": 3}), extra) == 1


def test_asistente_postura_con_dos_botones(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("postura")
        a._mostrar()
        bombear(root, 30)
        textos = _textos(a.extra)
        for clave in ("as_postura_elegir", "as_postura_apoyado", "as_postura_baja"):
            assert t(clave) in textos, clave
        assert str(a.b_sig.cget("state")) == "normal"          # se puede seguir sin escoger
        baja = next(b for b in a.extra.winfo_children()[1].winfo_children()
                    if b.cget("text") == t("as_postura_baja"))
        baja.invoke()
        assert app.cfg.datos["zona"]["mano_baja"] is True
        assert a.lbl_postura.cget("text") == t("as_consejo_baja")
        assert app.ordenes[-1][0] == "config" and app.ordenes[-1][1]["zona"]["mano_baja"] is True
        a._poner_postura(False)
        assert app.cfg.datos["zona"]["mano_baja"] is False and a.lbl_postura.cget("text") == ""
        # al volver al paso, si eligió mano baja, el consejo sigue a la vista
        a._poner_postura(True)
        a._mostrar()
        assert a.lbl_postura.cget("text") == t("as_consejo_baja")
        # el consejo cabe sin cortarse
        a.win.update_idletasks()
        assert a.lbl_postura.winfo_width() + 2 >= a.lbl_postura.winfo_reqwidth()
    finally:
        a.cerrar()


def test_asistente_paso_scroll_se_logra(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("scroll")
        a._mostrar()
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"scroll": 0})
        bombear(root, 100)
        assert str(a.b_sig.cget("state")) == "disabled" and a.lbl_texto.cget("text") == t("as_scroll")
        app.ultima_vista = Vista(estado=K.PASANDO_PAGINA, cuentas={"scroll": 1})
        bombear(root, 150)
        assert str(a.b_sig.cget("state")) == "normal"
    finally:
        a.cerrar()


# =============================================================== calibración con la mano baja
def test_calibracion_revisa_la_muneca_con_la_mano_baja(root, tmp_path):
    from lycan_mouse_control.ui import calibracion as UC
    from lycan_mouse_control.ui.textos import t
    app = AppFalsa(tmp_path)
    app.cfg.datos["zona"]["mano_baja"] = True
    app.ultima_vista = Vista(estado=K.PAUSA, brillo=120.0, ancho_mano=0.28, punta=(0.5, 0.6),
                             muneca=(0.5, 0.99), alto_mano=0.3, medidas={"p": 0.3, "s": 1.0, "a": 5.0})
    c = UC.Calibracion(root, app, lambda ok: None)
    try:
        assert c._mano_baja()
        c._munecas = [0.99] * 10
        assert not c.revisar_muneca()
        assert c.lbl_info.cget("text") == t("cal_incline") and c._munecas == []
        c._munecas = [0.90] * 10
        assert c.revisar_muneca()
        assert c.lbl_info.cget("text") == t("cal_mano_baja_ok")
    finally:
        c.destroy()


def test_calibracion_con_mano_baja_no_deja_salir_la_muneca(root, tmp_path, monkeypatch):
    from lycan_mouse_control import calibracion as CAL
    from lycan_mouse_control.ui import calibracion as UC
    app = AppFalsa(tmp_path)
    app.cfg.datos["zona"]["mano_baja"] = True
    monkeypatch.setattr(CAL, "calcular_umbrales", lambda muestras, actual: (dict(actual), []))
    fin = []
    c = UC.Calibracion(root, app, fin.append)
    try:
        rng = np.random.default_rng(3)
        c.puntos = [tuple(p) for p in rng.uniform((0.3, 0.55), (0.7, 0.95), (60, 2))]
        c._altos = [0.35] * 9
        c._terminar()
        z = app.cfg.datos["zona"]
        assert fin == [True]
        assert z["y1"] <= 1 - 1.1 * 0.35 + 1e-3 and z["y1"] - z["y0"] >= 0.1
        assert z["mano_baja"] is True
    finally:
        c.destroy()


def test_calibracion_sin_mano_baja_no_recorta(root, tmp_path, monkeypatch):
    from lycan_mouse_control import calibracion as CAL
    from lycan_mouse_control.ui import calibracion as UC
    app = AppFalsa(tmp_path)
    monkeypatch.setattr(CAL, "calcular_umbrales", lambda muestras, actual: (dict(actual), []))
    c = UC.Calibracion(root, app, lambda ok: None)
    try:
        rng = np.random.default_rng(3)
        c.puntos = [tuple(p) for p in rng.uniform((0.3, 0.55), (0.7, 0.95), (60, 2))]
        c._altos = [0.35] * 9
        c._terminar()
        assert app.cfg.datos["zona"]["y1"] > 1 - 1.1 * 0.35
    finally:
        c.destroy()


# =============================================================== ayuda y ventana principal
def test_ayuda_muestra_la_palma_el_barrido_y_la_mano_baja(root):
    from lycan_mouse_control.ui.ayuda import FILAS_2D, TEMAS, VentanaAyuda
    from lycan_mouse_control.ui.textos import t
    assert ("abierta", "ch_palma") in FILAS_2D and ("abierta", "ch_barrido") in FILAS_2D
    assert "ch_mano_baja" in TEMAS
    for modo in ("2D", "3D"):
        v = VentanaAyuda(root, modo, False)
        textos = _textos(v.win)
        v.win.destroy()
        assert t("ch_palma") in textos and t("ch_barrido") in textos
        assert any(t("ch_mano_baja") in x for x in textos)


def test_ventana_principal_muestra_pasando_pagina(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    app = AppModo(tmp_path, "2D")
    v = VentanaPrincipal(root, app)
    app.motor.vistas.put(Vista(estado=K.PASANDO_PAGINA, modo="2D", imagen=np.zeros((240, 320, 3), np.uint8)))
    bombear(root, 150)
    assert v.lbl_estado.cget("text") == t("estado_PASANDO_PAGINA")
    assert str(root.cget("bg")).lower() == K.COLORES_ESTADO[K.PASANDO_PAGINA].lower()
    for etiqueta in ("pasando", "barrido_der", "barrido_izq", "scroll_fin"):
        assert t("sena_" + etiqueta) != "sena_" + etiqueta
        app.motor.vistas.put(Vista(estado=K.ACTIVO, modo="2D", etiqueta=etiqueta,
                                   imagen=np.zeros((240, 320, 3), np.uint8)))
        bombear(root, 120)
        assert t("sena_" + etiqueta) in _textos(root), etiqueta
    app.cerrando = True


def test_indicador_tiene_palabras_para_lo_nuevo():
    from lycan_mouse_control.ui.indicador_cursor import PALABRAS, PALABRAS_ESTADO
    assert K.PASANDO_PAGINA in PALABRAS_ESTADO
    for k in ("pasando", "barrido_der", "barrido_izq"):
        assert k in PALABRAS


# =============================================================== textos
def test_textos_nuevos_sin_jerga_y_avisos():
    from lycan_mouse_control.ui.textos import PALABRAS_PROHIBIDAS, TXT, texto_aviso
    nuevos = [k for k in TXT if k.startswith((
        "estado_pasando", "ayuda_pasando", "estado_PASANDO", "ayuda_PASANDO", "sena_palma", "sena_pasando",
        "sena_scroll", "sena_barrido", "ch_palma", "ch_barrido", "ch_mano_baja", "op_palma", "op_scroll",
        "ay_scroll", "op_barrido", "ay_barrido", "op_mano_baja", "ay_mano_baja", "as_postura_", "as_consejo",
        "as_scroll", "pista_scroll", "cal_incline", "cal_mano_baja", "aviso_scroll", "aviso_barrido",
        "aviso_baje"))]
    assert len(nuevos) >= 35, len(nuevos)
    for k in nuevos:
        assert not any(p in TXT[k].lower() for p in PALABRAS_PROHIBIDAS), k
    assert texto_aviso(Aviso("scroll")) == "Pasando página: suba o baje la mano"
    assert texto_aviso(Aviso("scroll_fin")) == "Listo"
    assert texto_aviso(Aviso("barrido_der")) == "Siguiente"
    assert texto_aviso(Aviso("barrido_izq")) == "Anterior"
    assert texto_aviso(Aviso("baje_mano")) == "Baje la mano hasta la zona del teclado"
    # los textos exactos del plan
    assert TXT["op_scroll_palma"] == "Pasar página con la palma"
    assert TXT["ch_palma"].startswith("Muestre la palma abierta y quieta")
    assert TXT["cal_incline"] == "No se ve su muñeca. Incline la pantalla hacia atrás o la cámara hacia abajo."


def test_version_1_0_2():
    from lycan_mouse_control.version import VERSION
    assert VERSION == "1.0.2"
