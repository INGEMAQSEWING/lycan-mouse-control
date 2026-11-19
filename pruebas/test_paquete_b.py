"""1.0.2 paquete B «Girar con un puño»: girar con un puño, lanzar con inercia y golpe.

Todo con manos sintéticas y la salida simulada: nunca se abre la cámara ni se pone el gancho.
"""
import copy
import json
import math

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles as P
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.acciones import Aviso, Clic, MoverDelta, Pulsar
from lycan_mouse_control.config import FABRICA, OPCIONES, RANGOS, Configuracion, validar
from lycan_mouse_control.gestos_puno import PUNO_GIRA, PUNO_QUIETO
from test_estados import soltar_al_final

C = (0.55, 0.50)          # centro de la palma
ATAJOS = {"abrir_golpe": "Ctrl+Alt+U", "cerrar_golpe": "Ctrl+Alt+J"}


def golpes(perfil="edwin3d", **extra):
    """Config con atajos de golpe para ``perfil``."""
    return {"gestos": {"por_programa": {perfil: dict(ATAJOS)}}, **extra}


def preparar(modo="3D", perfil="edwin3d", cfg=None, fps=30.0):
    sim = Sim(modo=modo, perfil=perfil, cfg=cfg, fps=fps)
    sim.activar(C)
    sim.durante(600, s.en("apuntar", C))
    return sim


def medio(sim, desde=0.0):
    return [ev[2] for t, ev in sim.salida.eventos if t >= desde and ev[0] == "boton" and ev[1] == "medio"]


def derecho(sim, desde=0.0):
    return [t for t, ev in sim.salida.eventos if t >= desde and ev == ("boton", "der", True)]


def pulsados(sim, desde=0.0):
    return [ev[1] for t, ev in sim.salida.eventos if t >= desde and ev[0] == "pulsar"]


def deltas(sim, desde=0.0):
    d = [a for a in sim.desde(desde) if isinstance(a, MoverDelta)]
    return sum(a.dx for a in d), sum(a.dy for a in d), d


def cuadros(sim, manos):
    for m in manos:
        sim.cuadro(m)


def girar(sim, hasta=(0.68, 0.50), n=12, espera_ms=100, desde=C):
    """Cierra el puño (quieto ``espera_ms``) y lo mueve de ``desde`` a ``hasta`` en ``n`` cuadros."""
    sim.durante(espera_ms, s.en("puno", desde))
    cuadros(sim, s.trayecto("puno", desde, hasta, n))


# =============================================================== girar con un puño
def test_puno_quieto_en_3d_es_clic_derecho_a_los_300ms():
    sim = preparar()
    t0 = sim.t
    sim.durante(250, s.en("puno", C))
    assert derecho(sim, t0) == []                    # a los 250 ms (la espera de la 1.0.1) todavía no
    sim.durante(200, s.en("puno", C))
    clics = derecho(sim, t0)
    assert len(clics) == 1 and clics[0] - t0 >= 0.300 - sim.dt - 1e-6
    assert medio(sim) == []
    sim.durante(300, s.en("abierta", C))
    soltar_al_final(sim)


def test_espera_del_puno_3d_se_puede_cambiar():
    sim = preparar(cfg={"senas": {"tiempos_ms": {"puno_3d": 500}}})
    t0 = sim.t
    sim.durante(600, s.en("puno", C))
    clics = derecho(sim, t0)
    assert len(clics) == 1 and clics[0] - t0 >= 0.5 - sim.dt - 1e-6
    sim.durante(300, s.en("abierta", C))
    soltar_al_final(sim)


@pytest.mark.parametrize("perfil", ["edwin3d", "sketchup"])
def test_puno_que_se_mueve_gira_con_el_boton_del_medio(perfil):
    sim = preparar(perfil=perfil)
    t0 = sim.t
    girar(sim)
    assert sim.estado == K.GIRANDO_3D
    assert sim.nucleo.maquina.gesto == "orbita1"
    sim.durante(400, s.en("puno", (0.68, 0.50)))      # el filtro alcanza a la mano
    dx, dy, d = deltas(sim, t0)
    assert medio(sim, t0) == [True]
    # (revisión 1.0.2: el giro empieza un cuadro después, con 2 cuadros de puño corrido)
    assert dx > 105 and abs(dy) < 25, (dx, dy)
    assert all(math.hypot(a.dx, a.dy) <= 61 for a in d)
    assert derecho(sim, t0) == [] and not any(isinstance(a, Clic) for a in sim.desde(t0))
    sim.durante(300, s.en("abierta", (0.68, 0.50)))
    assert medio(sim, t0) == [True, False]
    assert sim.estado == K.ACTIVO
    soltar_al_final(sim)


def test_girar_sube_y_baja():
    sim = preparar()
    t0 = sim.t
    girar(sim, hasta=(0.55, 0.62))
    sim.durante(400, s.en("puno", (0.55, 0.62)))
    dx, dy, _d = deltas(sim, t0)
    assert dy > 45 and abs(dx) < 25, (dx, dy)      # (revisión 1.0.2: arranca un cuadro después)
    sim.durante(300, s.en("abierta", (0.55, 0.62)))
    soltar_al_final(sim)


def test_rapidez_del_giro_con_un_puno():
    resultados = []
    for k in (0.6, 2.4):
        sim = preparar(cfg={"orbita": {"k_un_puno": k}})
        t0 = sim.t
        girar(sim)
        sim.durante(400, s.en("puno", (0.68, 0.50)))
        resultados.append(deltas(sim, t0)[0])
        sim.durante(300, s.en("abierta", (0.68, 0.50)))
        soltar_al_final(sim)
    assert resultados[1] > 2.5 * resultados[0] > 0, resultados


def test_puno_entre_002_y_003_no_hace_nada():
    """Movido 0,025 anchos (más que «quieto», menos que «girar»): ni clic derecho ni giro."""
    sim = preparar()
    t0 = sim.t
    dx = 0.025                                         # anchos de la imagen
    sim.durante(100, s.en("puno", C))
    cuadros(sim, s.trayecto("puno", C, (C[0] + dx, C[1]), 3))
    sim.durante(700, s.en("puno", (C[0] + dx, C[1])))
    assert derecho(sim, t0) == [] and medio(sim, t0) == []
    assert PUNO_QUIETO < dx < PUNO_GIRA
    sim.durante(300, s.en("abierta", (C[0] + dx, C[1])))
    soltar_al_final(sim)


def test_despues_del_clic_derecho_el_puno_nunca_gira():
    sim = preparar()
    t0 = sim.t
    sim.durante(400, s.en("puno", C))
    assert len(derecho(sim, t0)) == 1
    cuadros(sim, s.trayecto("puno", C, (0.70, 0.5), 10))
    sim.durante(300, s.en("puno", (0.70, 0.5)))
    assert medio(sim, t0) == []
    assert sim.nucleo.maquina.gesto is None
    # al abrir la mano, el próximo puño ya puede girar
    sim.durante(400, s.en("abierta", (0.70, 0.5)))
    t1 = sim.t
    girar(sim, desde=(0.70, 0.5), hasta=(0.58, 0.5))
    assert medio(sim, t1) == [True]
    sim.durante(300, s.en("abierta", (0.58, 0.5)))
    soltar_al_final(sim)


def test_en_2d_el_puno_que_se_mueve_sigue_dando_clic_derecho():
    sim = preparar(modo="2D", perfil="edwin2d")
    t0 = sim.t
    girar(sim)
    sim.durante(300, s.en("puno", (0.68, 0.50)))
    assert medio(sim, t0) == []
    assert len(derecho(sim, t0)) == 1
    assert sim.nucleo.maquina.gesto is None
    sim.durante(300, s.en("abierta", (0.68, 0.50)))
    soltar_al_final(sim)


@pytest.mark.parametrize("postura", ["pellizco", "apuntar", "abierta", "relajada", "pellizco_anular"])
def test_las_senas_viejas_que_se_mueven_no_giran(postura):
    """Mover la mano con otra seña nunca arranca el giro con un puño."""
    sim = preparar()
    t0 = sim.t
    sim.durante(150, s.en(postura, C))
    cuadros(sim, s.trayecto(postura, C, (0.70, 0.55), 12))
    sim.durante(200, s.en(postura, (0.70, 0.55)))
    assert sim.nucleo.maquina.gesto != "orbita1"
    assert medio(sim, t0) == []
    sim.durante(300, s.en("apuntar", (0.70, 0.55)))
    soltar_al_final(sim)


def test_abrir_y_cerrar_el_puno_moviendose_no_gira_solo():
    """El puño a medio cerrar (pasando por NINGUNA) que se mueve no es un puño: no gira."""
    sim = preparar()
    t0 = sim.t
    for k in range(12):
        f = k / 11
        P_ = s.intermedia("abierta", "puno", 0.45 + 0.1 * math.sin(k))
        sim.cuadro(s.en(P_, (C[0] + 0.12 * f, C[1])))
    assert medio(sim, t0) == []
    sim.durante(300, s.en("abierta", (0.67, 0.5)))
    soltar_al_final(sim)


def test_mano_perdida_en_pleno_giro_suelta_el_medio():
    sim = preparar()
    t0 = sim.t
    girar(sim)
    assert medio(sim, t0) == [True]
    t_perdida = sim.t
    sim.durante(400, [])
    subidas = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", False)]
    assert subidas and subidas[0] - t_perdida <= 0.150 + sim.dt + 1e-6
    soltar_al_final(sim)


def test_pausa_y_cambio_de_programa_en_pleno_giro_sueltan():
    for orden in ("pausa", "perfil"):
        sim = preparar()
        girar(sim)
        assert sim.salida.botones()[-1] == ("medio", True)
        if orden == "pausa":
            sim.orden(sim.nucleo.pausar(sim.t))
        else:
            sim.orden(sim.nucleo.cambiar_perfil(sim.t, P.PERFILES["sketchup"]))
        assert sim.salida.todo_suelto()
        assert sim.nucleo.maquina.gesto is None
        soltar_al_final(sim)


def test_girar_un_puno_con_cuadros_perdidos_no_salta():
    sim = preparar()
    t0 = sim.t
    sim.durante(100, s.en("puno", C))
    for k, m in enumerate(s.trayecto("puno", C, (0.70, 0.5), 18)):
        sim.cuadro([] if k % 4 == 3 else m)          # MediaPipe pierde la mano UN cuadro de cada 4
    sim.durante(400, s.en("puno", (0.70, 0.5)))
    dx, dy, d = deltas(sim, t0)
    assert medio(sim, t0) == [True]
    assert dx > 120 and all(math.hypot(a.dx, a.dy) <= 61 for a in d)
    sim.durante(300, s.en("abierta", (0.70, 0.5)))
    soltar_al_final(sim)


def test_salto_imposible_del_puno_se_descarta():
    sim = preparar()
    t0 = sim.t
    girar(sim)
    sim.durante(300, s.en("puno", (0.68, 0.50)))
    dx0 = deltas(sim, t0)[0]
    sim.durante(400, s.en("puno", (0.68, 0.85)))      # MediaPipe «salta» 0,35 hacia abajo
    dx1, dy1, _d = deltas(sim, t0)
    assert abs(dy1) < 30 and abs(dx1 - dx0) < 10, (dx1, dy1)
    sim.durante(300, s.en("abierta", (0.68, 0.85)))
    soltar_al_final(sim)


def test_reagarre_en_el_borde_con_un_puno():
    sim = preparar(cfg={"orbita": {"k_un_puno": 5.0}})
    t0 = sim.t
    girar(sim, hasta=(0.95, 0.50), n=20)
    sim.durante(1500, s.en("puno", (0.95, 0.50)))
    evs = medio(sim, t0)
    assert evs[:3] == [True, False, True], evs          # se suelta, vuelve al agarre y agarra de nuevo
    sim.durante(300, s.en("abierta", (0.95, 0.50)))
    soltar_al_final(sim)


# ------------------------------------------------ opción «girar con»
def test_dos_punos_es_como_la_101():
    sim = preparar(cfg={"orbita": {"girar": "dos_punos"}})
    t0 = sim.t
    girar(sim)
    sim.durante(300, s.en("puno", (0.68, 0.50)))
    assert medio(sim, t0) == [] and derecho(sim, t0) == []      # movido: ni gira ni clic derecho
    sim.durante(300, s.en("abierta", (0.68, 0.50)))
    from test_estados import manos_volante
    t1 = sim.t
    sim.durante(300, manos_volante(0))
    sim.durante(600, lambda f: manos_volante(20 * f))
    assert sim.nucleo.maquina.gesto == "orbita" and medio(sim, t1) == [True]
    sim.durante(300, manos_volante(20, postura="abierta"))
    soltar_al_final(sim)


def test_un_puno_apaga_el_giro_con_dos_punos():
    from test_estados import manos_volante
    sim = preparar()
    sim.durante(300, manos_volante(0))
    sim.durante(600, lambda f: manos_volante(20 * f))
    assert sim.nucleo.maquina.gesto != "orbita"
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    sim.durante(300, manos_volante(20, postura="abierta"))
    soltar_al_final(sim)


def test_los_dos_con_dos_punos_gana_el_de_dos_manos():
    from test_estados import manos_volante
    sim = preparar(cfg={"orbita": {"girar": "ambos"}})
    t0 = sim.t
    sim.durante(300, manos_volante(0))
    sim.durante(800, lambda f: manos_volante(25 * f, centro=(0.5 + 0.06 * f, 0.52)))
    assert sim.nucleo.maquina.gesto == "orbita"
    assert medio(sim, t0) == [True]
    sim.durante(300, manos_volante(25, centro=(0.56, 0.52), postura="abierta"))
    # con la otra mano abierta, el puño solo gira
    t1 = sim.t
    sim.durante(400, [s.en("abierta", (0.30, 0.5), lado="Left"), s.en("abierta", C)])
    sim.durante(100, [s.en("abierta", (0.30, 0.5), lado="Left"), s.en("puno", C)])
    cuadros(sim, [[s.en("abierta", (0.30, 0.5), lado="Left"), m] for m in s.trayecto("puno", C, (0.68, 0.5), 12)])
    assert sim.nucleo.maquina.gesto == "orbita1" and medio(sim, t1) == [True]
    sim.durante(300, [s.en("abierta", (0.30, 0.5), lado="Left"), s.en("abierta", (0.68, 0.5))])
    soltar_al_final(sim)


# =============================================================== lanzar con inercia
INERCIA = {"orbita": {"inercia": True}}


def lanzar(sim, hasta=(0.75, 0.50), n=6):
    """Puño rápido (0,2 anchos en 6 cuadros = 1 imagen por segundo) y se abre la mano en el aire."""
    girar(sim, hasta=hasta, n=n)
    sim.cuadro(s.en("abierta", hasta))


def test_inercia_apagada_soltar_rapido_solo_suelta():
    sim = preparar()
    t0 = sim.t
    lanzar(sim)
    sim.durante(100, s.en("abierta", (0.75, 0.5)))
    assert medio(sim, t0) == [True, False]
    t1 = sim.t
    sim.durante(600, s.en("abierta", (0.75, 0.5)))
    assert sim.nucleo.maquina.gesto is None
    assert deltas(sim, t1)[2] == []
    soltar_al_final(sim)


def test_lanzar_sigue_girando_y_frena_solo():
    sim = preparar(cfg=INERCIA)
    t0 = sim.t
    lanzar(sim)
    m = sim.nucleo.maquina
    assert m.gesto == "inercia" and m.inercia_activa
    assert sim.estado == K.GIRANDO_3D
    assert any(isinstance(a, Aviso) and a.clave == "inercia" for a in sim.desde(t0))
    t1 = sim.t
    sim.durante(300, s.en("abierta", (0.75, 0.5)))
    assert medio(sim, t0) == [True]                     # el botón sigue abajo
    dx1 = deltas(sim, t1)[0]
    assert dx1 > 20, dx1
    sim.durante(4500, s.en("abierta", (0.75, 0.5)))
    assert m.gesto is None and not m.inercia_activa
    evs = medio(sim, t0)
    assert evs[0] is True and evs[-1] is False          # (en el borde puede reagarrar)
    # frena: lo que se mueve en el último tramo es menos que al principio
    d = [(t, a) for t, a in sim.acciones if t >= t1 and isinstance(a, MoverDelta)]
    assert d and d[-1][0] - t1 <= 4.0 + 1e-6
    primeros = sum(a.dx for t, a in d if t < t1 + 0.3)
    ultimos = sum(a.dx for t, a in d if t >= d[-1][0] - 0.3)
    assert primeros > ultimos
    soltar_al_final(sim)


def test_friccion_alta_frena_antes():
    tiempos, recorrido = [], []
    for fr in (6.0, 0.5):
        sim = preparar(cfg={"orbita": {"inercia": True, "friccion": fr}})
        lanzar(sim)
        t1 = sim.t
        while sim.nucleo.maquina.gesto == "inercia" and sim.t - t1 < 6:
            sim.cuadro(s.en("abierta", (0.75, 0.5)))
        tiempos.append(sim.t - t1)
        recorrido.append(deltas(sim, t1)[0])
        soltar_al_final(sim)
    assert tiempos[0] < tiempos[1] <= 4.0 + 0.1, tiempos
    assert recorrido[0] < recorrido[1], recorrido


def test_la_inercia_reagarra_en_el_borde_y_nunca_pasa_de_4_segundos():
    sim = preparar(cfg={"orbita": {"inercia": True, "friccion": 0.3}})
    t0 = sim.t
    lanzar(sim)
    t1 = sim.t
    while sim.nucleo.maquina.gesto == "inercia" and sim.t - t1 < 6:
        sim.cuadro(s.en("abierta", (0.75, 0.5)))
    assert sim.t - t1 <= 4.0 + 0.1
    evs = medio(sim, t0)
    assert evs[:3] == [True, False, True] and evs[-1] is False, evs
    bajadas = [t for t, ev in sim.salida.eventos if t >= t0 and ev == ("boton", "medio", True)]
    subidas = [t for t, ev in sim.salida.eventos if t >= t0 and ev == ("boton", "medio", False)]
    assert bajadas[1] - subidas[0] >= 0.6 - 1e-6        # sin doble clic del medio
    soltar_al_final(sim)


def test_soltar_despacio_con_inercia_prendida_solo_suelta():
    sim = preparar(cfg=INERCIA)
    t0 = sim.t
    girar(sim, hasta=(0.66, 0.5), n=12)
    sim.durante(300, s.en("puno", (0.66, 0.5)))        # se frena antes de abrir
    sim.cuadro(s.en("abierta", (0.66, 0.5)))
    assert sim.nucleo.maquina.gesto == "orbita1"
    sim.durante(300, s.en("abierta", (0.66, 0.5)))
    assert sim.nucleo.maquina.gesto is None
    assert medio(sim, t0) == [True, False]
    soltar_al_final(sim)


def test_atrapar_con_el_puno_sin_soltar_el_boton():
    sim = preparar(cfg=INERCIA)
    t0 = sim.t
    lanzar(sim)
    sim.durante(150, s.en("abierta", (0.75, 0.5)))
    assert sim.nucleo.maquina.gesto == "inercia"
    sim.durante(100, s.en("puno", (0.75, 0.5)))
    m = sim.nucleo.maquina
    assert m.gesto == "orbita1" and not m.inercia_activa
    t1 = sim.t
    sim.durante(300, s.en("puno", (0.75, 0.5)))
    assert abs(deltas(sim, t1)[0]) < 15                 # atrapada: ya no sigue sola
    assert medio(sim, t0) == [True]                     # ni se soltó ni se volvió a bajar
    girar(sim, desde=(0.75, 0.5), hasta=(0.65, 0.5), espera_ms=40)
    sim.durante(300, s.en("abierta", (0.65, 0.5)))
    assert medio(sim, t0) == [True, False]
    soltar_al_final(sim)


@pytest.mark.parametrize("freno", ["mano_fuera", "tecla", "pausa", "bloqueo", "atajo_salir"])
def test_frenos_de_la_inercia(freno):
    sim = preparar(cfg=INERCIA)
    lanzar(sim)
    sim.durante(100, s.en("abierta", (0.75, 0.5)))
    assert sim.nucleo.maquina.gesto == "inercia"
    t1 = sim.t
    if freno == "mano_fuera":
        sim.durante(300, [])
    elif freno == "tecla":
        acc = sim.orden(sim.nucleo.frenar(sim.t))
        assert any(isinstance(a, Aviso) and a.clave == "frenado" for a in acc)
    elif freno == "pausa":
        sim.orden(sim.nucleo.pausar(sim.t))
    elif freno == "bloqueo":
        sim.orden(sim.nucleo.bloquear(sim.t, "admin"))
    else:
        sim.orden(sim.nucleo.alternar_pausa(sim.t))
    assert sim.nucleo.maquina.gesto is None and not sim.nucleo.maquina.inercia_activa
    assert sim.salida.todo_suelto()
    sim.durante(500, s.en("abierta", (0.75, 0.5)) if freno != "mano_fuera" else [])
    # (sin mano, la pista se retiene 150 ms como siempre: en ese rato puede seguir un poco)
    assert deltas(sim, t1 + (0.2 if freno == "mano_fuera" else 0.04))[2] == []
    if freno == "bloqueo":
        sim.orden(sim.nucleo.desbloquear(sim.t))
    soltar_al_final(sim)


def test_frenar_sin_inercia_no_hace_nada():
    sim = preparar(cfg=INERCIA)
    assert sim.nucleo.frenar(sim.t) == []
    girar(sim)
    assert sim.nucleo.frenar(sim.t) == []
    assert sim.nucleo.maquina.gesto == "orbita1"
    sim.durante(300, s.en("abierta", (0.68, 0.5)))
    soltar_al_final(sim)


def test_durante_la_inercia_las_otras_senas_no_hacen_nada():
    sim = preparar(cfg=INERCIA)
    lanzar(sim)
    t1 = sim.t
    for postura in ("pellizco", "pellizco_menique", "pellizco_anular", "apuntar"):
        sim.durante(100, s.en(postura, (0.75, 0.5)))
    assert [ev for t, ev in sim.salida.eventos if t >= t1 and ev[0] in ("boton", "pulsar", "rueda")] == []
    soltar_al_final(sim)


def test_la_velocidad_al_lanzar_tiene_tope():
    sim = preparar(cfg=INERCIA)
    lanzar(sim, hasta=(0.95, 0.5), n=2)                 # rapidísimo
    m = sim.nucleo.maquina
    if m.gesto == "inercia":
        assert math.hypot(*m.g["v"]) <= 8.0 * 1366 + 1e-6
    soltar_al_final(sim)


# =============================================================== golpe (despiezar / armar)
def abrir_golpe(sim, pos=C, puno_ms=150, cuadros_abrir=2, hacia="abierta", sostener_ms=400):
    sim.durante(puno_ms, s.en("puno", pos))
    cuadros(sim, s.abrir_de_golpe(pos, cuadros_abrir, hacia))
    sim.durante(sostener_ms, s.en(hacia, pos))


def cerrar_golpe(sim, pos=C, palma_ms=400, cuadros_cerrar=2, puno_ms=500):
    sim.durante(palma_ms, s.en("abierta", pos))
    cuadros(sim, s.cerrar_de_golpe(pos, cuadros_cerrar))
    sim.durante(puno_ms, s.en("puno", pos))


def test_sin_atajo_el_golpe_no_se_detecta():
    sim = preparar()                                     # edwin3d no trae atajo de fábrica
    t0 = sim.t
    abrir_golpe(sim)
    cerrar_golpe(sim)
    assert pulsados(sim, t0) == []
    assert P.gesto_de(P.PERFILES["edwin3d"], "abrir_golpe", FABRICA) is None
    sim.durante(300, s.en("abierta", C))
    soltar_al_final(sim)


@pytest.mark.parametrize("modo,perfil", [("3D", "edwin3d"), ("3D", "sketchup"), ("2D", "generico")])
def test_abrir_de_golpe_manda_el_atajo_una_vez(modo, perfil):
    sim = preparar(modo=modo, perfil=perfil, cfg=golpes(perfil))
    t0 = sim.t
    abrir_golpe(sim)
    assert pulsados(sim, t0) == [("ctrl", "alt", "u")]
    assert derecho(sim, t0) == [] and medio(sim, t0) == []
    avisos = [a for a in sim.desde(t0) if isinstance(a, Aviso) and a.clave == "golpe_abrir"]
    assert len(avisos) == 1 and avisos[0].texto == "Ctrl+Alt+U"
    assert sim.nucleo.maquina.palma_usada is True
    sim.durante(800, s.en("abierta", C))                 # sostener la palma no repite
    assert len(pulsados(sim, t0)) == 1
    soltar_al_final(sim)


def test_abrir_de_golpe_a_15_cuadros_por_segundo():
    sim = preparar(cfg=golpes(), fps=15.0)
    t0 = sim.t
    abrir_golpe(sim, puno_ms=140, cuadros_abrir=2)
    assert pulsados(sim, t0) == [("ctrl", "alt", "u")]
    soltar_al_final(sim)


def test_abrir_despacio_no_despieza():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    abrir_golpe(sim, cuadros_abrir=9)                    # 300 ms abriendo
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_abrir_rapido_sin_estirar_los_dedos_no_despieza():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    abrir_golpe(sim, hacia="relajada")
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_abrir_y_cerrar_enseguida_no_despieza():
    """La palma tiene que sostenerse 150 ms."""
    sim = preparar(cfg=golpes())
    t0 = sim.t
    abrir_golpe(sim, sostener_ms=60)
    sim.durante(400, s.en("puno", C))
    assert ("ctrl", "alt", "u") not in pulsados(sim, t0)
    sim.durante(300, s.en("apuntar", C))
    soltar_al_final(sim)


def test_abrir_despues_de_girar_no_despieza():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    girar(sim)
    cuadros(sim, s.abrir_de_golpe((0.68, 0.5), 2))       # aun abriendo de golpe
    sim.durante(500, s.en("abierta", (0.68, 0.5)))
    assert pulsados(sim, t0) == []
    assert medio(sim, t0) == [True, False]
    soltar_al_final(sim)


def test_puno_con_clic_derecho_y_abrir_de_golpe_no_despieza():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    abrir_golpe(sim, puno_ms=450)
    assert len(derecho(sim, t0)) == 1
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_abrir_de_golpe_moviendo_la_mano_no_despieza():
    sim = preparar(modo="2D", perfil="generico", cfg=golpes("generico"))
    t0 = sim.t
    sim.durante(150, s.en("puno", C))
    lejos = (C[0] + 0.12, C[1])
    cuadros(sim, [s.en(s.intermedia("puno", "abierta", 0.5), (C[0] + 0.06, C[1])), s.en("abierta", lejos)])
    sim.durante(400, s.en("abierta", lejos))
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_cerrar_de_golpe_arma_y_no_da_clic_derecho():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    cerrar_golpe(sim, puno_ms=600)
    assert pulsados(sim, t0) == [("ctrl", "alt", "j")]
    assert derecho(sim, t0) == []
    # el puño de «armar» no gira aunque se mueva, y al abrir de golpe no despieza
    cuadros(sim, s.trayecto("puno", C, (0.68, 0.5), 10))
    assert medio(sim, t0) == []
    cuadros(sim, s.abrir_de_golpe((0.68, 0.5), 2))
    sim.durante(400, s.en("abierta", (0.68, 0.5)))
    assert pulsados(sim, t0) == [("ctrl", "alt", "j")]
    soltar_al_final(sim)


def test_cerrar_de_golpe_moviendose_gira_y_no_arma():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    sim.durante(400, s.en("abierta", C))
    cuadros(sim, s.cerrar_de_golpe(C, 2))
    cuadros(sim, s.trayecto("puno", C, (0.70, 0.5), 3))  # se mueve antes de los 120 ms
    sim.durante(200, s.en("puno", (0.70, 0.5)))
    assert pulsados(sim, t0) == []
    assert medio(sim, t0) == [True]
    sim.durante(300, s.en("abierta", (0.70, 0.5)))
    soltar_al_final(sim)


def test_cerrar_desde_una_palma_breve_no_arma():
    """La palma estirada tiene que verse 200 ms antes de cerrar."""
    sim = preparar(cfg=golpes())
    t0 = sim.t
    sim.durante(500, s.en("apuntar", C))
    cerrar_golpe(sim, palma_ms=100)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_cerrar_despacio_no_arma_y_da_clic_derecho():
    sim = preparar(cfg=golpes())
    t0 = sim.t
    cerrar_golpe(sim, cuadros_cerrar=9)
    assert pulsados(sim, t0) == []
    assert len(derecho(sim, t0)) == 1
    soltar_al_final(sim)


def test_golpe_bloqueado_un_segundo():
    sim = preparar(modo="2D", perfil="generico", cfg=golpes("generico"))
    t0 = sim.t
    abrir_golpe(sim, sostener_ms=200)
    abrir_golpe(sim, puno_ms=120, sostener_ms=200)       # menos de 1 s después
    assert pulsados(sim, t0) == [("ctrl", "alt", "u")]
    sim.durante(800, s.en("abierta", C))
    abrir_golpe(sim, puno_ms=120)                         # ya pasó el segundo
    assert pulsados(sim, t0) == [("ctrl", "alt", "u")] * 2
    soltar_al_final(sim)


def test_golpe_apagado_no_hace_nada():
    sim = preparar(cfg=golpes(gestos={"golpe": False, "por_programa": {"edwin3d": dict(ATAJOS)}}))
    t0 = sim.t
    abrir_golpe(sim)
    cerrar_golpe(sim)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


@pytest.mark.parametrize("valor", ["Ctrl+Nada", "", "   ", 5, None])
def test_atajo_vacio_o_malo_no_detecta(valor):
    cfg = {"gestos": {"por_programa": {"generico": {"abrir_golpe": valor}}}}
    sim = preparar(modo="2D", perfil="generico", cfg=cfg)
    t0 = sim.t
    abrir_golpe(sim)
    assert pulsados(sim, t0) == []
    soltar_al_final(sim)


def test_golpe_con_boton_abajo_no_sale():
    sim = preparar(modo="2D", perfil="generico", cfg=golpes("generico"))
    t0 = sim.t
    sim.orden(sim.nucleo.tecla_clic(sim.t, True))         # la tecla sostiene el izquierdo
    abrir_golpe(sim)
    assert pulsados(sim, t0) == []
    sim.orden(sim.nucleo.tecla_clic(sim.t, False))
    soltar_al_final(sim)


@pytest.mark.parametrize("postura", ["pellizco", "pellizco_anular", "pellizco_menique", "juntos", "v", "apuntar"])
def test_las_senas_viejas_no_disparan_el_golpe(postura):
    """Pasar de una seña vieja a la palma abierta de golpe (o al revés) no despieza ni arma."""
    sim = preparar(modo="2D", perfil="generico", cfg=golpes("generico"))
    t0 = sim.t
    sim.durante(300, s.en(postura, C))
    cuadros(sim, s.transicion(postura, "abierta", 2, C))
    sim.durante(400, s.en("abierta", C))
    cuadros(sim, s.transicion("abierta", postura, 2, C))
    sim.durante(400, s.en(postura, C))
    assert pulsados(sim, t0) == []
    sim.durante(300, s.en("apuntar", C))
    soltar_al_final(sim)


def test_el_golpe_no_dispara_otras_senas():
    """Abrir y cerrar de golpe no da clic izquierdo, ni doble clic, ni activa o pausa."""
    sim = preparar(modo="2D", perfil="generico", cfg=golpes("generico"))
    t0 = sim.t
    abrir_golpe(sim)
    sim.durante(800, s.en("abierta", C))
    cerrar_golpe(sim)
    evs = [ev for t, ev in sim.salida.eventos if t >= t0 and ev[0] in ("boton", "clic")]
    assert evs == []
    assert sim.base == K.ACTIVO
    assert len(pulsados(sim, t0)) == 2
    soltar_al_final(sim)


def test_gesto_de_lee_la_config_y_el_perfil():
    import dataclasses
    p = dataclasses.replace(P.PERFILES["sketchup"], abrir_golpe="Ctrl+Shift+G", cerrar_golpe="Ctrl+G")
    assert P.gesto_de(p, "abrir_golpe", {}) == "Ctrl+Shift+G"
    cfg = {"gestos": {"por_programa": {"sketchup": {"abrir_golpe": ""}}}}
    assert P.gesto_de(p, "abrir_golpe", cfg) is None                  # vacío = nada
    assert P.gesto_de(p, "cerrar_golpe", cfg) == "Ctrl+G"             # ausente = lo del perfil
    cfg = {"gestos": {"por_programa": {"sketchup": {"abrir_golpe": "Alt+Izquierda"}}}}
    assert P.gesto_de(p, "abrir_golpe", cfg) == "Alt+Izquierda"
    for basura in ({"gestos": "x"}, {"gestos": {"por_programa": []}}, {"gestos": {"por_programa": {"sketchup": 3}}}):
        assert P.gesto_de(p, "abrir_golpe", basura) == "Ctrl+Shift+G"
    assert P.gesto_de(P.GENERICO, "abrir_golpe", None) is None


def test_perfil_personalizado_con_atajos_de_golpe():
    pers = {"mio": {"nombre": "Mi CAD", "exes": ["micad.exe"], "abrir_golpe": "Ctrl+E", "cerrar_golpe": 4}}
    p = P.cargar_personalizados(pers)["mio"]
    assert p.abrir_golpe == "Ctrl+E" and p.cerrar_golpe is None


# =============================================================== configuración
def test_config_de_la_101_carga_con_los_valores_de_fabrica_nuevos(tmp_path):
    viejo = copy.deepcopy(FABRICA)
    del viejo["gestos"]
    for k in ("girar", "k_un_puno", "inercia", "friccion"):
        del viejo["orbita"][k]
    del viejo["senas"]["tiempos_ms"]["puno_3d"]
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(viejo), encoding="utf-8")
    c = Configuracion(ruta)
    d = c.cargar()
    assert d["orbita"]["girar"] == "un_puno" and d["orbita"]["k_un_puno"] == 1.2
    assert d["orbita"]["inercia"] is False and d["orbita"]["friccion"] == 1.5
    assert d["senas"]["tiempos_ms"]["puno_3d"] == 300
    assert d["gestos"] == {"golpe": True, "por_programa": {}, "barrido": False}  # (barrido: apagado en la 1.0.3)
    assert c.aviso is None


@pytest.mark.parametrize("ruta,malo", [
    ("orbita.girar", "tres_punos"), ("orbita.girar", 2), ("orbita.k_un_puno", 9.0), ("orbita.k_un_puno", "x"),
    ("orbita.friccion", 0.0), ("orbita.friccion", float("nan")), ("orbita.inercia", "si"),
    ("senas.tiempos_ms.puno_3d", 50), ("senas.tiempos_ms.puno_3d", 5000), ("gestos.golpe", 1)])
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


def test_claves_nuevas_tienen_rango_u_opciones():
    assert RANGOS["senas.tiempos_ms.puno_3d"] == (150, 1000)
    assert RANGOS["orbita.k_un_puno"] == (0.1, 5.0) and RANGOS["orbita.friccion"] == (0.3, 6.0)
    assert OPCIONES["orbita.girar"] == ("un_puno", "dos_punos", "ambos")
    assert validar({"senas": {"tiempos_ms": {"puno_3d": 412.6}}})["senas"]["tiempos_ms"]["puno_3d"] == 413


def test_por_programa_con_basura_no_rompe():
    probl = []
    out = validar({"gestos": {"por_programa": "hola"}}, problemas=probl)
    assert out["gestos"]["por_programa"] == {} and probl
    sucio = {"edwin3d": {"abrir_golpe": "Ctrl+Alt+U", "cerrar_golpe": 7, "x": ["a"]}, "malo": 3,
             "sketchup": {"abrir_golpe": "no es un atajo"}, 5: {"abrir_golpe": "Enter"}}
    probl = []
    out = validar({"gestos": {"por_programa": sucio}}, problemas=probl)
    pp = out["gestos"]["por_programa"]
    assert pp["edwin3d"] == {"abrir_golpe": "Ctrl+Alt+U"}
    assert "malo" not in pp and pp["sketchup"] == {"abrir_golpe": "no es un atajo"}
    assert probl
    # la máquina no se rompe con eso: el atajo que no se entiende se ignora
    sim = preparar(perfil="sketchup", cfg={"gestos": {"por_programa": pp}})
    abrir_golpe(sim)
    assert pulsados(sim) == []
    soltar_al_final(sim)


def test_maquina_sin_validar_no_se_rompe_con_valores_raros():
    cfg = {"orbita": {"girar": "x", "k_un_puno": "rapido", "friccion": -1, "inercia": "si"},
           "gestos": {"golpe": None, "por_programa": 3}, "senas": {"tiempos_ms": {"puno_3d": "mucho"}}}
    sim = preparar(cfg=cfg)
    m = sim.nucleo.maquina
    assert m.girar == "un_puno" and m.k_un_puno == 1.2 and m.friccion == 1.5 and m.inercia_on is False
    assert m.s_puno_3d == 0.3
    girar(sim)
    abrir_golpe(sim)
    sim.durante(300, s.en("abierta", C))
    soltar_al_final(sim)


# =============================================================== secuencias sintéticas
def test_secuencias_sinteticas():
    tr = s.trayecto("puno", (0.5, 0.5), (0.6, 0.5), 4)
    assert len(tr) == 4
    centros = [m.img[[0, 5, 9, 13, 17], :2].mean(axis=0) for m in tr]
    assert centros[-1] == pytest.approx((0.6, 0.5), abs=1e-9)
    assert centros[0][0] == pytest.approx(0.525, abs=1e-9)
    ab = s.abrir_de_golpe((0.5, 0.5), 3)
    assert len(ab) == 3 and np.allclose(ab[-1].mundo, s.en("abierta", (0.5, 0.5)).mundo)
    ce = s.cerrar_de_golpe((0.5, 0.5), 2)
    assert np.allclose(ce[-1].mundo, s.en("puno", (0.5, 0.5)).mundo)


# =============================================================== motor y gancho
def test_motor_avisa_la_inercia_al_gancho_y_la_frena_con_una_tecla():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    from lycan_mouse_control.sistema import teclado as T
    sim = preparar(cfg=INERCIA)
    lanzar(sim)
    assert sim.nucleo.maquina.gesto == "inercia"
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.nucleo = sim.nucleo
    m.sincronizar_gancho()
    assert m.estado_gancho.inercia_activa is True
    # cualquier tecla (que no sea la de clic) pasa normal al programa y frena la pieza
    assert T.decidir(0x41, 0x1E, False, True, False, 0, m.estado_gancho) == (False, ("frenar",))
    m.ordenes.put(("frenar",))
    m._atender_ordenes()
    m.sincronizar_gancho()
    assert sim.nucleo.maquina.gesto is None and m.estado_gancho.inercia_activa is False


@pytest.mark.parametrize("semilla", range(8))
def test_punos_y_palmas_al_azar_nada_queda_presionado(semilla):
    """Puños que se mueven, se abren de golpe o despacio, lanzan, se atrapan y se pierden, con
    teclas que frenan y pausas: nunca queda un botón abajo ni sale una tecla con botones abajo."""
    rng = np.random.default_rng(100 + semilla)
    girar_con = ("un_puno", "ambos", "dos_punos")[semilla % 3]
    cfg = golpes("edwin3d", orbita={"inercia": True, "girar": girar_con, "friccion": float(rng.uniform(0.3, 6))})
    sim = preparar(cfg=cfg, fps=float(rng.choice([15, 24, 30])))
    pos = np.array(C)
    postura = "puno"
    for _ in range(int(8 * 30)):
        r = rng.random()
        if r < 0.10:
            postura = str(rng.choice(["puno", "abierta", "relajada", "apuntar", "pellizco"]))
        pos = np.clip(pos + rng.normal(0, 0.02 if postura == "puno" else 0.008, 2), 0.1, 0.9)
        if rng.random() < 0.03:
            sim.cuadro([])
        elif rng.random() < 0.05:
            P_ = s.intermedia("puno", "abierta", float(rng.random()))
            sim.cuadro(s.en(P_, tuple(pos)))
        else:
            sim.cuadro(s.en(postura, tuple(pos)))
        q = rng.random()
        if q < 0.01:
            sim.orden(sim.nucleo.frenar(sim.t))
        elif q < 0.013:
            sim.orden(sim.nucleo.alternar_pausa(sim.t))
        sim.invariantes(final=False)
    sim.durante(300, [])
    soltar_al_final(sim)
    assert not sim.nucleo.errores, sim.nucleo.ultimo_error
