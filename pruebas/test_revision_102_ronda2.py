"""Segunda ronda de revisión de la 1.0.2: pellizcos del anular y del meñique que parpadeaban,
cambio de programa en pleno giro, modo «3D_dos», gancho de teclado con el motor detenido, grabar
tecla con Ctrl/Alt, y textos/tamaños de la interfaz. Todo con manos sintéticas (sin cámara)."""
import time
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles as P
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.senas import GANA_CLARO, GANA_MEMORIA, GANA_SEGUIR, Clasificador, Sena
from lycan_mouse_control.sistema import teclado as T

C = (0.55, 0.50)


def _preparar(modo="2D", perfil="generico"):
    sim = Sim(modo=modo, perfil=perfil)
    sim.activar(C)
    sim.durante(600, s.en("apuntar", C))
    return sim


def _bajadas_izq(sim, desde):
    return sum(1 for t, ev in sim.salida.eventos if t >= desde and ev == ("boton", "izq", True))


def _arrastre(postura, semilla, ruido_mm=1.5, f=0.90, cuadros=45):
    """Pellizco firme pero con el pulgar algo cerca del dedo vecino, arrastrando 1,5 s."""
    rng = np.random.default_rng(semilla)
    var = s.variacion_aleatoria(rng, ruido_mm=0, rot_max=30, permitir_izquierda=False)
    sim = _preparar()
    pose = s.intermedia("apuntar", postura, f)

    def m(pos, pp=pose):
        return s.mano(pp, posicion=pos, ancla="centro", rot=var.rot, escala=var.escala, ruido_mm=ruido_mm, rng=rng)

    sim.durante(300, m(C, s.construir("apuntar")))
    t0 = sim.t
    for k in range(1, 4):
        sim.cuadro(m(C, s.intermedia("apuntar", postura, f * k / 3)))
    x = C[0]
    for _ in range(cuadros):
        x += 0.004
        sim.cuadro(m((x, 0.5)))
    for k in range(1, 4):
        sim.cuadro(m((x, 0.5), s.intermedia(postura, "apuntar", k / 3)))
    sim.durante(400, m((x, 0.5), s.construir("apuntar")))
    assert not sim.salida.botones_abajo
    return _bajadas_izq(sim, t0)


# ================================================== 1. pellizcos del anular y del meñique
@pytest.mark.parametrize("semilla", range(6))
def test_arrastre_con_el_anular_no_se_corta_con_ruido(semilla):
    assert _arrastre("pellizco_anular", 50 + semilla) == 1


@pytest.mark.parametrize("semilla", range(4))
def test_arrastre_con_el_anular_aguanta_ruido_fuerte(semilla):
    assert _arrastre("pellizco_anular", 80 + semilla, ruido_mm=3.0) == 1


@pytest.mark.parametrize("semilla", range(6))
def test_menique_sostenido_da_un_solo_doble_clic(semilla):
    assert _arrastre("pellizco_menique", 50 + semilla, cuadros=60) == 2      # un doble clic


def test_indice_sigue_igual():
    assert _arrastre("pellizco", 7) == 1


def test_regla_del_06_tiene_histeresis():
    c = Clasificador()
    assert c._limite_gana(Sena.PELLIZCO_ANULAR) == GANA_CLARO
    assert GANA_SEGUIR > GANA_CLARO
    c._ult_dedo = (Sena.PELLIZCO_ANULAR, 0)
    assert c._limite_gana(Sena.PELLIZCO_ANULAR) == GANA_SEGUIR
    assert c._limite_gana(Sena.PELLIZCO_MENIQUE) == GANA_CLARO      # solo el mismo dedo
    c._ult_dedo = (Sena.PELLIZCO_ANULAR, GANA_MEMORIA)
    assert c._limite_gana(Sena.PELLIZCO_ANULAR) == GANA_CLARO      # pasados ~150 ms ya no
    assert c._gana(0.14, 0.2, limite=GANA_SEGUIR) and not c._gana(0.14, 0.2)
    c.reiniciar()
    assert c._ult_dedo[0] is None


def test_clasificador_cuenta_cuadros_desde_el_ultimo_pellizco_de_dedo():
    from lycan_mouse_control.senas import construir_umbrales
    c = Clasificador(construir_umbrales())
    w = s.mano("pellizco_anular").mundo
    for _ in range(4):
        c.clasificar(w)
    assert c._ult_dedo == (Sena.PELLIZCO_ANULAR, 0)
    c.clasificar(None)                       # mano perdida: también cuenta
    assert c._ult_dedo == (Sena.PELLIZCO_ANULAR, 1)


def test_cerrojo_del_menique_no_lo_suelta_ninguna():
    sim = _preparar()
    m = sim.nucleo.maquina
    p = SimpleNamespace(detectada=True)
    t = sim.t + 0.1
    acc = []
    for i in range(5):                        # 5 cuadros de meñique: dispara una vez
        m._menique(t + i / 30, p, Sena.PELLIZCO_MENIQUE, False, acc)
    assert m.men_cerrojo and m.cuenta["menique"] == 1
    t += 5 / 30
    for i in range(4):                        # 4 cuadros de NINGUNA: el cerrojo sigue
        m._menique(t + i / 30, p, Sena.NINGUNA, False, acc)
    assert m.men_cerrojo
    t += 4 / 30
    for i in range(5):
        m._menique(t + i / 30, p, Sena.PELLIZCO_MENIQUE, False, acc)
    assert m.cuenta["menique"] == 1           # no repite el doble clic
    t += 5 / 30
    for i in range(2):                        # 2 cuadros de otra seña de verdad: se suelta
        m._menique(t + i / 30, p, Sena.APUNTAR, False, acc)
    assert not m.men_cerrojo


def test_cerrojo_del_menique_se_suelta_con_medio_segundo_sin_menique():
    sim = _preparar()
    m = sim.nucleo.maquina
    p = SimpleNamespace(detectada=True)
    acc = []
    t = sim.t + 0.1
    for i in range(5):
        m._menique(t + i / 30, p, Sena.PELLIZCO_MENIQUE, False, acc)
    assert m.men_cerrojo
    m._menique(t + 0.2, p, Sena.NINGUNA, False, acc)
    assert m.men_cerrojo
    m._menique(t + 0.75, SimpleNamespace(detectada=False), Sena.NINGUNA, False, acc)
    assert not m.men_cerrojo


# ================================================== 2. cambio de programa en pleno giro
def test_cambiar_de_programa_girando_con_un_puno_no_da_clic_derecho():
    from test_paquete_b import derecho, girar, preparar
    sim = preparar()
    girar(sim)
    assert sim.nucleo.maquina.gesto in ("orbita1", "inercia")
    t1 = sim.t
    sim.orden(sim.nucleo.cambiar_perfil(sim.t, P.PERFILES["sketchup"]))
    sim.durante(800, s.en("puno", (0.68, 0.50)))
    assert derecho(sim, t1) == []
    assert not sim.salida.botones_abajo
    # al abrir la mano, el puño vuelve a dar clic derecho
    sim.durante(300, s.en("apuntar", (0.68, 0.50)))
    t2 = sim.t
    sim.durante(600, s.en("puno", (0.68, 0.50)))
    assert len(derecho(sim, t2)) == 1


# ================================================== 3. modo «3D_dos»
def test_al_cambiar_modo_entiende_3d_dos():
    from lycan_mouse_control.app import App
    falso = SimpleNamespace(cfg=SimpleNamespace(datos={"modo": "2D"}))
    App.al_cambiar_modo(falso, "3D_dos")
    assert falso.cfg.datos["modo"] == "3D"
    App.al_cambiar_modo(falso, "2D")
    assert falso.cfg.datos["modo"] == "2D"
    App.al_cambiar_modo(falso, None)
    App.al_cambiar_modo(falso, "raro")
    assert falso.cfg.datos["modo"] == "2D"


# ================================================== 4. gancho con el motor detenido o colgado
def test_gancho_no_traga_la_tecla_si_el_motor_no_da_latido():
    e = T.EstadoGancho(motor_activo=True, t_vivo=100.0)
    sup, ev = T.decidir(0x65, 0x4C, False, True, False, 0, e, 100.5)
    assert sup and ev[0] == "tecla_clic"
    T.decidir(0x65, 0x4C, False, False, False, 0, e, 100.6)
    sup, ev = T.decidir(0x65, 0x4C, False, True, False, 0, e, 100.0 + T.LATIDO_S + 0.5)
    assert (sup, ev) == (False, None)          # motor colgado: la tecla escribe normal
    assert T.decidir(0x65, 0x4C, False, False, False, 0, e, 103.0) == (False, None)


def test_motor_detenido_suelta_el_gancho():
    from test_motor_app import armar, esperar
    m, _sal = armar(lambda t: [])
    try:
        m.ordenes.put(("pausar",))
        assert esperar(lambda: m.estado_gancho.motor_activo)
        assert m.estado_gancho.t_vivo is not None
        assert abs(time.perf_counter() - m.estado_gancho.t_vivo) < 1.0
    finally:
        m.detener()
        m.join(3)
    assert m.estado_gancho.motor_activo is False and m.estado_gancho.inercia_activa is False


# ================================================== 5. grabar tecla con Ctrl/Alt
def test_grabar_deja_pasar_el_atajo_entero():
    e = T.EstadoGancho(grabando=True)
    assert T.decidir(0xA2, 0x1D, False, True, False, 0, e) == (False, ("rechazada", 0xA2))   # Ctrl pasa
    assert T.decidir(0x5A, 0x2C, False, True, False, 0, e) == (False, ("rechazada_mod", 0x5A))  # Z pasa
    assert T.decidir(0x5A, 0x2C, False, False, False, 0, e) == (False, None)
    assert T.decidir(0xA2, 0x1D, False, False, False, 0, e) == (False, None)
    assert e.grabando and not e.mods_grabando


# ================================================== 6. interfaz
@pytest.fixture
def root():
    ultimo = None
    for _ in range(5):
        try:
            r = tk.Tk()
            break
        except tk.TclError as e:
            ultimo = e
            time.sleep(0.2)
    else:
        pytest.skip(f"sin pantalla ({ultimo})")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass


def test_textos_nuevos():
    from lycan_mouse_control.ui.textos import t
    assert "un puño" in t("ay_inercia")
    assert "Volver a practicar señas" in t("ay_mano_baja")
    assert "⚙ > Clic" in t("aviso_tecla_nueva") and len(t("aviso_tecla_nueva")) <= 80


def test_chuleta_3d_con_dos_punos_no_habla_de_girar_con_un_puno():
    from lycan_mouse_control.ui.ayuda import filas_3d
    claves = [c for _, c in filas_3d("dos_punos")]
    assert "ch_puno_3d_dos" in claves and "ch_puno_3d" not in claves
    assert "ch_puno_3d" in [c for _, c in filas_3d("un_puno")]
    assert "ch_puno_3d" in [c for _, c in filas_3d("ambos")]


@pytest.mark.parametrize("accion,esperado", [("deshacer", "deshacer (Ctrl+Z)"), ("enter", "Enter"),
                                             ("esc", "Esc"), ("doble_clic", "doble clic")])
def test_fila_del_menique_respeta_mayusculas(accion, esperado):
    from lycan_mouse_control.ui.ayuda import texto_fila
    assert f": {esperado}." in texto_fila("ch_menique", {"senas": {"menique": accion}})


def test_asistente_con_los_dos_giros_suelta_en_singular():
    from lycan_mouse_control.ui.asistente import pasos_para
    pasos = {p.clave: p for p in pasos_para("3D", "ambos")}
    assert pasos["girar"].texto == "as_girar_un_puno"
    assert pasos["soltar"].texto == "as_soltar_un_puno"
    pasos = {p.clave: p for p in pasos_para("3D", "dos_punos")}
    assert pasos["soltar"].texto == "as_soltar"


def test_aviso_largo_crece_y_no_se_corta(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    from test_interfaz import AppFalsa, bombear
    app = AppFalsa(tmp_path)
    v = VentanaPrincipal(root, app)
    try:
        for clave in ("aviso_tecla_nueva", "aviso_bloqueado_admin", "aviso_camara_lenta"):
            v.mostrar_aviso(t(clave), 10)
            bombear(root, 50)
            v.root.update_idletasks()
            assert v.lbl_aviso.winfo_manager() == "place"
            assert v.lbl_aviso.winfo_height() + 2 >= v.lbl_aviso.winfo_reqheight(), clave
    finally:
        app.cerrando = True


def test_asistente_tecla_si_despues_de_no_quiero_vuelve_a_contar(root, tmp_path):
    from lycan_mouse_control.motor import Vista
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    from test_interfaz import bombear
    from test_ronda1_interfaz import AppModo
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("tecla")
        a._mostrar()
        a._tecla_no_quiero()
        assert str(a.b_sig.cget("state")) == "normal"
        a._tecla_si()
        assert "no_quiere" not in a.extra_estado
        assert str(a.b_sig.cget("state")) == "disabled"
        img = np.zeros((240, 320, 3), np.uint8)
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"tecla": 0}, imagen=img)
        bombear(root, 120)
        app.ultima_vista = Vista(estado=K.ACTIVO, cuentas={"tecla": 2}, imagen=img)
        bombear(root, 150)
        assert a.lbl_logro.cget("text") == t("as_logrado", k=2, n=2)
        assert str(a.b_sig.cget("state")) == "normal"
    finally:
        a.cerrar()


def test_opciones_crece_con_letras_grandes(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones as Opciones
    from test_ronda1_interfaz import AppModo
    app = AppModo(tmp_path, "2D")
    app.root = root
    viejo = float(root.tk.call("tk", "scaling"))
    root.tk.call("tk", "scaling", viejo * 1.25)
    try:
        op = Opciones(root, app)
        try:
            op.win.update_idletasks()
            pide = op.win.winfo_reqwidth()
            ancho = int(op.win.geometry().split("x")[0])
            assert ancho >= min(pide, op.win.winfo_screenwidth() - 20)
            assert ancho <= op.win.winfo_screenwidth()
        finally:
            op.cancelar()
    finally:
        root.tk.call("tk", "scaling", viejo)
