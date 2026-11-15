"""Revisión de la 1.0.2 (tres revisores): confusiones entre señas, tecla de clic e interfaz.

Todo con manos sintéticas y la configuración en una carpeta temporal; nunca se abre la cámara.
"""
import tkinter as tk

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles as P
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.acciones import MoverDelta, Rueda
from lycan_mouse_control.motor import Vista
from test_interfaz import bombear
from test_paquete_a_interfaz import _textos
from test_ronda1_interfaz import AppModo, root  # noqa: F401 - fixture

C = (0.55, 0.50)
ATAJOS = {"abrir_golpe": "Ctrl+Alt+U", "cerrar_golpe": "Ctrl+Alt+J"}


def preparar(modo="3D", perfil="edwin3d", cfg=None, fps=30.0):
    sim = Sim(modo=modo, perfil=perfil, cfg=cfg, fps=fps)
    sim.activar(C)
    sim.durante(600, s.en("apuntar", C))
    return sim


def bajadas_izq(sim, desde):
    return [t for t, ev in sim.salida.eventos if t >= desde and ev == ("boton", "izq", True)]


def medio(sim, desde=0.0):
    return [ev[2] for t, ev in sim.salida.eventos if t >= desde and ev[0] == "boton" and ev[1] == "medio"]


def derecho(sim, desde=0.0):
    return [t for t, ev in sim.salida.eventos if t >= desde and ev == ("boton", "der", True)]


def pulsados(sim, desde=0.0):
    return [ev[1] for t, ev in sim.salida.eventos if t >= desde and ev[0] == "pulsar"]


def cuadros(sim, manos):
    for m in manos:
        sim.cuadro(m)


# =============================================================== 1: meñique sin clics de más
def _ir_y_volver_del_menique(sim, n, rot):
    def m(p):
        return s.mano(p, posicion=C, ancla="centro", rot=rot)
    sim.durante(400, m(s.construir("apuntar")))
    for k in range(1, n + 1):
        sim.cuadro(m(s.intermedia("apuntar", "pellizco_menique", k / n)))
    sim.durante(400, m(s.construir("pellizco_menique")))
    for k in range(1, n + 1):
        sim.cuadro(m(s.intermedia("pellizco_menique", "apuntar", k / n)))
    sim.durante(400, m(s.construir("apuntar")))


@pytest.mark.parametrize("fps", [30.0, 15.0])
@pytest.mark.parametrize("n", [4, 8, 10, 12, 15, 20])
@pytest.mark.parametrize("rot", [(0, 0, 0), (30, 0, -20), (25, 0, -15)])
def test_apuntar_menique_apuntar_es_solo_el_doble_clic(fps, n, rot):
    """El pulgar pasa por encima del anular camino al meñique (y al volver): eso no es un clic."""
    sim = preparar(modo="2D", perfil="generico", fps=fps)
    t0 = sim.t
    _ir_y_volver_del_menique(sim, n, rot)
    assert len(bajadas_izq(sim, t0)) == 2          # exactamente el doble clic
    assert len([1 for t, e in sim.salida.eventos if t >= t0 and e[0] == "boton" and e[1] == "izq"]) == 4


@pytest.mark.parametrize("fps", [30.0, 15.0])
@pytest.mark.parametrize("n", [1, 3, 6, 10])
def test_el_clic_con_el_anular_sigue_funcionando(fps, n):
    sim = preparar(modo="2D", perfil="generico", fps=fps)
    t0 = sim.t
    cuadros(sim, s.transicion("apuntar", "pellizco_anular", n, C))
    sim.durante(200, s.en("pellizco_anular", C))
    cuadros(sim, s.transicion("pellizco_anular", "apuntar", n, C))
    sim.durante(300, s.en("apuntar", C))
    assert len(bajadas_izq(sim, t0)) == 1


def test_arrastre_con_el_anular_no_se_corta():
    sim = preparar(modo="2D", perfil="generico")
    t0 = sim.t
    sim.durante(300, s.en("pellizco_anular", C))
    cuadros(sim, s.trayecto("pellizco_anular", C, (0.70, 0.45), 15))
    sim.durante(200, s.en("pellizco_anular", (0.70, 0.45)))
    sim.durante(300, s.en("apuntar", (0.70, 0.45)))
    izq = [e[2] for t, e in sim.salida.eventos if t >= t0 and e[0] == "boton" and e[1] == "izq"]
    assert izq == [True, False]


def test_con_el_menique_en_nada_el_anular_no_cambia():
    sim = preparar(modo="2D", perfil="generico", cfg={"senas": {"menique": "nada"}})
    t0 = sim.t
    sim.durante(200, s.en("pellizco_anular", C))
    sim.durante(300, s.en("apuntar", C))
    assert len(bajadas_izq(sim, t0)) == 1


# =============================================================== 4: temblor en el puño quieto (3D)
def test_un_cuadro_de_temblor_no_gira_y_sale_el_clic_derecho():
    sim = preparar()
    t0 = sim.t
    sim.durante(100, s.en("puno", C))
    sim.cuadro(s.en("puno", (C[0] + 0.04, C[1])))
    sim.durante(500, s.en("puno", C))
    assert sim.nucleo.maquina.gesto is None and medio(sim, t0) == []
    assert len(derecho(sim, t0)) == 1
    sim.durante(300, s.en("abierta", C))
    assert sim.salida.todo_suelto()


def test_puno_que_se_mueve_de_verdad_sigue_girando():
    sim = preparar()
    t0 = sim.t
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.68, 0.50), 12))
    assert sim.nucleo.maquina.gesto == "orbita1" and medio(sim, t0) == [True]
    assert derecho(sim, t0) == []
    sim.durante(300, s.en("abierta", (0.68, 0.50)))
    assert sim.salida.todo_suelto()


# =============================================================== 5: el giro se suelta al apuntar
@pytest.mark.parametrize("otra", ["apuntar", "pellizco", "v"])
def test_pasar_del_puno_a_otra_sena_suelta_el_giro(otra):
    sim = preparar()
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.65, C[1]), 8))
    assert sim.nucleo.maquina.gesto == "orbita1"
    cuadros(sim, s.transicion("puno", otra, 3, (0.65, C[1])))
    sim.durante(150, s.en(otra, (0.65, C[1])))
    t0 = sim.t
    assert sim.nucleo.maquina.gesto is None and "medio" not in sim.salida.botones_abajo
    cuadros(sim, s.trayecto(otra, (0.65, C[1]), (0.45, 0.40), 20))
    assert not [a for t, a in sim.acciones if t >= t0 and isinstance(a, MoverDelta)]
    sim.durante(300, s.en("apuntar", (0.45, 0.40)))
    assert sim.salida.todo_suelto()


# =============================================================== 2: la palma que soltó el giro
def test_soltar_el_giro_y_mirar_el_modelo_no_hace_zoom():
    sim = preparar()
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.65, C[1]), 8))
    cuadros(sim, s.transicion("puno", "abierta", 3, (0.65, C[1])))
    t0 = sim.t
    sim.durante(2000, s.en("abierta", (0.65, C[1])))
    assert sim.nucleo.maquina.gesto is None
    cuadros(sim, s.trayecto("abierta", (0.65, C[1]), (0.55, 0.62), 5))
    cuadros(sim, s.transicion("abierta", "apuntar", 3, (0.55, 0.62)))
    sim.durante(2000, s.en("apuntar", (0.55, 0.62)))
    assert not [a for t, a in sim.acciones if t >= t0 and isinstance(a, Rueda)]


# =============================================================== 6: cerrar para girar no «arma»
def test_en_3d_cerrar_el_puno_para_girar_no_arma():
    sim = preparar(cfg={"gestos": {"por_programa": {"edwin3d": dict(ATAJOS)}}})
    sim.durante(350, s.en("abierta", C))
    t0 = sim.t
    cuadros(sim, s.transicion("abierta", "puno", 2, C))
    sim.durante(150, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.70, C[1]), 10))
    assert pulsados(sim, t0) == []
    assert sim.nucleo.maquina.gesto == "orbita1" and medio(sim, t0) == [True]
    sim.durante(300, s.en("abierta", (0.70, C[1])))


def test_en_3d_armar_sigue_saliendo_con_el_puno_quieto():
    sim = preparar(cfg={"gestos": {"por_programa": {"edwin3d": dict(ATAJOS)}}})
    sim.durante(350, s.en("abierta", C))
    t0 = sim.t
    cuadros(sim, s.transicion("abierta", "puno", 2, C))
    sim.durante(500, s.en("puno", C))
    assert pulsados(sim, t0) == [("ctrl", "alt", "j")]
    assert derecho(sim, t0) == []                       # armar, no clic derecho
    sim.durante(300, s.en("abierta", C))


# =============================================================== 7: abrir despacio con cámara lenta
def test_el_hueco_del_golpe_tiene_tope():
    sim = preparar(modo="2D", perfil="generico", fps=10.0)
    m = sim.nucleo.maquina
    m._dt_cuadro = 0.1
    assert m._hueco_golpe() == pytest.approx(0.20)
    m._dt_cuadro = 1 / 30
    assert m._hueco_golpe() == pytest.approx(0.15)


# =============================================================== corrección 5 y 8: atajos y config
def test_un_gesto_no_manda_un_atajo_del_programa():
    cfg = {"gestos": {"por_programa": {"generico": {"abrir_golpe": "Ctrl+Alt+X", "barrido_der": "alt+ctrl+m"}}}}
    assert P.gesto_de(P.GENERICO, "abrir_golpe", cfg) is None
    assert P.gesto_de(P.GENERICO, "barrido_der", cfg) is None
    assert P.choca_con_atajos("Ctrl+Alt+K", {"pausar": "Ctrl+Alt+K"}) == "pausar"
    assert P.choca_con_atajos("Ctrl+Alt+M", {"pausar": "Ctrl+Alt+K"}) is None    # ya no es de pausar
    assert P.choca_con_atajos("Ctrl+Shift+G") is None


@pytest.mark.parametrize("vk", [0x10, 0xA0, 0xA1, 0xA2, 0xA5, 0x5B, 0x5C, 0x01, 0x02, 0x05])
def test_config_a_mano_no_acepta_modificadores_ni_botones_como_tecla(vk):
    from lycan_mouse_control.config import validar
    problemas = []
    out = validar({"tecla_clic": {"vk": vk, "scan": 0x2A, "numerico": False, "nombre": "x"}}, problemas=problemas)
    assert out["tecla_clic"]["numerico"] is True and out["tecla_clic"]["vk"] == 0x65
    assert any("tecla_clic.vk" in p for p in problemas)


def test_config_a_mano_con_una_tecla_normal_se_respeta():
    from lycan_mouse_control.config import validar
    out = validar({"tecla_clic": {"vk": 0x7A, "scan": 0x57, "numerico": False, "nombre": "F11"}})
    assert out["tecla_clic"]["vk"] == 0x7A and out["tecla_clic"]["numerico"] is False


# =============================================================== interfaz
def test_asistente_y_chuleta_sin_las_senas_apagadas():
    from lycan_mouse_control.ui.asistente import pasos_para
    from lycan_mouse_control.ui.ayuda import FILAS_2D, filas_3d, filas_segun_config, texto_fila
    from lycan_mouse_control.ui.textos import t
    cfg = {"senas": {"clic_indice": False, "clic_anular": False, "menique": "nada"},
           "scroll": {"palma": False}, "gestos": {"barrido": False}}
    claves = [p.clave for p in pasos_para("2D", "un_puno", cfg)]
    assert "clic" not in claves and "clic_anular" not in claves and "scroll" not in claves
    assert len(pasos_para("2D")) == 14
    filas = [c for _, c in filas_segun_config(FILAS_2D, cfg)]
    for c in ("ch_clic", "ch_arrastrar", "ch_anular", "ch_menique", "ch_palma", "ch_barrido"):
        assert c not in filas
    assert texto_fila("ch_menique", {"senas": {"menique": "enter"}}) == t("ch_menique_accion", accion="enter")
    assert ("abierta", "as_soltar_un_puno") in filas_3d("un_puno")
    assert ("abierta", "as_soltar") in filas_3d("dos_punos")
    por = {p.clave: p for p in pasos_para("3D", "un_puno")}
    assert por["soltar"].texto == "as_soltar_un_puno"


def test_ventana_de_ayuda_con_la_config(root):
    from lycan_mouse_control.ui.ayuda import VentanaAyuda
    from lycan_mouse_control.ui.textos import t
    v = VentanaAyuda(root, "2D", False, cfg={"senas": {"menique": "clic_derecho"}, "gestos": {"golpe": False}})
    try:
        textos = _textos(v.win)
        assert t("ch_menique_accion", accion=t("mq_clic_derecho").lower()) in textos
        assert not any(x.endswith(t("ch_golpe")) for x in textos)
    finally:
        v.win.destroy()


def test_el_paso_zoom_no_se_logra_con_la_palma():
    from lycan_mouse_control.ui.asistente import contar_logros
    extra = {}
    v = Vista(estado=K.ACTIVO, cuentas={"zoom": 0})
    assert contar_logros("zoom", [], v, extra) == 0
    ruedas = [(0, ("rueda", 120))] * 5                # ruedas del scroll con la palma
    assert contar_logros("zoom", ruedas, Vista(estado=K.ACTIVO, cuentas={"zoom": 0}), extra) == 0
    assert contar_logros("zoom", ruedas, Vista(estado=K.ACTIVO, cuentas={"zoom": 3}), extra) == 3


def test_la_maquina_cuenta_el_zoom_de_la_pinza():
    sim = preparar(modo="2D", perfil="generico")
    a, b = (0.40, 0.5), (0.60, 0.5)
    sim.durante(300, [s.en("pellizco", a, lado="Left"), s.en("pellizco", b)])
    for k in range(1, 11):
        d = 0.02 * k
        sim.cuadro([s.en("pellizco", (a[0] - d, 0.5), lado="Left"), s.en("pellizco", (b[0] + d, 0.5))])
    assert sim.nucleo.maquina.cuenta["zoom"] >= 1


def test_indicador_junto_al_puntero_tiene_las_palabras_nuevas():
    from lycan_mouse_control.ui.indicador_cursor import PALABRAS
    for k in ("lanzar", "despiezar", "armar", "scroll_fin", "menique_doble_clic", "menique_enter"):
        assert k in PALABRAS


def test_textos_de_la_revision():
    from lycan_mouse_control.ui.textos import PALABRAS_PROHIBIDAS, TXT, t
    for k in ("as_tecla_si", "as_tecla_listo"):
        assert "dos veces para hacer clic" not in TXT[k] and "cada toque es un clic" in TXT[k]
    assert "Esc" in TXT["op_grabando"]
    assert "1.0.1" not in TXT["ay_girar_con"]
    for k in ("ch_girar_un_puno", "op_girar_con", "aviso_inercia", "aviso_frenado", "as_girar_un_puno",
              "ch_lanzar", "op_inercia", "ay_inercia", "ay_k_un_puno"):
        assert "pieza" not in TXT[k].lower(), k
    for k in ("pista_clic_anular", "pista_tecla", "pista_scroll", "pista_girar_un_puno"):
        assert TXT[k][0].islower(), k
    for k in ("ayuda_INERCIA", "ayuda_GIRANDO_3D_dos", "aviso_modo_3D_dos", "as_soltar_un_puno",
              "op_atajo_propio", "ay_atajo_barrido", "op_programa_atajos", "aviso_tecla_nueva",
              "ay_tecla_numerico", "op_sin_clic", "op_grabar_cancelada", "op_tecla_con_mod", "op_tecla_comun"):
        assert k in TXT and not any(p in TXT[k].lower() for p in PALABRAS_PROHIBIDAS), k
    assert "Ctrl+Shift+G" in TXT["ay_edwin3d_desdoblar"]
    for k in ("aviso_girando", "sena_palma", "estado_pasando", "ayuda_pasando", "ch_tecla"):
        assert k not in TXT
    assert t("cal_incline_seguir")


def _abrir(root, app, clave):
    from tkinter import ttk

    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    op = VentanaOpciones(root, app)
    nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
    nombres = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
    i = nombres.index(t(clave))
    nb.select(i)
    bombear(root, 60)
    w = nb.nametowidget(nb.tabs()[i])
    return op, getattr(w, "contenido", w)


def test_escribir_un_atajo_letra_por_letra_no_guarda_pedazos(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op, f = _abrir(root, app, "op_palma")
    try:
        entrada = next(h for fila in f.winfo_children() for h in fila.winfo_children()
                       if isinstance(h, tk.Entry) and h.winfo_class() == "Entry")
        v = op._ent_barrido["barrido_der"]
        assert entrada.bind("<KeyRelease>") and entrada.bind("<Return>")
        for pedazo in ("F", "Fl", "Flecha derecha"):
            v.set(pedazo)
            op._poner_atajo_barrido("barrido_der", guardar=False)     # lo que hace <KeyRelease>
            entrada.event_generate("<KeyRelease>")
            bombear(root, 5)
        assert "barrido_der" not in (op.cfg["gestos"]["por_programa"].get("generico") or {})
        assert op.lbl_barrido.cget("text") == t("op_atajo_malo")
        # «Guardar» no cierra con un atajo que no sirve
        op.guardar()
        assert op.win.winfo_exists()
        v.set("Alt+Derecha")
        op.guardar()
        assert app.cfg.datos["gestos"]["por_programa"]["generico"]["barrido_der"] == "Alt+Derecha"
    finally:
        try:
            op.win.destroy()
        except tk.TclError:
            pass


def test_opciones_no_deja_poner_un_atajo_del_programa(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "3D")
    op, _f = _abrir(root, app, "op_girar")
    try:
        op._ent_golpe["abrir_golpe"].set("Ctrl+Alt+X")
        assert op._poner_atajo_golpe("abrir_golpe") is False
        assert op.lbl_golpe.cget("text") == t("op_atajo_propio", funcion=t("op_atajo_salir"))
        assert "abrir_golpe" not in (op.cfg["gestos"]["por_programa"].get(op._programa_golpe()) or {})
    finally:
        op.cancelar()


def test_opciones_clic_cancelar_la_grabacion_deja_todo_como_estaba(root, tmp_path):
    from lycan_mouse_control.ui.textos import t

    class AppConGancho(AppModo):
        def __init__(self, tmp_path):
            super().__init__(tmp_path, "2D")
            self.cb = None
            self.cancelado = 0

        def grabar_tecla(self, cb):
            self.cb = cb
            return True

        def cancelar_grabar(self):
            self.cancelado += 1

    app = AppConGancho(tmp_path)
    op, _f = _abrir(root, app, "op_clic")
    try:
        op._v_numerico.set(False)
        op._tecla_numerico(False)
        assert op.lbl_tecla_estado.cget("text") == t("op_grabando")
        app.cb(("rechazada_mod", 0x4D))
        assert op.lbl_tecla_estado.cget("text") == t("op_tecla_con_mod")
        app.cb(("cancelada",))
        assert op.lbl_tecla_estado.cget("text") == t("op_grabar_cancelada")
        assert op._v_numerico.get() is True and op.cfg["tecla_clic"]["numerico"] is True
        # cambiar de pestaña también cancela
        op._tecla_numerico(False)
        antes = app.cancelado
        op.nb.select(0)
        bombear(root, 30)
        assert app.cancelado > antes and op._v_numerico.get() is True
        # una letra se acepta, pero se avisa que ya no escribirá
        op._grabar_tecla()
        app.cb(("grabada", 0x42, 0x30, False))
        assert t("op_tecla_comun", nombre=op.cfg["tecla_clic"]["nombre"]) in op.lbl_tecla_estado.cget("text")
        # sin clics con los dedos ni tecla: se avisa
        op._set(["senas", "clic_indice"], False)
        op._set(["senas", "clic_anular"], False)
        op._set(["tecla_clic", "activa"], False)
        assert op.lbl_sin_clic.cget("text") == t("op_sin_clic")
        op._set(["tecla_clic", "activa"], True)
        assert op.lbl_sin_clic.cget("text") == ""
    finally:
        op.cancelar()


def test_asistente_deja_de_esperar_la_tecla_al_cambiar_de_paso(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente

    class AppConGancho(AppModo):
        cancelado = 0

        def grabar_tecla(self, cb):
            return True

        def cancelar_grabar(self):
            self.cancelado += 1

    app = AppConGancho(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("tecla")
        a._mostrar()
        a._tecla_no()
        antes = app.cancelado
        a.atras()
        assert app.cancelado > antes
    finally:
        a.cerrar()


def test_aviso_de_la_tecla_nueva_para_quien_viene_de_la_101(tmp_path):
    from lycan_mouse_control.app import App
    app = App.__new__(App)

    class Cfg:
        datos = {"tecla_clic": {"activa": True, "preguntado": False}, "primera_vez": False}
    app.cfg = Cfg()
    assert app._avisar_tecla_nueva() is True
    assert app.cfg.datos["tecla_clic"]["preguntado"] is True
    assert app._avisar_tecla_nueva() is False              # solo una vez
    app.cfg.datos["tecla_clic"] = {"activa": False, "preguntado": False}
    assert app._avisar_tecla_nueva() is False              # apagada: no hay nada que avisar


def test_ayuda_de_la_franja_mientras_gira_solo():
    from lycan_mouse_control.ui.textos import t
    assert "cierre el puño" in t("ayuda_INERCIA").lower()
    assert "las manos" in t("ayuda_GIRANDO_3D_dos")
    assert np is not None
