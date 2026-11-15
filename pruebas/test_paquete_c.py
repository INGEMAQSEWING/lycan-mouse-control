"""1.0.2 paquete C «Palma y comodidad»: pasar página con la palma, barrido y mano baja.

Todo con manos sintéticas y la salida simulada: nunca se abre la cámara ni se pone el gancho.
"""
import copy
import json

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import mano_baja as MB
from lycan_mouse_control import perfiles as P
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.acciones import Aviso, Bajar, Clic, Pulsar, Rueda, Sonido
from lycan_mouse_control.calibracion import evaluar_distancia
from lycan_mouse_control.config import FABRICA, RANGOS, Configuracion, validar
from test_estados import soltar_al_final

C = (0.55, 0.50)          # centro de la palma
ARRIBA = (0.55, 0.38)


def preparar(modo="2D", perfil="generico", cfg=None, fps=30.0, pos=C):
    sim = Sim(modo=modo, perfil=perfil, cfg=cfg, fps=fps)
    sim.activar(pos)
    sim.durante(600, s.en("apuntar", pos))
    return sim


def cuadros(sim, manos):
    for m in manos:
        sim.cuadro(m)


def ruedas(sim, desde=0.0):
    return [a.delta for a in sim.desde(desde) if isinstance(a, Rueda)]


def pulsados(sim, desde=0.0):
    return [ev[1] for t, ev in sim.salida.eventos if t >= desde and ev[0] == "pulsar"]


def avisos(sim, desde=0.0):
    return [a.clave for a in sim.desde(desde) if isinstance(a, Aviso)]


def clics(sim, desde=0.0):
    return [ev for t, ev in sim.salida.eventos if t >= desde and ev[0] == "boton" and ev[2]]


def empezar_scroll(sim, pos=C):
    """Palma estirada quieta hasta que arranca el scroll (máximo 1,5 s)."""
    for _ in range(45):
        sim.cuadro(s.en("abierta", pos))
        if sim.nucleo.maquina.gesto == "scroll":
            return
    raise AssertionError("el scroll no arrancó")


# =============================================================== scroll: arranque
def test_palma_estirada_quieta_medio_segundo_arranca_el_scroll():
    sim = preparar()
    t0 = sim.t
    sim.durante(400, s.en("abierta", C))
    assert sim.nucleo.maquina.gesto is None and sim.estado == K.ACTIVO
    sim.durante(350, s.en("abierta", C))
    assert sim.nucleo.maquina.gesto == "scroll"
    assert sim.estado == K.PASANDO_PAGINA
    assert "scroll" in avisos(sim, t0)
    assert any(isinstance(a, Sonido) and a.nombre == "scroll" for a in sim.desde(t0))
    t_aviso = next(t for t, a in sim.acciones if t >= t0 and isinstance(a, Aviso) and a.clave == "scroll")
    assert t_aviso - t0 >= 0.5 - 1e-6
    assert sim.nucleo.maquina.cuenta["scroll"] == 1
    assert ruedas(sim, t0) == [] and clics(sim, t0) == []      # quieta: no pasa nada todavía
    sim.durante(200, s.en("apuntar", C))
    assert sim.estado == K.ACTIVO
    soltar_al_final(sim)


@pytest.mark.parametrize("mano", ["relajada", "casi"])
def test_la_mano_relajada_nunca_arranca_el_scroll(mano):
    """La mano abierta relajada (dedos poco separados) ni quieta ni moviéndose pasa página."""
    sim = preparar()
    t0 = sim.t
    postura = s.casi_estirada() if mano == "casi" else "relajada"
    sim.durante(1500, s.en(postura, C))
    cuadros(sim, s.vaiven(C, 0.10, 30, postura))
    sim.durante(1500, s.en(postura, C))
    assert ruedas(sim, t0) == [] and "scroll" not in avisos(sim, t0)
    assert all(r.estado != K.PASANDO_PAGINA for t, r in sim.resultados if t >= t0)
    soltar_al_final(sim)


@pytest.mark.parametrize("postura", s.CONFUSIONES_PALMA)
def test_las_senas_viejas_no_arrancan_el_scroll(postura):
    sim = preparar()
    t0 = sim.t
    sim.durante(1500, s.en(postura, C))
    cuadros(sim, s.vaiven(C, 0.08, 20, postura))
    assert ruedas(sim, t0) == [] and "scroll" not in avisos(sim, t0)
    assert all(r.estado != K.PASANDO_PAGINA for t, r in sim.resultados if t >= t0)
    soltar_al_final(sim)


def test_la_palma_que_se_mueve_no_arranca():
    """Palma estirada moviéndose despacio (más de 0,10 anchos por segundo): no pasa página."""
    sim = preparar()
    t0 = sim.t
    cuadros(sim, s.trayecto("abierta", (0.30, 0.5), (0.70, 0.5), 60))    # 0,2 anchos/s durante 2 s
    cuadros(sim, s.trayecto("abierta", (0.70, 0.5), (0.70, 0.30), 30))   # 0,15 anchos/s hacia arriba
    assert ruedas(sim, t0) == [] and sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


def test_palma_justo_despues_de_un_arrastre_no_arranca():
    sim = preparar()
    sim.durante(300, s.en("pellizco", C))
    cuadros(sim, s.trayecto("pellizco", C, (0.65, 0.5), 8))
    t0 = sim.t
    sim.durante(900, s.en("abierta", (0.65, 0.5)))           # < 1 s + medio segundo quieta
    assert sim.nucleo.maquina.gesto is None and "scroll" not in avisos(sim, t0)
    sim.durante(1000, s.en("abierta", (0.65, 0.5)))          # ya pasó el segundo: ahora sí
    assert sim.nucleo.maquina.gesto == "scroll"
    soltar_al_final(sim)


def test_palma_justo_despues_de_un_giro_no_arranca():
    sim = preparar(modo="3D", perfil="edwin3d")
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.68, 0.5), 12))
    assert sim.nucleo.maquina.gesto == "orbita1"
    t0 = sim.t
    sim.durante(900, s.en("abierta", (0.68, 0.5)))
    assert sim.nucleo.maquina.gesto is None and ruedas(sim, t0) == []
    # revisión 1.0.2: la palma que soltó el giro nunca pasa página (mirar el modelo no es zoom)...
    sim.durante(2000, s.en("abierta", (0.68, 0.5)))
    assert sim.nucleo.maquina.gesto is None and ruedas(sim, t0) == []
    # ... hasta que la mano haga otra seña
    sim.durante(200, s.en("apuntar", (0.68, 0.5)))
    sim.durante(1000, s.en("abierta", (0.68, 0.5)))
    assert sim.nucleo.maquina.gesto == "scroll"
    soltar_al_final(sim)


def test_la_palma_del_golpe_no_arranca_el_scroll():
    """Abrir de golpe = despiezar; esa palma no pasa página aunque se quede quieta."""
    cfg = {"gestos": {"por_programa": {"generico": {"abrir_golpe": "Ctrl+Alt+U"}}}}
    sim = preparar(cfg=cfg)
    sim.durante(150, s.en("puno", C))                         # (sin llegar al clic derecho)
    t0 = sim.t
    cuadros(sim, s.abrir_de_golpe(C, 2))
    sim.durante(2000, s.en("abierta", C))
    assert pulsados(sim, t0) == [("ctrl", "alt", "u")]
    assert sim.nucleo.maquina.gesto is None and ruedas(sim, t0) == []
    sim.durante(300, s.en("apuntar", C))                      # deja la palma...
    empezar_scroll(sim)                                       # ... y al volver, sí
    soltar_al_final(sim)


def test_scroll_apagado_no_hace_nada():
    sim = preparar(cfg={"scroll": {"palma": False}})
    t0 = sim.t
    sim.durante(1500, s.en("abierta", C))
    cuadros(sim, s.trayecto("abierta", C, ARRIBA, 10))
    assert ruedas(sim, t0) == [] and sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


def test_scroll_no_arranca_en_pausa():
    sim = preparar()
    sim.orden(sim.nucleo.pausar(sim.t))
    t0 = sim.t
    sim.durante(1500, s.en("abierta", C))
    assert sim.nucleo.maquina.gesto is None and ruedas(sim, t0) == []
    soltar_al_final(sim)


# =============================================================== scroll: rueda
def test_subir_la_mano_es_rueda_negativa_y_bajar_positiva():
    sim = preparar()
    empezar_scroll(sim)
    t0 = sim.t
    cuadros(sim, s.trayecto("abierta", C, ARRIBA, 12))       # 0,12 del alto = ~5 muescas
    sim.durante(300, s.en("abierta", ARRIBA))
    sube = ruedas(sim, t0)
    assert sube and all(d == -120 for d in sube) and 4 <= len(sube) <= 6, sube
    t1 = sim.t
    cuadros(sim, s.trayecto("abierta", ARRIBA, C, 12))
    sim.durante(300, s.en("abierta", C))
    baja = ruedas(sim, t1)
    assert baja and all(d == 120 for d in baja) and abs(len(baja) - len(sube)) <= 1, (sube, baja)
    assert clics(sim, t0) == [] and pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_invertir_el_scroll():
    sim = preparar(cfg={"scroll": {"invertir": True}})
    empezar_scroll(sim)
    t0 = sim.t
    cuadros(sim, s.trayecto("abierta", C, ARRIBA, 12))
    sim.durante(300, s.en("abierta", ARRIBA))
    assert ruedas(sim, t0) and all(d == 120 for d in ruedas(sim, t0))
    soltar_al_final(sim)


def test_paso_del_scroll():
    resultados = []
    for paso in (0.05, 0.0125):
        sim = preparar(cfg={"scroll": {"paso": paso}})
        empezar_scroll(sim)
        t0 = sim.t
        cuadros(sim, s.trayecto("abierta", C, (0.55, 0.40), 40))
        sim.durante(300, s.en("abierta", (0.55, 0.40)))
        resultados.append(len(ruedas(sim, t0)))
        soltar_al_final(sim)
    assert resultados[1] >= 3 * resultados[0] > 0, resultados


def test_mano_quieta_con_temblor_no_pasa_pagina():
    sim = preparar()
    empezar_scroll(sim)
    t0 = sim.t
    rng = np.random.default_rng(7)
    for _ in range(60):
        sim.cuadro(s.en("abierta", (C[0] + rng.normal(0, 0.002), C[1] + rng.normal(0, 0.002))))
    assert ruedas(sim, t0) == []
    soltar_al_final(sim)


@pytest.mark.parametrize("perfil,modo,limite", [("edwin2d", "2D", 8), ("generico", "2D", 20),
                                                 ("navegador", "2D", 20), ("sketchup", "3D", 10)])
def test_cubeta_del_scroll(perfil, modo, limite):
    """La mano muy rápida no pasa del máximo de muescas por segundo (edwin2d: 8 y enteras)."""
    sim = preparar(modo=modo, perfil=perfil)
    empezar_scroll(sim)
    t0 = sim.t
    for _ in range(3):
        cuadros(sim, s.trayecto("abierta", (0.55, 0.65), (0.55, 0.30), 6))
        cuadros(sim, s.trayecto("abierta", (0.55, 0.30), (0.55, 0.65), 6))
    tiempos = [t for t, a in sim.acciones if t >= t0 and isinstance(a, Rueda)]
    deltas = ruedas(sim, t0)
    assert deltas and all(abs(d) == 120 for d in deltas), deltas
    for t in tiempos:                                  # en cualquier ventana de 1 s
        assert sum(1 for u in tiempos if t <= u < t + 1.0) <= limite + 1
    soltar_al_final(sim)


def test_edwin3d_acepta_fracciones_al_bajar_y_enteras_al_subir():
    sim = preparar(modo="3D", perfil="edwin3d")
    empezar_scroll(sim)
    t0 = sim.t
    cuadros(sim, s.trayecto("abierta", C, (0.55, 0.60), 40))     # bajar despacio = rueda positiva
    sim.durante(300, s.en("abierta", (0.55, 0.60)))
    baja = ruedas(sim, t0)
    assert baja and all(d > 0 for d in baja) and any(d % 120 for d in baja), baja
    t1 = sim.t
    cuadros(sim, s.trayecto("abierta", (0.55, 0.60), (0.55, 0.45), 40))
    sim.durante(300, s.en("abierta", (0.55, 0.45)))
    sube = ruedas(sim, t1)
    assert sube and all(d == -120 for d in sube), sube    # alejar en EDWIN CNC 3D: muescas enteras
    soltar_al_final(sim)


# =============================================================== scroll: fin
def test_cerrar_la_mano_termina_sin_clic_derecho_ni_armar():
    cfg = {"gestos": {"por_programa": {"generico": {"cerrar_golpe": "Ctrl+G", "abrir_golpe": "Ctrl+Shift+G"}}}}
    sim = preparar(cfg=cfg)
    empezar_scroll(sim)
    cuadros(sim, s.trayecto("abierta", C, ARRIBA, 6))
    t0 = sim.t
    cuadros(sim, s.cerrar_de_golpe(ARRIBA, 2))
    sim.durante(800, s.en("puno", ARRIBA))
    assert sim.nucleo.maquina.gesto is None and sim.estado == K.ACTIVO
    assert clics(sim, t0) == [] and pulsados(sim, t0) == []
    assert "scroll_fin" in avisos(sim, t0)
    # abrir ese puño de golpe tampoco despieza
    t1 = sim.t
    cuadros(sim, s.abrir_de_golpe(ARRIBA, 2))
    sim.durante(400, s.en("abierta", ARRIBA))
    assert pulsados(sim, t1) == []
    # y un puño nuevo, más tarde, vuelve a dar clic derecho
    sim.durante(400, s.en("apuntar", ARRIBA))
    sim.durante(400, s.en("puno", ARRIBA))
    assert [ev[1] for ev in clics(sim, t1)] == ["der"]
    soltar_al_final(sim)


@pytest.mark.parametrize("fin", ["apuntar", "pellizco", "pellizco_anular", "v"])
def test_otras_senas_terminan_el_scroll_sin_clic(fin):
    sim = preparar()
    empezar_scroll(sim)
    t0 = sim.t
    sim.durante(300, s.en(fin, C))
    assert sim.nucleo.maquina.gesto is None
    assert clics(sim, t0) == [] and ruedas(sim, t0) == []
    sim.durante(300, s.en("apuntar", C))
    soltar_al_final(sim)


def test_un_cuadro_suelto_no_termina_el_scroll():
    sim = preparar()
    empezar_scroll(sim)
    sim.cuadro(s.en("apuntar", C))
    sim.cuadro(s.en("abierta", C))
    sim.cuadro(s.en("puno", C))
    sim.cuadro(s.en("abierta", C))
    assert sim.nucleo.maquina.gesto == "scroll"
    soltar_al_final(sim)


def test_mano_perdida_pausa_y_cambio_de_programa_terminan_el_scroll():
    for orden in ("perdida", "pausa", "programa"):
        sim = preparar()
        empezar_scroll(sim)
        if orden == "perdida":
            sim.durante(300, [])
        elif orden == "pausa":
            sim.orden(sim.nucleo.alternar_pausa(sim.t))
        else:
            sim.orden(sim.nucleo.cambiar_perfil(sim.t, P.PERFILES["navegador"]))
        assert sim.nucleo.maquina.gesto is None, orden
        soltar_al_final(sim)


def test_durante_el_scroll_nada_mas_se_presiona():
    sim = preparar(cfg={"senas": {"menique": "enter"}})
    empezar_scroll(sim)
    t0 = sim.t
    m = sim.nucleo.maquina
    assert m.tecla_clic(sim.t, True) == []            # la tecla de clic no baja el botón
    assert m.tecla_clic(sim.t, False) == []
    for _ in range(3):
        cuadros(sim, s.vaiven(C, 0.08, 15, "abierta"))
    assert clics(sim, t0) == [] and pulsados(sim, t0) == []
    assert m.gesto == "scroll" and sim.base == K.ACTIVO
    soltar_al_final(sim)


# =============================================================== scroll: inercia
def lanzar(sim, hasta=(0.55, 0.30), n=4, fin="apuntar"):
    """Mueve la palma rápido hacia arriba y termina con ``fin`` (2 cuadros)."""
    cuadros(sim, s.trayecto("abierta", C, hasta, n))
    cuadros(sim, [s.en(fin, hasta), s.en(fin, hasta)])


def test_soltar_rapido_la_pagina_sigue_y_frena_sola():
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim)
    m = sim.nucleo.maquina
    assert m.gesto == "scroll_inercia" and m.inercia_activa and sim.estado == K.PASANDO_PAGINA
    t0 = sim.t
    sim.durante(4000, s.en("apuntar", (0.55, 0.30)))
    sigue = ruedas(sim, t0)
    assert len(sigue) >= 4 and all(d == -120 for d in sigue), sigue
    assert m.gesto is None and sim.estado == K.ACTIVO
    # frenó: al final van más separadas que al principio
    tiempos = [t for t, a in sim.acciones if t >= t0 and isinstance(a, Rueda)]
    assert tiempos[-1] - tiempos[-2] > tiempos[1] - tiempos[0]
    soltar_al_final(sim)


def test_inercia_apagada_solo_termina():
    sim = preparar(cfg={"scroll": {"inercia": False}})
    empezar_scroll(sim)
    lanzar(sim)
    assert sim.nucleo.maquina.gesto is None
    t0 = sim.t
    sim.durante(1000, s.en("apuntar", (0.55, 0.30)))
    assert ruedas(sim, t0) == []
    soltar_al_final(sim)


def test_soltar_despacio_no_sigue():
    sim = preparar()
    empezar_scroll(sim)
    cuadros(sim, s.trayecto("abierta", C, ARRIBA, 30))
    sim.durante(200, s.en("abierta", ARRIBA))
    sim.durante(200, s.en("apuntar", ARRIBA))
    assert sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


def test_terminar_con_el_puno_no_deja_la_pagina_andando():
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim, fin="puno")
    assert sim.nucleo.maquina.gesto is None
    t0 = sim.t
    sim.durante(800, s.en("puno", (0.55, 0.30)))
    assert ruedas(sim, t0) == [] and clics(sim, t0) == []
    soltar_al_final(sim)


def test_friccion_alta_frena_antes():
    cuentas = []
    for fr in (0.5, 6.0):
        sim = preparar(cfg={"scroll": {"friccion": fr}})
        empezar_scroll(sim)
        lanzar(sim)
        t0 = sim.t
        sim.durante(3000, s.en("apuntar", (0.55, 0.30)))
        cuentas.append(len(ruedas(sim, t0)))
        soltar_al_final(sim)
    assert cuentas[0] > cuentas[1], cuentas


def test_atrapar_con_el_puno_la_detiene():
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim)
    sim.durante(100, s.en("apuntar", (0.55, 0.30)))
    sim.durante(100, s.en("puno", (0.55, 0.30)))
    assert sim.nucleo.maquina.gesto is None
    t0 = sim.t
    sim.durante(800, s.en("puno", (0.55, 0.30)))
    assert ruedas(sim, t0) == [] and clics(sim, t0) == []
    soltar_al_final(sim)


def test_atrapar_con_la_palma_vuelve_a_seguir_la_mano():
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim)
    sim.durante(100, s.en("abierta", (0.55, 0.30)))
    assert sim.nucleo.maquina.gesto == "scroll"
    t0 = sim.t
    sim.durante(500, s.en("abierta", (0.55, 0.30)))
    assert ruedas(sim, t0) == []                      # quieta: la página ya no anda sola
    cuadros(sim, s.trayecto("abierta", (0.55, 0.30), (0.55, 0.42), 12))
    assert ruedas(sim, t0) and all(d == 120 for d in ruedas(sim, t0))
    soltar_al_final(sim)


@pytest.mark.parametrize("freno", ["tecla", "sin_mano", "pausa"])
def test_frenos_de_la_inercia_del_scroll(freno):
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim)
    assert sim.nucleo.maquina.gesto == "scroll_inercia"
    if freno == "tecla":
        sim.orden(sim.nucleo.frenar(sim.t))
    elif freno == "sin_mano":
        sim.durante(300, [])
    else:
        sim.orden(sim.nucleo.alternar_pausa(sim.t))
    assert sim.nucleo.maquina.gesto is None and not sim.nucleo.maquina.inercia_activa
    t0 = sim.t
    sim.durante(600, s.en("apuntar", (0.55, 0.30)))
    assert ruedas(sim, t0) == []
    soltar_al_final(sim)


def test_la_inercia_nunca_dura_mas_de_6_segundos():
    sim = preparar(cfg={"scroll": {"friccion": 0.3}})
    empezar_scroll(sim)
    lanzar(sim)
    sim.durante(6200, s.en("apuntar", (0.55, 0.30)))
    assert sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


def test_frenar_el_giro_sigue_funcionando():
    """El freno del paquete C no cambia el de la pieza (paquete B)."""
    sim = preparar(modo="3D", perfil="edwin3d", cfg={"orbita": {"inercia": True}})
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (0.62, 0.5), 4))
    cuadros(sim, s.trayecto("puno", (0.62, 0.5), (0.80, 0.5), 3))
    sim.cuadro(s.en("abierta", (0.80, 0.5)))
    assert sim.nucleo.maquina.gesto == "inercia"
    sim.orden(sim.nucleo.frenar(sim.t))
    assert sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


# =============================================================== barrido
# revisión 1.0.2: el barrido es con la palma ESTIRADA (con la mano relajada se mueve el puntero)
def barrer(sim, desde=(0.40, 0.5), dx=0.30, n=5, postura="abierta", quieta_ms=300, dy=0.0):
    sim.durante(quieta_ms, s.en(postura, desde))
    t0 = sim.t
    cuadros(sim, s.barrido(desde, dx, n, postura, dy=dy))
    sim.durante(100, s.en(postura, (desde[0] + dx, desde[1] + dy)))
    return t0


@pytest.mark.parametrize("perfil,der,izq", [("generico", ("derecha",), ("izquierda",)),
                                            ("navegador", ("alt", "derecha"), ("alt", "izquierda"))])
def test_barrido_manda_siguiente_y_anterior(perfil, der, izq):
    sim = preparar(perfil=perfil)
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    assert pulsados(sim, t0) == [der]
    assert "barrido_der" in avisos(sim, t0)
    sim.durante(1200, s.en("relajada", (0.65, 0.5)))
    t1 = barrer(sim, (0.65, 0.5), -0.30)
    assert pulsados(sim, t1) == [izq]
    assert clics(sim, t0) == [] and ruedas(sim, t0) == []
    soltar_al_final(sim)


def test_barrido_con_la_palma_estirada():
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.5), 0.30, postura="abierta", quieta_ms=250)
    assert pulsados(sim, t0) == [("derecha",)]
    soltar_al_final(sim)


@pytest.mark.parametrize("dx,n", [(0.22, 7), (0.25, 6), (0.30, 5)])
def test_mover_rapido_el_puntero_con_la_mano_relajada_no_es_barrido(dx, n):
    """Revisión 1.0.2: en el perfil genérico la mano relajada mueve el puntero; moverla rápido de
    un lado a otro no debe mandar una flecha."""
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.5), dx, n, postura="relajada")
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


@pytest.mark.parametrize("perfil,modo", [("edwin2d", "2D"), ("sketchup", "3D"), ("edwin3d", "3D"),
                                         ("freecad", "3D")])
def test_en_programas_de_diseno_el_barrido_no_hace_nada(perfil, modo):
    sim = preparar(modo=modo, perfil=perfil)
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    sim.durante(1200, s.en("relajada", (0.65, 0.5)))
    barrer(sim, (0.65, 0.5), -0.30)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_el_regreso_de_la_mano_no_dispara_al_reves():
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    cuadros(sim, s.barrido((0.65, 0.5), -0.30, 5, "abierta"))           # vuelve enseguida
    sim.durante(300, s.en("relajada", (0.35, 0.5)))
    assert pulsados(sim, t0) == [("derecha",)]
    soltar_al_final(sim)


def test_dos_barridos_seguidos_solo_cuenta_uno_en_800ms():
    sim = preparar()
    t0 = barrer(sim, (0.15, 0.5), 0.25)
    cuadros(sim, s.barrido((0.40, 0.5), 0.25, 5, "abierta"))            # otra vez enseguida
    sim.durante(100, s.en("relajada", (0.65, 0.5)))
    assert pulsados(sim, t0) == [("derecha",)]
    sim.durante(900, s.en("relajada", (0.40, 0.5)))
    t1 = barrer(sim, (0.40, 0.5), 0.25)
    assert pulsados(sim, t1) == [("derecha",)]
    soltar_al_final(sim)


def test_una_mano_que_entra_por_el_lado_no_dispara():
    sim = preparar()
    sim.durante(500, [])
    t0 = sim.t
    cuadros(sim, s.entrar_por_el_lado(0.5, 0.45, 5, "relajada"))
    sim.durante(500, s.en("relajada", (0.45, 0.5)))
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


@pytest.mark.parametrize("postura", ["apuntar", "puno", "v", "juntos"])
def test_las_senas_viejas_rapidas_no_disparan_el_barrido(postura):
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.5), 0.30, postura=postura)
    sim.durante(1200, s.en(postura, (0.65, 0.5)))
    barrer(sim, (0.65, 0.5), -0.30, postura=postura)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_arrastrar_rapido_no_dispara_el_barrido():
    sim = preparar()
    sim.durante(300, s.en("pellizco", (0.35, 0.5)))
    t0 = sim.t
    cuadros(sim, s.barrido((0.35, 0.5), 0.30, 5, "pellizco"))
    sim.durante(300, s.en("pellizco", (0.65, 0.5)))
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


@pytest.mark.parametrize("dx,dy,n", [(0.30, 0.0, 30), (0.0, 0.25, 5), (0.22, 0.12, 5), (0.15, 0.0, 5)])
def test_movimientos_que_no_son_barrido(dx, dy, n):
    """Despacio, vertical, en diagonal o corto: no es un barrido."""
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.40), dx, n, dy=dy)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_barrido_apagado_no_hace_nada():
    sim = preparar(cfg={"gestos": {"barrido": False}})
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_barrido_por_programa():
    cfg = {"gestos": {"por_programa": {"edwin2d": {"barrido_der": "Ctrl+Tab"},
                                       "generico": {"barrido_der": "", "barrido_izq": "AvPág"}}}}
    sim = preparar(perfil="edwin2d", cfg=cfg)
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    assert pulsados(sim, t0) == [("ctrl", "tab")]
    soltar_al_final(sim)
    sim = preparar(cfg=cfg)
    t0 = barrer(sim, (0.35, 0.5), 0.30)
    assert pulsados(sim, t0) == []                     # vacío = nada
    sim.durante(1200, s.en("relajada", (0.65, 0.5)))
    t1 = barrer(sim, (0.65, 0.5), -0.30)
    assert pulsados(sim, t1) == [("avpag",)]
    soltar_al_final(sim)


def test_barrido_con_boton_abajo_o_en_pausa_no_sale():
    sim = preparar()
    m = sim.nucleo.maquina
    sim.durante(300, s.en("relajada", (0.35, 0.5)))
    sim.orden(m.tecla_clic(sim.t, True))                # la tecla sostiene el botón izquierdo
    t0 = sim.t
    cuadros(sim, s.barrido((0.35, 0.5), 0.30, 5, "abierta"))
    sim.orden(m.tecla_clic(sim.t, False))
    assert pulsados(sim, t0) == []
    sim.orden(sim.nucleo.pausar(sim.t))
    t1 = barrer(sim, (0.65, 0.5), -0.30)
    assert pulsados(sim, t1) == []
    soltar_al_final(sim)


def test_el_barrido_no_cuenta_como_otra_sena():
    sim = preparar()
    t0 = barrer(sim, (0.35, 0.5), 0.30, postura="abierta", quieta_ms=200)
    evs = [ev for t, ev in sim.salida.eventos if t >= t0 and ev[0] in ("boton", "rueda")]
    assert evs == [] and sim.base == K.ACTIVO and sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


# =============================================================== perfiles
def test_perfil_navegador_y_programas_de_diseno():
    for exe in ("chrome.exe", r"C:\Program Files\Mozilla Firefox\FIREFOX.EXE", "msedge.exe", "brave.exe",
                "opera.exe"):
        assert P.perfil_para_exe(exe).clave == "navegador"
    nav = P.PERFILES["navegador"]
    assert nav.barrido_der == "Alt+Derecha" and nav.barrido_izq == "Alt+Izquierda" and not nav.diseno
    assert nav.orbitar == P.GENERICO.orbitar and nav.combinacion_desplazar("2D") == P.GENERICO.combinacion_desplazar("2D")
    for clave in ("edwin3d", "sketchup", "freecad", "freecad_blender", "blender", "edwin2d"):
        p = P.PERFILES[clave]
        assert p.diseno and P.gesto_de(p, "barrido_der", {}) is None, clave
    assert P.gesto_de(P.GENERICO, "barrido_der", {}) == "Derecha"
    assert P.gesto_de(P.GENERICO, "barrido_izq", {"gestos": {"por_programa": {"generico": {"barrido_izq": ""}}}}) is None


def test_perfil_personalizado_con_barrido():
    pers = {"mio": {"nombre": "Visor", "exes": ["visor.exe"], "barrido_der": "AvPág", "barrido_izq": 3,
                    "diseno": "si"}}
    p = P.cargar_personalizados(pers)["mio"]
    assert p.barrido_der == "AvPág" and p.barrido_izq is None and p.diseno is False


# =============================================================== mano baja
def test_recortar_zona_para_que_no_salga_la_muneca():
    z = {"x0": 0.2, "y0": 0.25, "x1": 0.8, "y1": 0.90}
    r = MB.recortar_zona(z, 0.30)
    assert r["y1"] == pytest.approx(1 - 1.1 * 0.30, abs=1e-3) and r["y0"] == 0.25 and r["x0"] == 0.2
    assert z["y1"] == 0.90                                # no cambia la original
    r = MB.recortar_zona({"x0": 0.2, "y0": 0.60, "x1": 0.8, "y1": 0.90}, 0.40)
    assert r["y1"] == pytest.approx(0.56, abs=1e-3) and r["y1"] - r["y0"] >= MB.ALTO_MIN_ZONA - 1e-9
    assert MB.recortar_zona(z, 0.05) == z                   # la muñeca ya cabe
    for raro in (None, "x", float("nan"), -1, 2.0):
        assert MB.recortar_zona(z, raro) == z
    r = validar({"zona": MB.recortar_zona({"x0": 0.2, "y0": 0.85, "x1": 0.8, "y1": 0.99}, 0.5)})["zona"]
    assert r["y1"] - r["y0"] >= 0.1


def test_muneca_visible():
    assert MB.muneca_visible([0.9] * 20)
    assert MB.muneca_visible([0.9] * 18 + [0.99] * 2)       # 90 %
    assert not MB.muneca_visible([0.9] * 17 + [0.99] * 3)
    assert not MB.muneca_visible([])
    assert not MB.muneca_visible([None, float("nan"), "x"])
    assert MB.muneca_visible([np.float32(0.5)] * 3)
    vista = s.mano_baja("apuntar", muneca_y=0.92)
    assert float(vista.img[0, 1]) == pytest.approx(0.92)
    assert MB.muneca_visible([float(s.mano_baja(muneca_y=0.92).img[0, 1])] * 10)
    assert not MB.muneca_visible([float(s.mano_baja(muneca_y=0.99).img[0, 1])] * 10)


def test_distancia_con_mano_baja_acepta_la_mano_mas_cerca():
    assert evaluar_distancia(0.28) == "lejos"
    assert evaluar_distancia(0.28, mano_baja=True) == "ok"
    assert evaluar_distancia(0.40, mano_baja=True) == "lejos"
    assert evaluar_distancia(0.05, mano_baja=True) == "cerca"
    assert evaluar_distancia(None, mano_baja=True) == "sin_mano"


def test_vigia_de_mano_baja_avisa_una_vez():
    v = MB.VigiaManoBaja()
    assert not v.paso(0.0, 0.10, 0.25)
    assert not v.paso(1.9, 0.10, 0.25)
    assert v.paso(2.0, 0.10, 0.25)
    assert not v.paso(5.0, 0.10, 0.25)                       # una sola vez
    assert not v.paso(5.1, 0.30, 0.25)                       # bajó: se rearma
    assert not v.paso(5.2, 0.10, 0.25)
    assert v.paso(7.3, 0.10, 0.25)
    assert not v.paso(8.0, None, 0.25) and not v.paso(8.1, float("nan"), 0.25)


def _motor_con_mano(mano_baja: bool, pos_punta, segundos: float, paso=0.5):
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    cfg = por_defecto()
    cfg["zona"]["mano_baja"] = mano_baja
    m = Motor(cfg, SalidaSimulada(), sistema=False)
    m.nucleo = Nucleo(cfg)
    m.nucleo.maquina.activar(0.0)
    t = 0.0
    out = []
    while t <= segundos:
        res = m.nucleo.procesar(t, [s.mano("apuntar", posicion=pos_punta, distancia_m=1.0)])
        m.nucleo.maquina.base = K.ACTIVO
        m._comodidad(t, res)
        t += paso
    while not m.avisos.empty():
        out.append(m.avisos.get().clave)
    return out


def test_motor_con_mano_baja_no_avisa_brazo_alto_y_pide_bajar_la_mano():
    alto = (0.5, 0.05)                    # la muñeca queda arriba de la imagen (brazo levantado)
    assert "brazo_alto" in _motor_con_mano(False, alto, 65)
    con_baja = _motor_con_mano(True, alto, 65)
    assert "brazo_alto" not in con_baja
    assert con_baja.count("baje_mano") == 1
    assert "baje_mano" not in _motor_con_mano(True, (0.5, 0.5), 10)
    assert "baje_mano" not in _motor_con_mano(False, alto, 10)


def test_vista_trae_la_muneca_y_el_alto_de_la_mano():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.nucleo = Nucleo(por_defecto())
    m.camara = None
    mano = s.mano_baja("apuntar", muneca_y=0.92)
    res = m.nucleo.procesar(0.0, [mano])
    m._publicar(res, None)
    v = m.vistas.get_nowait()
    assert v.muneca[1] == pytest.approx(0.92, abs=1e-6)
    assert v.alto_mano == pytest.approx(0.92 - float(mano.img[:, 1].min()), abs=1e-6)


# =============================================================== configuración
def test_config_de_la_101_carga_con_los_valores_de_fabrica_nuevos(tmp_path):
    viejo = copy.deepcopy(FABRICA)
    del viejo["scroll"]
    del viejo["gestos"]                       # (tampoco existía en la 1.0.1)
    del viejo["zona"]["mano_baja"]
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(viejo), encoding="utf-8")
    c = Configuracion(ruta)
    d = c.cargar()
    assert d["scroll"] == {"palma": True, "inercia": True, "friccion": 2.0, "invertir": False, "paso": 0.025}
    assert d["gestos"]["barrido"] is True and d["zona"]["mano_baja"] is False
    assert d["zona"]["codo_apoyado"] is True             # se deja aunque no se usa
    assert c.aviso is None and not c.problemas


@pytest.mark.parametrize("ruta,malo", [
    ("scroll.palma", "si"), ("scroll.inercia", 1), ("scroll.friccion", 0.0), ("scroll.friccion", 9.0),
    ("scroll.friccion", float("nan")), ("scroll.invertir", None), ("scroll.paso", 0.5), ("scroll.paso", "x"),
    ("gestos.barrido", "no"), ("zona.mano_baja", 1)])
def test_valores_malos_vuelven_a_fabrica(ruta, malo):
    datos = copy.deepcopy(FABRICA)
    d = datos
    partes = ruta.split(".")
    for k in partes[:-1]:
        d = d[k]
    d[partes[-1]] = malo
    probl = []
    out = validar(datos, problemas=probl)
    v, f = out, FABRICA
    for k in partes:
        v, f = v[k], f[k]
    assert v == f and probl


def test_claves_nuevas_tienen_rango():
    assert RANGOS["scroll.friccion"] == (0.3, 6.0) and RANGOS["scroll.paso"] == (0.005, 0.10)
    assert validar({"scroll": "nada"})["scroll"] == FABRICA["scroll"]
    assert validar({"scroll": {"paso": 0.05, "friccion": 1}})["scroll"]["paso"] == 0.05


def test_maquina_sin_validar_no_se_rompe_con_valores_raros():
    cfg = {"scroll": {"palma": "si", "inercia": None, "friccion": "mucha", "invertir": 3, "paso": -1},
           "gestos": {"barrido": None, "por_programa": {"generico": {"barrido_der": 5}}}}
    sim = preparar(cfg=cfg)
    m = sim.nucleo.maquina
    assert m.scroll_palma and m.scroll_inercia_on and m.scroll_friccion == 2.0
    assert m.scroll_invertir is False and m.scroll_paso == 0.025 and m.barrido_on
    empezar_scroll(sim)
    lanzar(sim)
    sim.orden(sim.nucleo.frenar(sim.t))
    sim.durante(300, s.en("apuntar", C))
    t0 = barrer(sim, (0.65, 0.5), -0.30)
    assert pulsados(sim, t0) == [("izquierda",)]
    soltar_al_final(sim)
    sim = Sim(cfg={"scroll": None, "gestos": "x"})
    assert sim.nucleo.maquina.scroll_palma and sim.nucleo.maquina.barrido_on


# =============================================================== secuencias sintéticas
def test_secuencias_sinteticas_del_paquete_c():
    q = s.quieta("abierta", (0.4, 0.5), 3)
    assert len(q) == 3 and all(np.allclose(m.img, q[0].img) for m in q)
    v = s.vaiven((0.5, 0.5), 0.1, 8)
    ys = [m.img[[0, 5, 9, 13, 17], 1].mean() for m in v]
    assert min(ys) == pytest.approx(0.4, abs=1e-6) and max(ys) == pytest.approx(0.6, abs=1e-6)
    assert ys[0] < 0.5                                       # primero sube
    b = s.barrido((0.3, 0.5), 0.2, 4)
    assert b[-1].img[[0, 5, 9, 13, 17], 0].mean() == pytest.approx(0.5, abs=1e-9)
    e = s.entrar_por_el_lado(0.5, 0.4, 5)
    assert e[0].img[[0, 5, 9, 13, 17], 0].mean() < 0.15
    from lycan_mouse_control.senas import Clasificador
    c = Clasificador()
    for _ in range(8):
        c.clasificar(s.casi_estirada())
    assert c.sena.value == "ABIERTA" and not c.medidas.palma_estirada
    assert 0.54 <= c.medidas.sep < 0.60


# =============================================================== motor y gancho
def test_motor_avisa_la_inercia_del_scroll_al_gancho_y_la_frena_con_una_tecla():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    from lycan_mouse_control.sistema import teclado as T
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim)
    assert sim.nucleo.maquina.gesto == "scroll_inercia"
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.nucleo = sim.nucleo
    m.sincronizar_gancho()
    assert m.estado_gancho.inercia_activa is True
    assert T.decidir(0x41, 0x1E, False, True, False, 0, m.estado_gancho) == (False, ("frenar",))
    m.ordenes.put(("frenar",))
    m._atender_ordenes()
    m.sincronizar_gancho()
    assert sim.nucleo.maquina.gesto is None and m.estado_gancho.inercia_activa is False


def test_estado_pasando_pagina_tiene_color_y_textos():
    from lycan_mouse_control.ui.textos import TXT
    assert K.PASANDO_PAGINA in K.COLORES_ESTADO
    assert "estado_PASANDO_PAGINA" in TXT and "ayuda_PASANDO_PAGINA" in TXT


# =============================================================== al azar
@pytest.mark.parametrize("semilla", range(8))
def test_palmas_y_barridos_al_azar_nada_queda_presionado(semilla):
    """Palmas quietas, vaivenes, barridos, puños, pellizcos, manos perdidas, teclas que frenan y
    pausas: nunca queda un botón abajo, nunca sale rueda o tecla con botones abajo."""
    rng = np.random.default_rng(300 + semilla)
    perfil, modo = [("generico", "2D"), ("navegador", "2D"), ("edwin2d", "2D"), ("edwin3d", "3D")][semilla % 4]
    cfg = {"scroll": {"friccion": float(rng.uniform(0.3, 6)), "invertir": bool(semilla % 2)},
           "orbita": {"inercia": True}}
    sim = preparar(modo=modo, perfil=perfil, cfg=cfg, fps=float(rng.choice([15, 24, 30])))
    m = sim.nucleo.maquina
    pos = np.array(C)
    postura = "abierta"
    for _ in range(int(9 * 30)):
        r = rng.random()
        if r < 0.08:
            postura = str(rng.choice(["abierta", "abierta", "relajada", "apuntar", "puno", "pellizco",
                                      "pellizco_anular"]))
        paso = 0.03 if rng.random() < 0.15 else 0.004
        pos = np.clip(pos + rng.normal(0, paso, 2), 0.1, 0.9)
        if rng.random() < 0.02:
            sim.cuadro([])
        else:
            sim.cuadro(s.en(postura, tuple(pos)))
        q = rng.random()
        if q < 0.01:
            sim.orden(sim.nucleo.frenar(sim.t))
        elif q < 0.015:
            sim.orden(m.tecla_clic(sim.t, True))
        elif q < 0.025:
            sim.orden(m.tecla_clic(sim.t, False))
        elif q < 0.028:
            sim.orden(sim.nucleo.alternar_pausa(sim.t))
        sim.invariantes(final=False)
    sim.orden(m.tecla_clic(sim.t, False))
    sim.durante(300, [])
    soltar_al_final(sim)
    assert not sim.nucleo.errores, sim.nucleo.ultimo_error
    _ = (Bajar, Clic, Pulsar)


# =============================================================== revisión 1.0.2
@pytest.mark.parametrize("postura", ["relajada"])
def test_la_mano_relajada_termina_el_scroll_a_los_300ms(postura):
    """Bajar la mano relajada al teclado no sigue pasando página (en diseño sería zoom)."""
    sim = preparar(modo="3D", perfil="edwin3d")
    empezar_scroll(sim)
    p = s.casi_estirada() if postura == "casi" else "relajada"
    sim.durante(330, s.en(p, C))
    assert sim.nucleo.maquina.gesto is None
    t0 = sim.t
    cuadros(sim, s.trayecto(p, C, (C[0], 0.95), 10))
    sim.durante(300, [])
    assert ruedas(sim, t0) == []
    soltar_al_final(sim)


def test_la_palma_que_baja_al_borde_termina_el_scroll():
    sim = preparar()
    empezar_scroll(sim)
    cuadros(sim, s.trayecto("abierta", C, (C[0], 0.93), 6))
    assert sim.nucleo.maquina.gesto is None
    soltar_al_final(sim)


@pytest.mark.parametrize("fin", ["apuntar", "pellizco"])
def test_en_diseno_el_scroll_no_sigue_solo(fin):
    """En los programas de diseño la rueda es zoom: nunca sigue andando sola."""
    sim = preparar(modo="3D", perfil="edwin3d")
    empezar_scroll(sim)
    lanzar(sim, fin=fin)
    t0 = sim.t
    sim.durante(2000, s.en(fin, (0.55, 0.30)))
    assert sim.nucleo.maquina.gesto is None and ruedas(sim, t0) == []
    soltar_al_final(sim)


def test_un_pellizco_no_deja_la_pagina_andando_sola():
    sim = preparar()
    empezar_scroll(sim)
    lanzar(sim, fin="pellizco")
    sim.durante(150, s.en("pellizco", (0.55, 0.30)))
    t0 = sim.t
    assert sim.nucleo.maquina.gesto is None
    sim.durante(1000, s.en("pellizco", (0.55, 0.30)))
    assert ruedas(sim, t0) == []
    soltar_al_final(sim)
