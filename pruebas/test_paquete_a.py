"""1.0.2 paquete A «Clics»: pellizco con el anular, pulgar + meñique, clic con tecla o pedal.

Todo con manos sintéticas y la salida simulada: nunca se abre la cámara ni se pone el gancho.
"""
import collections
import copy
import json
import math

import numpy as np
import pytest

from conftest import M, Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.acciones import Aviso, Bajar, Clic, Mover, Pulsar, Rueda, Subir, describir
from lycan_mouse_control.clics import ACCIONES_MENIQUE, ORDEN_MENIQUE, limite_tecla_s
from lycan_mouse_control.config import FABRICA, OPCIONES, RANGOS, Configuracion, validar
from lycan_mouse_control.salida.simulada import SalidaSimulada
from lycan_mouse_control.senas import (UMBRALES_FABRICA, Clasificador, Sena, clasificar_una,
                                       construir_umbrales)
from lycan_mouse_control.sistema import teclado as T
from lycan_mouse_control.teclas import interpretar_envio, nombre_envio
from test_estados import P0, manos_pinza, quieto, soltar_al_final

U = construir_umbrales()
U_VAR = construir_umbrales(una_mano_zoom=True)
NUEVAS = (Sena.PELLIZCO_ANULAR, Sena.PELLIZCO_MENIQUE)
CUADROS = 6


def _cuenta(postura, ruido, umbrales=U_VAR, n=200, semilla=1234):
    rng = np.random.default_rng(semilla)
    c = collections.Counter()
    for _ in range(n):
        v = s.variacion_aleatoria(rng, ruido_mm=ruido)
        cl = Clasificador(umbrales)
        r = None
        for _f in range(CUADROS):
            r = cl.clasificar(s.mano(postura, variacion=v, rng=rng).mundo)
        c[r] += 1
    return c


# ======================================================================== clasificador
@pytest.mark.parametrize("postura", sorted(s.CONFUSIONES))
def test_confusiones_no_dan_la_sena_nueva(postura):
    prohibidas = {Sena(x) for x in s.CONFUSIONES[postura]}
    c2 = _cuenta(postura, 2.0)
    assert not any(c2[x] for x in prohibidas), c2
    c4 = _cuenta(postura, 4.0)
    assert sum(c4[x] for x in prohibidas) <= 10, c4      # con mucho ruido, como máximo 5 %


@pytest.mark.parametrize("postura", ["abierta", "puno", "apuntar", "pellizco", "pellizco_corazon", "juntos",
                                     "v", "relajada"])
def test_las_senas_viejas_nunca_dan_anular_ni_menique(postura):
    c = _cuenta(postura, 2.0)
    assert not any(c[x] for x in NUEVAS), c


def test_las_senas_nuevas_no_dan_pellizco_ni_activar():
    for postura in ("pellizco_anular", "pellizco_menique"):
        c = _cuenta(postura, 2.0)
        assert not (c[Sena.PELLIZCO] or c[Sena.ACTIVAR] or c[Sena.PUNO] or c[Sena.PELLIZCO_CORAZON]), c


def test_anular_apagado_no_se_detecta_y_queda_apuntando():
    u = construir_umbrales({"clic_anular": False})
    assert u["pellizco_anular"]["activo"] is False
    m = s.mano("pellizco_anular").mundo
    assert clasificar_una(m, u, 4) == Sena.APUNTAR
    assert clasificar_una(m, U, 4) == Sena.PELLIZCO_ANULAR


def test_menique_en_nada_no_se_detecta():
    u = construir_umbrales({"menique": "nada"})
    assert u["pellizco_menique"]["activo"] is False
    assert clasificar_una(s.mano("pellizco_menique").mundo, u, 4) != Sena.PELLIZCO_MENIQUE
    assert construir_umbrales({"menique": "enter"})["pellizco_menique"]["activo"] is True


@pytest.mark.parametrize("hacia", ["abierta", "apuntar", "relajada"])
def test_abrir_el_puno_no_da_pellizco_nuevo(hacia):
    """Del puño hacia otra postura en 10 pasos: nunca 2 cuadros seguidos de anular o meñique."""
    for lado in ("Right", "Left"):
        c = Clasificador(U)
        for _ in range(5):
            c.clasificar(s.mano("puno", lado=lado).mundo)
        seguidos = maximo = 0
        for k in range(10):
            r = c.clasificar(s.mano(s.intermedia("puno", hacia, k / 9), lado=lado).mundo)
            seguidos = seguidos + 1 if r in NUEVAS else 0
            maximo = max(maximo, seguidos)
        assert maximo < 2


def test_medidas_nuevas_y_palma_estirada():
    c = Clasificador(U)
    for _ in range(4):
        c.clasificar(s.construir("abierta"))
    d = c.medidas.como_dict()
    for k in ("pa", "pm", "lejos_anular", "lejos_menique", "sep", "palma_estirada"):
        assert k in d
    assert c.medidas.palma_estirada is True and d["sep"] >= 0.60
    r = Clasificador(U)
    for _ in range(4):
        r.clasificar(s.construir("relajada"))
    assert r.medidas.palma_estirada is False
    a = Clasificador(U)
    for _ in range(4):
        a.clasificar(s.construir("pellizco_anular"))
    assert a.medidas.pa < 0.28 and a.medidas.lejos_anular > 0.65


def test_umbrales_del_anular_y_menique_se_recortan_y_validan():
    u = construir_umbrales({"pellizco_anular": {"entrar": 5.0, "salir": 9.0},
                            "pellizco_menique": {"entrar": 0.39, "salir": 0.30}})
    assert u["pellizco_anular"]["entrar"] == pytest.approx(0.28 * 1.4)
    assert u["pellizco_menique"]["entrar"] == UMBRALES_FABRICA["pellizco_menique"]["entrar"]


# ======================================================================== máquina: anular
def _izq(sim):
    return [b for b in sim.salida.botones() if b[0] == "izq"]


def test_clic_con_anular_cae_donde_apunta():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    antes = sim.salida.cursor
    sim.durante(250, M("pellizco_anular", P0))
    sim.durante(400, M("apuntar", P0))
    assert _izq(sim)[-2:] == [("izq", True), ("izq", False)]
    assert math.dist(sim.salida.cursor, antes) <= 2
    assert sim.nucleo.maquina.cuenta["anular"] == 1
    soltar_al_final(sim)


def test_arrastre_con_anular():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    t0 = sim.t
    sim.durante(150, M("pellizco_anular", P0))
    d = 200 / sim.mapeo.px_por_unidad_x
    sim.durante(600, lambda f: M("pellizco_anular", (P0[0] + d * f, P0[1])))
    assert sim.estado == K.ARRASTRANDO
    sim.durante(300, M("apuntar", (P0[0] + d, P0[1])))
    acc = [a for a in sim.desde(t0) if isinstance(a, (Mover, Bajar, Subir))]
    tipos = [type(a) for a in acc]
    i_b, i_s = tipos.index(Bajar), tipos.index(Subir)
    movs = [a for a in acc[i_b:i_s] if isinstance(a, Mover)]
    assert movs and movs[-1].x - movs[0].x > 150
    soltar_al_final(sim)


def test_pulgar_corazon_con_la_variante_no_lo_roba_el_anular():
    sim = Sim(cfg={"zoom": {"una_mano": True}})
    sim.nucleo.actualizar_umbrales(sim.cfg["senas"], True)
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(400, M("pellizco_corazon", P0))
    assert sim.nucleo.seguidor.principal.sena == Sena.PELLIZCO_CORAZON
    assert not _izq(sim)
    sim.durante(300, M("apuntar", P0))
    soltar_al_final(sim)


def test_abrir_el_puno_no_da_clic_de_anular():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(400, M("puno", P0))
    for k in range(10):
        sim.cuadro(M(s.intermedia("puno", "abierta", k / 9), P0))
    sim.durante(300, M("abierta", P0))
    assert not _izq(sim)
    soltar_al_final(sim)


def test_dos_pellizcos_de_anular_seguidos_no_pausan():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    for _ in range(2):
        sim.durante(160, M("pellizco_anular", P0))
        sim.durante(160, M("apuntar", P0))
    sim.durante(900, M("apuntar", P0))
    assert sim.base == K.ACTIVO
    assert len([b for b in _izq(sim) if b[1]]) == 2
    soltar_al_final(sim)


def test_clic_indice_apagado_deja_el_anular_y_la_pinza():
    sim = Sim(cfg={"senas": {"clic_indice": False}})
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(250, M("pellizco", P0))
    sim.durante(300, M("apuntar", P0))
    assert not _izq(sim)                                   # el índice ya no hace clic
    sim.durante(250, M("pellizco_anular", P0))
    sim.durante(300, M("apuntar", P0))
    assert [b for b in _izq(sim) if b[1]] == [("izq", True)]
    sim.durante(300, M("abierta", P0))
    sim.durante(200, manos_pinza(0.10))
    sim.durante(900, lambda f: manos_pinza(0.10 * (1 + 0.3 * f)))
    assert sim.de_tipo(Rueda)                              # la pinza de dos manos sigue
    soltar_al_final(sim)


def test_clic_anular_apagado_no_hace_clic():
    sim = Sim(cfg={"senas": {"clic_anular": False}})
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(300, M("pellizco_anular", P0))
    sim.durante(300, M("apuntar", P0))
    assert not _izq(sim)
    soltar_al_final(sim)


# ======================================================================== máquina: meñique
ESPERADO_MENIQUE = {
    "doble_clic": [("boton", "izq", True), ("boton", "izq", False), ("boton", "izq", True),
                   ("boton", "izq", False)],
    "clic_derecho": [("boton", "der", True), ("boton", "der", False)],
    "clic_medio": [("boton", "medio", True), ("boton", "medio", False)],
    "enter": [("pulsar", ("enter",))],
    "esc": [("pulsar", ("esc",))],
    "suprimir": [("pulsar", ("supr",))],
    "deshacer": [("pulsar", ("ctrl", "z"))],
}


@pytest.mark.parametrize("accion", sorted(ESPERADO_MENIQUE))
def test_menique_hace_la_accion_elegida_una_sola_vez(accion):
    sim = Sim(cfg={"senas": {"menique": accion}})
    sim.activar(P0)
    quieto(sim, ms=400)
    antes = sim.salida.cursor
    n0 = len(sim.salida.eventos)
    sim.durante(1000, M("pellizco_menique", P0))          # sostenido: dispara UNA vez
    evs = [ev for _, ev in list(sim.salida.eventos)[n0:] if ev[0] != "mover"]
    assert evs == ESPERADO_MENIQUE[accion]
    assert math.dist(sim.salida.cursor, antes) <= 2       # puntero congelado
    sim.durante(300, M("apuntar", P0))
    soltar_al_final(sim)


def test_menique_doble_clic_va_en_una_sola_llamada():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(300, M("pellizco_menique", P0))
    assert Clic(K.IZQ, 2) in sim.de_tipo(Clic)
    llamadas = collections.Counter(t for t, ev in sim.salida.eventos if ev[0] == "boton")
    assert 4 in llamadas.values()
    soltar_al_final(sim)


def test_menique_vuelve_a_disparar_despues_de_soltar():
    sim = Sim(cfg={"senas": {"menique": "enter"}})
    sim.activar(P0)
    quieto(sim, ms=400)
    for _ in range(2):
        sim.durante(300, M("pellizco_menique", P0))
        sim.durante(200, M("apuntar", P0))
    assert sim.eventos("pulsar") == [("pulsar", ("enter",))] * 2
    soltar_al_final(sim)


def test_menique_en_nada_no_detecta_ni_hace_nada():
    sim = Sim(cfg={"senas": {"menique": "nada"}})
    sim.activar(P0)
    quieto(sim, ms=400)
    n0 = len(sim.salida.eventos)
    sim.durante(500, M("pellizco_menique", P0))
    assert sim.nucleo.seguidor.principal.sena != Sena.PELLIZCO_MENIQUE
    assert not [ev for _, ev in list(sim.salida.eventos)[n0:] if ev[0] in ("boton", "pulsar")]
    soltar_al_final(sim)


def test_menique_nunca_dispara_con_un_boton_abajo():
    sim = Sim(cfg={"senas": {"menique": "enter"}})
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.orden(sim.nucleo.tecla_clic(sim.t, True))          # la tecla sostiene el botón izquierdo
    sim.durante(500, M("pellizco_menique", P0))
    for _ in range(3):
        sim.nucleo.maquina.tecla_repite(sim.t)
        sim.durante(100, M("pellizco_menique", P0))
    assert not sim.eventos("pulsar")
    sim.orden(sim.nucleo.tecla_clic(sim.t, False))
    sim.durante(200, M("apuntar", P0))
    soltar_al_final(sim)


def test_menique_en_pausa_no_hace_nada():
    sim = Sim()
    sim.durante(600, M("pellizco_menique", P0))
    assert not sim.salida.botones()
    soltar_al_final(sim)


# ======================================================================== máquina: tecla
def _tecla(sim, abajo):
    sim.orden(sim.nucleo.tecla_clic(sim.t, abajo))


def test_tecla_un_toque_es_un_clic_en_el_sitio():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    antes = sim.salida.cursor
    _tecla(sim, True)
    sim.durante(66, M("apuntar", P0))
    _tecla(sim, False)
    assert _izq(sim) == [("izq", True), ("izq", False)]
    assert math.dist(sim.salida.cursor, antes) <= 2
    assert sim.nucleo.maquina.cuenta["tecla"] == 1
    sim.durante(200, M("apuntar", P0))
    soltar_al_final(sim)


def test_tecla_dos_toques_son_dos_clics_en_el_mismo_punto():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    for _ in range(2):
        _tecla(sim, True)
        sim.durante(66, M("apuntar", P0))
        _tecla(sim, False)
        sim.durante(66, M("apuntar", P0))
    assert _izq(sim) == [("izq", True), ("izq", False)] * 2
    soltar_al_final(sim)


def test_tecla_sostenida_y_mover_la_mano_es_arrastre():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    _tecla(sim, True)
    x0 = sim.salida.cursor[0]
    d = 200 / sim.mapeo.px_por_unidad_x
    for k in range(20):
        sim.nucleo.maquina.tecla_repite(sim.t)
        sim.cuadro(M("apuntar", (P0[0] + d * k / 19, P0[1])))
    assert sim.estado == K.ARRASTRANDO
    assert sim.salida.cursor[0] - x0 > 150
    # un pellizco durante el arrastre con tecla no suelta el botón
    sim.durante(200, M("pellizco", (P0[0] + d, P0[1])))
    sim.nucleo.maquina.tecla_repite(sim.t)
    sim.durante(200, M("apuntar", (P0[0] + d, P0[1])))
    assert "izq" in sim.salida.botones_abajo
    _tecla(sim, False)
    assert not sim.salida.botones_abajo
    soltar_al_final(sim)


def test_tecla_en_pausa_no_hace_nada():
    sim = Sim()
    sim.durante(300, M("apuntar", P0))
    _tecla(sim, True)
    _tecla(sim, False)
    assert not sim.salida.botones()
    soltar_al_final(sim)


def test_tecla_sin_mano_no_presiona():
    sim = Sim()
    sim.activar(P0)
    sim.durante(300, [])
    _tecla(sim, True)
    assert not sim.salida.botones()
    _tecla(sim, False)
    soltar_al_final(sim)


def test_tecla_apagada_no_presiona():
    sim = Sim(cfg={"tecla_clic": {"activa": False}})
    sim.activar(P0)
    _tecla(sim, True)
    _tecla(sim, False)
    assert not sim.salida.botones()
    soltar_al_final(sim)


def test_seguridad_suelta_sola_si_no_llega_la_repeticion():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    _tecla(sim, True)
    sim.durante(600, M("apuntar", P0))
    assert "izq" in sim.salida.botones_abajo           # antes del límite (1 s en pruebas) sigue
    sim.durante(600, M("apuntar", P0))
    assert not sim.salida.botones_abajo
    assert any(isinstance(a, Aviso) and a.clave == "tecla_suelta" for a in sim.de_tipo(Aviso))
    _tecla(sim, False)                                  # el soltar que llega tarde no hace nada
    assert _izq(sim) == [("izq", True), ("izq", False)]
    soltar_al_final(sim)


def test_tecla_con_repeticiones_no_se_suelta():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    _tecla(sim, True)
    for _ in range(20):
        sim.nucleo.maquina.tecla_repite(sim.t)
        sim.durante(100, M("apuntar", P0))
    assert "izq" in sim.salida.botones_abajo
    _tecla(sim, False)
    soltar_al_final(sim)


@pytest.mark.parametrize("como", ["mano", "pausa", "bloqueo", "programa"])
def test_tecla_se_suelta_con_mano_perdida_pausa_bloqueo_y_cambio_de_programa(como):
    from lycan_mouse_control import perfiles
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    _tecla(sim, True)
    assert "izq" in sim.salida.botones_abajo
    if como == "mano":
        sim.durante(300, [])
    elif como == "pausa":
        sim.orden(sim.nucleo.pausar(sim.t))
    elif como == "bloqueo":
        sim.orden(sim.nucleo.bloquear(sim.t, "admin"))
        sim.orden(sim.nucleo.desbloquear(sim.t))
    else:
        sim.orden(sim.nucleo.cambiar_perfil(sim.t, perfiles.obtener("sketchup")))
    assert not sim.salida.botones_abajo
    _tecla(sim, False)
    assert _izq(sim) == [("izq", True), ("izq", False)]
    soltar_al_final(sim)


def test_tecla_no_baja_si_el_pellizco_ya_tiene_el_boton():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(200, M("pellizco", P0))
    assert sim.estado == K.ARRASTRANDO
    _tecla(sim, True)
    _tecla(sim, False)
    assert "izq" in sim.salida.botones_abajo           # sigue el del pellizco
    sim.durante(300, M("apuntar", P0))
    assert _izq(sim) == [("izq", True), ("izq", False)]
    soltar_al_final(sim)


def test_frenar_sin_inercia_no_hace_nada():
    sim = Sim()
    sim.activar(P0)
    assert sim.nucleo.frenar(sim.t) == []
    assert sim.nucleo.maquina.inercia_activa is False
    soltar_al_final(sim)


# ======================================================================== gancho: decidir
def _e(**kw):
    e = T.EstadoGancho(motor_activo=True)
    for k, v in kw.items():
        setattr(e, k, v)
    return e


@pytest.mark.parametrize("vk", [0x65, 0x0C])       # con y sin Bloq Num
def test_decidir_5_numerico_bajar_y_subir(vk):
    e = _e()
    sup, ev = T.decidir(vk, 0x4C, False, True, False, 0, e, 1.0)
    assert sup and ev == ("tecla_clic", True, 1.0)
    sup, ev = T.decidir(vk, 0x4C, False, True, False, 0, e, 1.5)
    assert sup and ev == ("tecla_repite", 1.5)            # repetición: se traga
    sup, ev = T.decidir(vk, 0x4C, False, False, False, 0, e, 2.0)
    assert sup and ev == ("tecla_clic", False, 2.0)


def test_decidir_el_5_de_arriba_no_cuenta():
    e = _e()
    assert T.decidir(0x35, 0x06, False, True, False, 0, e) == (False, None)
    assert T.decidir(0x35, 0x06, False, False, False, 0, e) == (False, None)


def test_decidir_inyectada_y_propia_pasan():
    e = _e()
    assert T.decidir(0x65, 0x4C, False, True, True, 0, e) == (False, None)
    assert T.decidir(0x65, 0x4C, False, True, False, K.LYCAN_EXTRA, e) == (False, None)
    assert not e.abajo_suprimido


def test_decidir_en_pausa_pasa_el_bajar_y_el_subir():
    e = _e(motor_activo=False)
    assert T.decidir(0x65, 0x4C, False, True, False, 0, e) == (False, None)
    assert T.decidir(0x65, 0x4C, False, True, False, 0, e) == (False, None)     # repetición
    assert T.decidir(0x65, 0x4C, False, False, False, 0, e) == (False, None)


def test_decidir_bajar_activo_pausa_en_medio_subir_se_traga():
    e = _e()
    assert T.decidir(0x65, 0x4C, False, True, False, 0, e)[0]
    e.motor_activo = False
    sup, ev = T.decidir(0x65, 0x4C, False, False, False, 0, e, 3.0)
    assert sup and ev == ("tecla_clic", False, 3.0)       # si no, quedaría pegada en el programa


def test_decidir_tecla_apagada_pasa():
    e = _e(activa=False)
    assert T.decidir(0x65, 0x4C, False, True, False, 0, e) == (False, None)


def test_decidir_tecla_propia_exige_vk_scan_y_extendida():
    e = _e(numerico=False, vk=0x7A, scan=0x57, extendida=False)       # F11
    assert T.decidir(0x7A, 0x57, False, True, False, 0, e)[1] == ("tecla_clic", True, 0.0)
    assert T.decidir(0x7A, 0x57, False, False, False, 0, e)[0]
    assert T.decidir(0x7A, 0x57, True, True, False, 0, e) == (False, None)
    assert T.decidir(0x65, 0x4C, False, True, False, 0, e) == (False, None)


def test_decidir_grabar_y_modificadores_rechazados():
    e = _e(grabando=True)
    for vk in (0x10, 0x11, 0x12, 0xA0, 0xA3, 0x5B):
        sup, ev = T.decidir(vk, 0x2A, False, True, False, 0, e)
        assert sup and ev == ("rechazada", vk)
    assert e.grabando
    sup, ev = T.decidir(0x7A, 0x57, False, True, False, 0, e)
    assert sup and ev == ("grabada", 0x7A, 0x57, False)
    assert not e.grabando
    assert T.decidir(0x7A, 0x57, False, True, False, 0, e) == (True, None)     # repetición
    assert T.decidir(0x7A, 0x57, False, False, False, 0, e) == (True, None)    # su subir
    assert T.decidir(0x7A, 0x57, False, True, False, 0, e) == (False, None)    # ya pasa normal


def test_decidir_otra_tecla_con_inercia_frena_y_pasa():
    e = _e(inercia_activa=True)
    assert T.decidir(0x41, 0x1E, False, True, False, 0, e) == (False, ("frenar",))
    e.inercia_activa = False
    assert T.decidir(0x41, 0x1E, False, True, False, 0, e) == (False, None)


def test_datos_de_tecla_grabada():
    assert T.datos_tecla_grabada(0x0C, 0x4C, False)["numerico"] is True
    d = T.datos_tecla_grabada(0x7A, 0x57, False)
    assert d["numerico"] is False and d["vk"] == 0x7A and d["nombre"]


def test_limite_de_la_seguridad():
    assert limite_tecla_s(None, None) == 1.0
    assert limite_tecla_s(9, 40) == 1.0
    lento = limite_tecla_s(3, 0)
    rapido = limite_tecla_s(0, 31)
    assert rapido < lento
    assert rapido == pytest.approx(0.25 + 2 / 30 + 0.25)
    assert lento == pytest.approx(1.0 + 2 / 2.5 + 0.25)


# ======================================================================== teclas
@pytest.mark.parametrize("texto,tupla", [
    ("Enter", ("enter",)), ("Esc", ("esc",)), ("Supr", ("supr",)), ("Ctrl+Z", ("ctrl", "z")),
    ("Alt+Izquierda", ("alt", "izquierda")), ("Ctrl+Shift+G", ("ctrl", "shift", "g")),
    ("Ctrl+Alt+U", ("ctrl", "alt", "u")), ("RePág", ("repag",)), ("F5", ("f5",)),
])
def test_teclas_ida_y_vuelta(texto, tupla):
    assert interpretar_envio(texto) == tupla
    assert nombre_envio(tupla) == texto
    assert interpretar_envio(nombre_envio(tupla)) == tupla


@pytest.mark.parametrize("texto,tupla", [("Del", ("supr",)), ("Left", ("izquierda",)), ("ctrl + z", ("ctrl", "z")),
                                         ("Shift+Ctrl+G", ("ctrl", "shift", "g")), ("PgDn", ("avpag",))])
def test_teclas_alias(texto, tupla):
    assert interpretar_envio(texto) == tupla


@pytest.mark.parametrize("malo", ["", "   ", None, 5, "Ctrl", "Ctrl+", "Ctrl++Z", "Z+X", "Hola", "Ctrl+Alt"])
def test_teclas_textos_malos(malo):
    assert interpretar_envio(malo) is None


# ======================================================================== salida
def test_salida_doble_clic_y_pulsar():
    s_ = SalidaSimulada()
    s_.aplicar([Clic("izq", 2)])
    assert s_.llamadas == 1 and len(s_.botones()) == 4
    s_.aplicar([Pulsar(("ctrl", "z"))])
    assert s_.solo("pulsar") == [("pulsar", ("ctrl", "z"))]
    assert describir(Clic("izq", 2)) == "Doble clic izquierdo"
    assert describir(Pulsar(("ctrl", "z"))) == "Tecla Ctrl+Z"


def test_salida_pulsar_nunca_con_botones_abajo_ni_sobre_la_ventana():
    s_ = SalidaSimulada()
    s_.aplicar([Bajar("izq"), Pulsar(("enter",)), Subir("izq")])
    assert not s_.solo("pulsar")
    s_.foco_propio = True
    avisos = s_.aplicar([Pulsar(("enter",))])
    assert not s_.solo("pulsar") and avisos and avisos[0].clave == "sobre_ventana"


def test_windows_construye_pulsar_con_extendida():
    from lycan_mouse_control.salida import windows as W
    ins = W.eventos_pulsar(("ctrl", "supr"))
    assert len(ins) == 4
    vks = [(i.ki.wVk, bool(i.ki.dwFlags & W.KEYEVENTF_KEYUP), bool(i.ki.dwFlags & W.KEYEVENTF_EXTENDEDKEY))
           for i in ins]
    assert vks == [(0xA2, False, False), (0x2E, False, True), (0x2E, True, True), (0xA2, True, False)]
    assert all(i.ki.dwExtraInfo == K.LYCAN_EXTRA for i in ins)
    assert W.eventos_pulsar(("nada",)) == []


# ======================================================================== config
def test_config_vieja_de_la_101_carga_con_los_valores_de_fabrica_nuevos(tmp_path):
    viejo = copy.deepcopy(FABRICA)
    del viejo["tecla_clic"]
    for k in ("pellizco_anular", "pellizco_menique", "clic_indice", "clic_anular", "menique"):
        del viejo["senas"][k]
    del viejo["senas"]["tiempos_ms"]["menique"]
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(viejo), encoding="utf-8")
    c = Configuracion(ruta)
    d = c.cargar()
    assert c.aviso is None and not c.problemas
    assert d["tecla_clic"] == FABRICA["tecla_clic"]
    assert d["senas"]["clic_indice"] is True and d["senas"]["clic_anular"] is True
    assert d["senas"]["menique"] == "doble_clic"
    assert d["senas"]["tiempos_ms"]["menique"] == 100
    assert d["senas"]["pellizco_anular"] == {"entrar": 0.28, "salir": 0.42}


@pytest.mark.parametrize("ruta,malo", [
    ("senas.menique", "bailar"), ("senas.menique", 3), ("senas.clic_anular", "sí"),
    ("senas.tiempos_ms.menique", 5), ("senas.pellizco_anular.entrar", 7.0), ("senas.pellizco_menique.salir", -1),
    ("tecla_clic.vk", 999), ("tecla_clic.scan", -3), ("tecla_clic.activa", 1), ("tecla_clic.nombre", ""),
    ("tecla_clic.nombre", 42), ("tecla_clic.extendida", "no"),
])
def test_config_valores_malos_vuelven_a_fabrica(ruta, malo):
    datos = copy.deepcopy(FABRICA)
    datos["tecla_clic"]["numerico"] = False       # así vk/scan no se reescriben
    d = datos
    partes = ruta.split(".")
    for k in partes[:-1]:
        d = d[k]
    d[partes[-1]] = malo
    p = []
    out = validar(datos, problemas=p)
    v = out
    f = FABRICA
    for k in partes:
        v, f = v[k], f[k]
    assert v == f and p


def test_config_numerico_fija_el_5():
    datos = copy.deepcopy(FABRICA)
    datos["tecla_clic"].update(vk=0x41, scan=0x1E, nombre="A")
    assert validar(datos)["tecla_clic"]["vk"] == 0x65
    datos["tecla_clic"]["numerico"] = False
    out = validar(datos)["tecla_clic"]
    assert out["vk"] == 0x41 and out["nombre"] == "A"


def test_config_claves_nuevas_tienen_rango_y_opciones():
    for r in ("senas.pellizco_anular.entrar", "senas.pellizco_menique.salir", "senas.tiempos_ms.menique",
              "tecla_clic.vk", "tecla_clic.scan"):
        assert r in RANGOS
    assert tuple(OPCIONES["senas.menique"]) == ORDEN_MENIQUE
    assert set(ACCIONES_MENIQUE) | {"nada"} == set(ORDEN_MENIQUE)


# ======================================================================== motor
def test_motor_atiende_la_tecla_y_avisa_al_gancho():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.mapeo import Mapeo
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    sal = SalidaSimulada()
    m = Motor(por_defecto(), sal, sistema=False)
    m.mapeo = Mapeo()
    m.nucleo = Nucleo(por_defecto(), mapeo=m.mapeo, pos_cursor=sal.posicion_cursor)
    m.ordenes.put(("pausar",))
    m._atender_ordenes()
    assert m.estado_gancho.motor_activo is True
    m.nucleo.procesar(0.0, [M("apuntar", P0)])
    m.ordenes.put(("tecla_clic", True, 0.05))
    m.ordenes.put(("tecla_repite", 0.1))
    m.ordenes.put(("tecla_clic", False, 0.12))
    m.ordenes.put(("frenar",))
    m._atender_ordenes()
    assert sal.botones() == [("izq", True), ("izq", False)]
    m.ordenes.put(("pausar",))
    m._atender_ordenes()
    assert m.estado_gancho.motor_activo is False
    cfg = por_defecto()
    cfg["tecla_clic"].update(numerico=False, vk=0x7A, scan=0x57)
    m.cfg["camara"] = cfg["camara"]
    m._nueva_config(cfg)
    assert m.estado_gancho.numerico is False and m.estado_gancho.vk == 0x7A


def test_argumento_sin_gancho_y_app_no_pone_el_gancho():
    from lycan_mouse_control import app as A
    a = A.argumentos(["--sin-gancho"])
    assert a.sin_gancho is True
    assert A.argumentos([]).sin_gancho is False
    app = A.App(A.argumentos(["--simular", "--sin-gancho"]))
    app._iniciar_gancho()
    assert app.gancho is None
    assert app.grabar_tecla(lambda ev: None) is False
    app._evento_gancho(("tecla_clic", True, 1.0))
    assert app.motor.ordenes.get_nowait() == ("tecla_clic", True, 1.0)
    app._evento_gancho(("grabada", 0x7A, 0x57, False))
    assert app.cola_gancho.get_nowait()[0] == "grabada"
    app._soltar_todo_seguro("prueba")


@pytest.mark.skipif(not hasattr(T, "KBDLLHOOKSTRUCT"), reason="solo Windows")
def test_callback_del_gancho_sin_instalarlo():
    """El callback lee la estructura de Windows, decide y encola, sin poner ningún gancho."""
    import ctypes
    eventos = []
    g = T.GanchoTeclado(T.EstadoGancho(motor_activo=True), eventos.append)
    k = T.KBDLLHOOKSTRUCT(0x65, 0x4C, 0, 0, 0)
    assert g._callback(0, T.WM_KEYDOWN, ctypes.addressof(k)) == 1
    k2 = T.KBDLLHOOKSTRUCT(0x65, 0x4C, T.LLKHF_UP, 0, 0)
    assert g._callback(0, T.WM_KEYUP, ctypes.addressof(k2)) == 1
    assert [e[:2] for e in eventos] == [("tecla_clic", True), ("tecla_clic", False)]
    assert not g.is_alive()           # nunca se arrancó el hilo


def test_limite_de_repeticion_de_windows_es_razonable():
    v = T.limite_repeticion_s()
    assert 0.3 <= v <= 2.5
