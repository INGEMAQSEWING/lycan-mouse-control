"""11.4: secuencias de cuadros por núcleo + perfiles + salida simulada (E1-E36).

Al final de cada secuencia se revisan las invariantes: cada Bajar tiene su Subir, ninguna tecla
queda abajo, no hay Bajar repetido, Shift nunca sube antes que el medio y no hay rueda con Shift/Ctrl.
"""
import math

import numpy as np
import pytest

from conftest import M, Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles
from lycan_mouse_control.acciones import (Aviso, Bajar, Clic, Mover, MoverDelta, Rueda, SoltarTodo, Subir,
                                          Tecla)
from lycan_mouse_control.sintetico import intermedia, mano

P0 = (0.5, 0.48)
# 1.0.2: de fábrica se gira con UN puño; estas pruebas son del giro con dos puños (1.0.1)
DOS_PUNOS = {"orbita": {"girar": "dos_punos"}}


def entrada(acciones):
    return [a for a in acciones if isinstance(a, (Mover, MoverDelta, Bajar, Subir, Clic, Rueda, Tecla))]


def soltar_al_final(sim):
    """Sin manos 300 ms y pausa: todo debe quedar suelto."""
    sim.durante(300, [])
    sim.orden(sim.nucleo.pausar(sim.t))
    sim.invariantes()


def quieto(sim, postura="apuntar", ms=1500, pos=P0, lado="Right"):
    sim.durante(ms, M(postura, pos, lado))


def eventos_boton(sim, boton):
    return [(t, ev[2]) for t, ev in sim.salida.eventos if ev[0] == "boton" and ev[1] == boton]


# ---------------------------------------------------------------- activar / pausar
def test_E1_arranque_sin_senas_queda_en_pausa():
    sim = Sim()
    sim.durante(1000, M("apuntar"))
    sim.durante(1000, [])
    sim.durante(500, M("pellizco"))
    sim.durante(500, M("puno"))
    assert sim.base == K.PAUSA
    assert entrada(a for _, a in sim.acciones) == []
    assert sim.salida.botones() == []


def test_E2_en_pausa_juntos_activa_en_250ms():
    sim = Sim()
    t0 = sim.t
    sim.durante(400, M("juntos", P0))
    t_act = next(t for t, r in sim.resultados if r.base == K.ACTIVO)
    assert 0.25 - 1e-6 <= t_act - t0 <= 0.40
    assert sim.de_tipo(Bajar, Clic) == []
    assert any(getattr(a, "nombre", "") == "activar" for _, a in sim.acciones)
    soltar_al_final(sim)


def test_E2b_anillo_de_progreso_sube_mientras_se_sostiene():
    sim = Sim()
    sim.durante(200, M("juntos", P0))
    prog = [r.progreso for _, r in sim.resultados]
    assert prog[-1] > prog[2] > 0


def test_E3_en_pausa_doble_sena_por_costumbre_queda_activo():
    sim = Sim()
    sim.durante(400, M("juntos"))
    sim.durante(200, M("apuntar"))
    sim.durante(300, M("juntos"))
    sim.durante(1200, M("apuntar"))
    assert sim.base == K.ACTIVO
    soltar_al_final(sim)


def test_E4_activo_sena_completa_y_segunda_a_500ms_pausa():
    sim = Sim()
    sim.activar()
    t0 = sim.t
    sim.durante(300, M("juntos"))
    sim.durante(500, M("apuntar"))
    sim.durante(300, M("juntos"))
    assert sim.base == K.PAUSA
    assert any(isinstance(a, SoltarTodo) for a in sim.desde(t0))
    soltar_al_final(sim)


def test_E4b_pausa_sin_soltar_la_segunda():
    sim = Sim()
    sim.activar()
    sim.durante(300, M("juntos"))
    sim.durante(300, M("apuntar"))
    t0 = sim.t
    sim.durante(400, M("juntos"))     # no hace falta soltar la segunda
    t_p = next(t for t, r in sim.resultados if t >= t0 and r.base == K.PAUSA)
    assert t_p - t0 <= 0.25


def test_E5_dos_senas_separadas_1000ms_sigue_activo():
    sim = Sim()
    sim.activar()
    sim.durante(300, M("juntos"))
    sim.durante(1000, M("apuntar"))
    sim.durante(300, M("juntos"))
    sim.durante(300, M("apuntar"))
    assert sim.base == K.ACTIVO
    soltar_al_final(sim)


def test_E6_sena_sostenida_2s_no_cuenta_y_avisa():
    sim = Sim()
    sim.activar()
    t0 = sim.t
    sim.durante(2000, M("juntos"))
    sim.durante(400, M("apuntar"))
    sim.durante(300, M("juntos"))
    sim.durante(300, M("apuntar"))
    assert sim.base == K.ACTIVO
    assert any(isinstance(a, Aviso) and a.clave == "sena_larga" for a in sim.desde(t0))
    soltar_al_final(sim)


def test_E7_sena_muy_corta_no_cuenta():
    sim = Sim()
    sim.activar()
    sim.durante(66, M("juntos"))
    sim.durante(300, M("apuntar"))
    sim.durante(300, M("juntos"))
    sim.durante(400, M("apuntar"))
    assert sim.base == K.ACTIVO
    soltar_al_final(sim)


def test_E7b_sena_corta_en_pausa_no_activa():
    sim = Sim()
    sim.durante(150, M("juntos"))
    sim.durante(500, M("apuntar"))
    assert sim.base == K.PAUSA


def test_E8_mientras_juntos_esta_puesta_no_mueve_ni_hace_clic():
    sim = Sim()
    sim.activar()
    sim.durante(150, M("juntos", P0))
    t0 = sim.t
    sim.durante(600, lambda f: M("juntos", (0.4 + 0.2 * f, 0.5)))
    assert entrada(sim.desde(t0)) == []
    soltar_al_final(sim)


# ---------------------------------------------------------------- clic izquierdo
def test_E9_pellizco_quieto_clic_en_la_posicion_rebobinada():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    antes = sim.salida.cursor
    t0 = sim.t
    sim.durante(250, M("pellizco", P0))
    sim.durante(400, M("apuntar", P0))
    acc = entrada(sim.desde(t0))
    tipos = [type(a) for a in acc]
    assert Bajar in tipos and Subir in tipos
    i_b, i_s = tipos.index(Bajar), tipos.index(Subir)
    assert not any(isinstance(a, Mover) for a in acc[i_b:i_s])     # ningún Mover intermedio
    assert math.dist(sim.salida.cursor, antes) <= 2
    assert sim.salida.botones()[-2:] == [("izq", True), ("izq", False)]
    soltar_al_final(sim)


def test_E10_pellizco_con_corrimiento_cae_donde_estaba():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    antes = sim.salida.cursor
    # el índice se corre ~25 px de pantalla hacia el pulgar en los 100 ms previos al pellizco
    corr = 25 / sim.mapeo.px_por_unidad_x
    for k in range(3):
        sim.cuadro(M("apuntar", (P0[0] - corr * (k + 1) / 3, P0[1])))
    sim.durante(250, M("pellizco", (P0[0] - corr, P0[1])))
    cursor_al_bajar = None
    for t, ev in sim.salida.eventos:
        if ev[0] == "mover":
            ultimo = (ev[1], ev[2])
        if ev == ("boton", "izq", True):
            cursor_al_bajar = ultimo
            break
    assert cursor_al_bajar is not None
    assert math.dist(cursor_al_bajar, antes) <= 2.5, (cursor_al_bajar, antes)
    sim.durante(400, M("apuntar", P0))
    soltar_al_final(sim)


def test_E11_pellizco_y_mover_200px_es_arrastre():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    t0 = sim.t
    sim.durante(150, M("pellizco", P0))
    d = 200 / sim.mapeo.px_por_unidad_x
    sim.durante(600, lambda f: M("pellizco", (P0[0] + d * f, P0[1])))
    sim.durante(300, M("pellizco", (P0[0] + d, P0[1])))
    assert sim.estado == K.ARRASTRANDO
    sim.durante(300, M("apuntar", (P0[0] + d, P0[1])))
    acc = entrada(sim.desde(t0))
    tipos = [type(a) for a in acc]
    i_b, i_s = tipos.index(Bajar), tipos.index(Subir)
    movs = [a for a in acc[i_b:i_s] if isinstance(a, Mover)]
    assert len(movs) >= 5
    assert movs[-1].x - movs[0].x > 150
    soltar_al_final(sim)


def test_E11b_dos_pellizcos_rapidos_doble_clic_en_el_mismo_punto():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    for _ in range(2):
        sim.durante(130, M("pellizco", P0))
        sim.durante(130, M("apuntar", P0))
    bajadas = [ev for _, ev in sim.salida.eventos if ev == ("boton", "izq", True)]
    assert len(bajadas) == 2
    t_b = [t for t, ev in sim.salida.eventos if ev == ("boton", "izq", True)]
    assert t_b[1] - t_b[0] < 0.5
    soltar_al_final(sim)


def test_E12_mano_desaparece_a_mitad_de_arrastre():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    sim.durante(300, lambda f: M("pellizco", (P0[0] + 0.05 * f, P0[1])))
    assert sim.estado == K.ARRASTRANDO
    t_perdida = sim.t
    sim.durante(400, [])
    t_subir = [t for t, ev in sim.salida.eventos if ev == ("boton", "izq", False)]
    assert t_subir and t_subir[0] - t_perdida <= 0.150 + sim.dt + 1e-6
    assert sim.estado == K.SIN_MANO
    assert sim.salida.todo_suelto()
    soltar_al_final(sim)


def test_E12b_al_volver_la_mano_no_presiona_nada_solo():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    sim.durante(200, M("pellizco", P0))
    sim.durante(300, [])
    n = len(sim.salida.botones())
    assert n >= 2                             # se presionó y se soltó por la pérdida
    sim.durante(500, M("pellizco", P0))      # vuelve ya pellizcando
    # al volver no puede haber NINGÚN botón nuevo presionado (sección 4.3)
    assert not [b for b in sim.salida.botones()[n:] if b[1]]
    sim.durante(300, M("apuntar", P0))
    assert sim.estado == K.ACTIVO
    soltar_al_final(sim)


# ---------------------------------------------------------------- clic derecho
def test_E13_transicion_pellizco_a_puno_sin_clic_derecho():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    sim.durante(200, M("pellizco", P0))
    sim.durante(600, M("puno", P0))
    sim.durante(300, M("apuntar", P0))
    assert not any(ev[1] == "der" for _, ev in sim.salida.eventos if ev[0] == "boton")
    assert sim.salida.botones()[-1] == ("izq", False)
    soltar_al_final(sim)


def test_E14_abierta_a_puno_un_clic_derecho_sin_repetir():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, "abierta")
    t0 = sim.t
    sim.durante(250, M("puno", P0))
    assert len([a for a in sim.desde(t0) if isinstance(a, Clic) and a.boton == "der"]) == 1
    sim.durante(1500, M("puno", P0))           # sigue en puño: no repite
    assert len([a for a in sim.desde(t0) if isinstance(a, Clic) and a.boton == "der"]) == 1
    sim.durante(300, M("abierta", P0))
    sim.durante(300, M("puno", P0))            # abrir y volver: otro clic
    assert len([a for a in sim.desde(t0) if isinstance(a, Clic) and a.boton == "der"]) == 2
    soltar_al_final(sim)


def test_E15_puno_de_150ms_no_hace_nada():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, "abierta")
    sim.durante(150, M("puno", P0))
    sim.durante(500, M("abierta", P0))
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    soltar_al_final(sim)


def test_E15b_puno_con_boton_sostenido_no_hace_clic_derecho():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    sim.durante(300, M("pellizco", P0))
    sim.durante(100, M("puno", P0))
    sim.durante(500, M("puno", P0))
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    soltar_al_final(sim)


# ---------------------------------------------------------------- 3D
def manos_volante(angulo_grados=0.0, r=0.13, centro=(0.5, 0.52), postura="puno", aspecto=4 / 3):
    a = math.radians(angulo_grados)
    dx, dy = r * math.cos(a), r * math.sin(a) * aspecto
    return [mano(postura, posicion=(centro[0] - dx, centro[1] - dy), ancla="centro", lado="Left"),
            mano(postura, posicion=(centro[0] + dx, centro[1] + dy), ancla="centro", lado="Right")]


def test_E16_3d_puno_y_a_los_150ms_la_otra_mano_en_puno():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    quieto(sim, "abierta", 500, pos=(0.63, 0.52))
    sim.durante(150, [mano("puno", posicion=(0.63, 0.52), ancla="centro")])
    sim.durante(600, manos_volante(0))
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    assert sim.estado == K.GIRANDO_3D
    assert ("medio", True) in sim.salida.botones()
    sim.durante(300, manos_volante(0, postura="abierta"))
    soltar_al_final(sim)


def test_E17_3d_dos_punos_girando_30_grados():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    t0 = sim.t
    sim.durante(1000, lambda f: manos_volante(30 * f))
    sim.durante(500, manos_volante(30))
    deltas = [a for a in sim.desde(t0) if isinstance(a, MoverDelta)]
    dx = sum(a.dx for a in deltas)
    dy = sum(a.dy for a in deltas)
    H = 768
    assert ("medio", True) in sim.salida.botones()
    assert dx == pytest.approx(30 / 180 * H, rel=0.25), dx
    assert abs(dy) < 20
    t1 = sim.t
    sim.durante(300, manos_volante(30, postura="abierta"))
    assert sim.salida.botones()[-1] == ("medio", False)
    assert sim.estado == K.ACTIVO
    soltar_al_final(sim)


def test_E17b_3d_girar_al_reves_y_subir_bajar_manos():
    sim = Sim(modo="3D", perfil="edwin3d", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    t0 = sim.t
    sim.durante(800, lambda f: manos_volante(-20 * f))
    sim.durante(300, manos_volante(-20))
    assert sum(a.dx for a in sim.desde(t0) if isinstance(a, MoverDelta)) < -40
    t1 = sim.t
    sim.durante(800, lambda f: manos_volante(-20, centro=(0.5, 0.52 + 0.08 * f)))
    sim.durante(300, manos_volante(-20, centro=(0.5, 0.60)))
    assert sum(a.dy for a in sim.desde(t1) if isinstance(a, MoverDelta)) > 25
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E17c_max_60px_por_cuadro():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    t0 = sim.t
    sim.durante(300, lambda f: manos_volante(30 * f))      # giro rápido (pero sin salto imposible)
    for a in sim.desde(t0):
        if isinstance(a, MoverDelta):
            assert math.hypot(a.dx, a.dy) <= 61
    sim.durante(200, [])
    soltar_al_final(sim)


def test_E18_3d_perder_una_mano_en_pleno_giro():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    sim.durante(300, lambda f: manos_volante(10 * f))
    t_perdida = sim.t
    sim.durante(400, [manos_volante(10)[1]])
    t_subir = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", False)]
    assert t_subir and t_subir[0] - t_perdida <= 0.150 + sim.dt + 1e-6
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    soltar_al_final(sim)


def test_E19_3d_soltar_y_reagarrar_a_los_300ms_sin_doble_clic_del_medio():
    sim = Sim(modo="3D", perfil="edwin3d", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    sim.durante(200, manos_volante(0, postura="abierta"))
    sim.durante(100, [])
    sim.durante(900, manos_volante(0))
    bajadas = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", True)]
    subidas = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", False)]
    assert len(bajadas) == 2
    assert bajadas[1] - subidas[0] >= 0.6 - 1e-6
    sim.durante(300, [])
    soltar_al_final(sim)


def manos_pinza(sep=0.12, centro=(0.5, 0.5)):
    return [mano("pellizco", posicion=(centro[0] - sep, centro[1]), ancla=9, lado="Left"),
            mano("pellizco", posicion=(centro[0] + sep, centro[1]), ancla=9, lado="Right")]


def test_E20_3d_desplazar_en_sketchup_orden_exacto():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(200, manos_pinza())
    n0 = len(sim.salida.eventos)
    sim.durante(800, lambda f: manos_pinza(centro=(0.5 + 0.1 * f, 0.5)))
    sim.durante(200, manos_pinza(centro=(0.6, 0.5)))
    assert sim.estado == K.DESPLAZANDO
    sim.durante(300, [mano("abierta", posicion=(0.48, 0.5), ancla=9, lado="Left"),
                      mano("abierta", posicion=(0.72, 0.5), ancla=9)])
    evs = [ev for _, ev in sim.salida.eventos[n0:] if ev[0] in ("boton", "tecla", "mover", "esperar")]
    claves = [ev for ev in evs if ev[0] in ("boton", "tecla")]
    # solo lo presionado por el gesto (los "soltar" de seguridad vienen después)
    i_shift = claves.index(("tecla", "shift", True))
    assert claves[i_shift + 1] == ("boton", "medio", True)
    i_up = claves.index(("boton", "medio", False))
    assert claves[i_up + 1] == ("tecla", "shift", False)
    movs = [ev for ev in evs[evs.index(("boton", "medio", True)):evs.index(("boton", "medio", False))]
            if ev[0] == "mover"]
    assert len(movs) >= 5
    # la espera de 20 ms entre Shift y el medio
    i = evs.index(("tecla", "shift", True))
    assert evs[i + 1] == ("esperar", 20)
    soltar_al_final(sim)


def test_E20b_2d_desplazar_usa_el_boton_del_medio_sin_shift():
    sim = Sim(modo="2D", perfil="edwin2d")
    sim.activar(P0)
    sim.durante(200, manos_pinza())
    sim.durante(800, lambda f: manos_pinza(centro=(0.5, 0.5 + 0.08 * f)))
    assert sim.estado == K.DESPLAZANDO
    assert ("tecla", "shift", True) not in sim.eventos()
    assert ("boton", "medio", True) in sim.eventos()
    sim.durante(300, [])
    soltar_al_final(sim)


@pytest.mark.parametrize("gesto", ["orbita", "desplazar"])
def test_E21_salir_con_el_atajo_en_pleno_gesto_suelta_todo(gesto):
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    if gesto == "orbita":
        sim.durante(300, manos_volante(0))
        sim.durante(300, lambda f: manos_volante(10 * f))
        assert sim.estado == K.GIRANDO_3D
    else:
        sim.durante(200, manos_pinza())
        sim.durante(500, lambda f: manos_pinza(centro=(0.5 + 0.1 * f, 0.5)))
        assert sim.estado == K.DESPLAZANDO
    n0 = len(sim.salida.eventos)
    sim.salida.soltar_todo("atajo de salir")          # lo que hace el hilo de atajos (Ctrl+Alt+X)
    evs = [ev for _, ev in sim.salida.eventos[n0:]]
    assert ("boton", "medio", False) in evs
    assert evs.index(("boton", "medio", False)) < evs.index(("tecla", "shift", False))
    assert sim.salida.todo_suelto()
    sim.invariantes()


def test_E22_dos_manos_que_se_cruzan_sin_saltos_ni_clic_derecho():
    sim = Sim(modo="3D", perfil="sketchup")
    sim.activar(P0)
    sim.durante(300, manos_volante(0, r=0.14))
    t0 = sim.t
    # se cruzan: intercambian x y etiqueta de un cuadro a otro
    for k in range(10):
        izq, der = manos_volante(0, r=0.14 - 0.028 * k)
        sim.cuadro([izq, der])
    for k in range(10):
        a, b = manos_volante(0, r=0.02 + 0.012 * k)
        a.etiqueta, b.etiqueta = "Right", "Left"
        sim.cuadro([b, a])
    deltas = [a for a in sim.desde(t0) if isinstance(a, MoverDelta)]
    assert all(math.hypot(a.dx, a.dy) <= 61 for a in deltas)
    assert abs(sum(a.dx for a in deltas)) < 80
    assert not any(isinstance(a, Clic) for _, a in sim.acciones)
    sim.durante(300, [])
    soltar_al_final(sim)


# ---------------------------------------------------------------- acercar / alejar
def pinza_ref(sim, sep):
    return manos_pinza(sep=sep)


def test_E23_zoom_dos_manos_separar_30_por_ciento_tres_muescas():
    sim = Sim(modo="2D", perfil="generico")
    sim.activar(P0)
    quieto(sim, ms=500)
    sim.durante(200, manos_pinza(0.10))
    t0 = sim.t
    sim.durante(900, lambda f: manos_pinza(0.10 * (1 + 0.3 * f)))
    sim.durante(300, manos_pinza(0.13))
    ruedas = [a for a in sim.desde(t0) if isinstance(a, Rueda)]
    assert [r.delta for r in ruedas] == [120, 120, 120]
    assert not [a for a in sim.desde(t0) if isinstance(a, Mover)]     # el puntero no se mueve
    sim.durante(300, [mano("abierta", posicion=(0.37, 0.5), ancla=9, lado="Left"),
                      mano("abierta", posicion=(0.63, 0.5), ancla=9)])
    assert len([a for a in sim.desde(t0) if isinstance(a, Rueda)]) == 3   # soltar no agrega muescas
    soltar_al_final(sim)


def test_E23b_juntar_las_manos_aleja():
    sim = Sim()
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.15))
    t0 = sim.t
    sim.durante(900, lambda f: manos_pinza(0.15 * (1 - 0.25 * f)))
    ruedas = [a.delta for a in sim.desde(t0) if isinstance(a, Rueda)]
    assert ruedas and all(d == -120 for d in ruedas)
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E23c_invertir_acercar_alejar():
    sim = Sim(cfg={"zoom": {"invertir": True}})
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.10))
    sim.durante(900, lambda f: manos_pinza(0.10 * (1 + 0.3 * f)))
    assert {a.delta for a in sim.de_tipo(Rueda)} == {-120}
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E24_zoom_en_librecad_maximo_8_muescas_por_segundo():
    sim = Sim(perfil="edwin2d")
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.06))
    t0 = sim.t
    sim.durante(400, lambda f: manos_pinza(0.06 + 0.30 * f))     # separación muy rápida
    sim.durante(1200, manos_pinza(0.36))
    tiempos = [t for t, a in sim.acciones if t >= t0 and isinstance(a, Rueda)]
    assert all(abs(a.delta) == 120 for a in sim.de_tipo(Rueda))
    assert len(tiempos) >= 3
    for i in range(len(tiempos)):
        en_un_segundo = [x for x in tiempos if tiempos[i] <= x < tiempos[i] + 1.0]
        assert len(en_un_segundo) <= 8
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E25_zoom_en_edwin_3d_admite_fracciones():
    sim = Sim(modo="3D", perfil="edwin3d")
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.10))
    sim.durante(900, lambda f: manos_pinza(0.10 * (1 + 0.3 * f)))
    deltas = [a.delta for a in sim.de_tipo(Rueda)]
    assert deltas
    assert all(abs(d) >= 15 for d in deltas)
    assert any(d % 120 for d in deltas)            # hay deltas que no son múltiplos de 120
    assert sum(deltas) == pytest.approx(math.log(1.3) / 0.08 * 120, rel=0.3)
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E26_zoom_con_temblor_de_3_por_ciento_no_hace_nada():
    rng = np.random.default_rng(8)
    sim = Sim()
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.12))
    sim.durante(1500, lambda f: manos_pinza(0.12 * (1 + rng.uniform(-0.03, 0.03))))
    assert sim.de_tipo(Rueda) == []
    sim.durante(300, [])
    soltar_al_final(sim)


def test_E27_rueda_con_shift_abajo_primero_termina_el_desplazamiento():
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    s = SalidaSimulada()
    s.aplicar([Tecla("shift", True), Bajar("medio"), MoverDelta(5, 0)])
    s.aplicar([Rueda(120)])
    evs = [ev for _, ev in s.eventos]
    i_rueda = evs.index(("rueda", 120))
    assert ("boton", "medio", False) in evs[:i_rueda]
    assert ("tecla", "shift", False) in evs[:i_rueda]
    assert not s.violaciones
    assert s.todo_suelto()


def test_E27b_en_un_gesto_de_dos_manos_nunca_hay_rueda_con_shift():
    sim = Sim(modo="3D", perfil="sketchup")
    sim.activar(P0)
    sim.durante(200, manos_pinza(0.10))
    # primero se mueve (desplazar) y después cambia la distancia: queda bloqueado en desplazar
    sim.durante(500, lambda f: manos_pinza(0.10, centro=(0.5 + 0.08 * f, 0.5)))
    sim.durante(600, lambda f: manos_pinza(0.10 * (1 + 0.4 * f), centro=(0.58, 0.5)))
    assert sim.de_tipo(Rueda) == []
    sim.durante(300, [])
    soltar_al_final(sim)


# ---------------------------------------------------------------- seguridad varias
@pytest.mark.parametrize("activo", [False, True])
def test_E28_rascarse_la_cara_no_hace_clic(activo):
    sim = Sim()
    if activo:
        sim.activar(P0)
        sim.durante(800, [])
    n0 = len(sim.salida.eventos)
    # entra rápido desde el borde, puño parcial, sale
    for k in range(4):
        sim.cuadro(M("relajada", (0.95 - 0.1 * k, 0.2 + 0.05 * k)))
    for k in range(3):
        sim.cuadro(M(intermedia("relajada", "puno", 0.5), (0.6, 0.35)))
    for k in range(3):
        sim.cuadro(M("relajada", (0.7 + 0.1 * k, 0.3)))
    sim.durante(300, [])
    botones = [ev for _, ev in sim.salida.eventos[n0:] if ev[0] == "boton" and ev[2]]
    assert botones == []
    sim.invariantes()


def test_E29_diez_segundos_sin_manos_pausa_sola():
    sim = Sim()
    sim.activar(P0)
    sim.durante(9500, [])
    assert sim.base == K.ACTIVO and sim.estado == K.SIN_MANO
    sim.durante(800, [])
    assert sim.base == K.PAUSA
    sim.invariantes()


def test_E30_cambio_de_perfil_en_pleno_arrastre():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    sim.durante(300, M("pellizco", P0))
    assert sim.estado == K.ARRASTRANDO
    acc = sim.orden(sim.nucleo.cambiar_perfil(sim.t, perfiles.PERFILES["sketchup"]))
    assert any(isinstance(a, SoltarTodo) for a in acc)
    assert sim.salida.todo_suelto()
    sim.durante(300, M("pellizco", P0))       # sigue pellizcando: no vuelve a presionar solo
    assert sim.salida.todo_suelto()
    sim.durante(300, M("apuntar", P0))
    soltar_al_final(sim)


@pytest.mark.parametrize("de,a", [("2D", "3D"), ("3D", "2D")])
def test_E31_cambio_de_modo_suelta_y_pausa(de, a):
    sim = Sim(modo=de)
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(300, M("pellizco", P0))
    acc = sim.orden(sim.nucleo.cambiar_modo(sim.t, a))
    assert any(isinstance(x, SoltarTodo) for x in acc)
    assert sim.base == K.PAUSA and sim.nucleo.modo == a
    assert sim.salida.todo_suelto()
    soltar_al_final(sim)


def test_E32_bajan_los_cuadros_por_segundo_durante_el_pellizco():
    resultados = []
    for fps_pellizco in (30, 12):
        sim = Sim()
        sim.activar(P0)
        quieto(sim, ms=800)
        sim.poner_fps(fps_pellizco)
        t0 = sim.t
        sim.durante(300, M("pellizco", P0))
        sim.durante(300, M("apuntar", P0))
        sim.poner_fps(30)
        b = [(round(t - t0, 2), ev[2]) for t, ev in sim.salida.eventos if t >= t0 and ev[0] == "boton"]
        resultados.append([x[1] for x in b])
        t_bajar = b[0][0]
        assert t_bajar <= 0.066 + 2 / fps_pellizco + 1e-6
        soltar_al_final(sim)
    assert resultados[0] == resultados[1] == [True, False]


def test_E33_cursor_sobre_la_ventana_propia_no_hace_clic():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    x, y = sim.salida.cursor
    sim.salida.rect_propio = (x - 50, y - 50, x + 50, y + 50)
    avisos = []
    t0 = sim.t
    for _ in range(10):
        r = sim.nucleo.procesar(sim.t, [M("pellizco", P0)])
        avisos += sim.salida.aplicar(r.acciones)
        sim.t += sim.dt
    assert not any(ev[0] == "boton" for t, ev in sim.salida.eventos if t >= t0)
    assert any(a.clave == "sobre_ventana" for a in avisos)
    sim.salida.rect_propio = None
    soltar_al_final(sim)


def test_E33b_ventana_activa_propia_no_envia_botones():
    sim = Sim()
    sim.activar(P0)
    quieto(sim)
    sim.salida.foco_propio = True
    sim.durante(300, M("pellizco", P0))
    sim.durante(300, M("puno", P0))
    assert not any(ev[0] == "boton" and ev[2] for _, ev in sim.salida.eventos)
    sim.salida.foco_propio = False
    soltar_al_final(sim)


def test_E34_ventana_elevada_bloquea():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    sim.durante(200, M("pellizco", P0))
    acc = sim.orden(sim.nucleo.bloquear(sim.t, "admin"))
    assert any(isinstance(a, SoltarTodo) for a in acc)
    assert any(isinstance(a, Aviso) and a.clave == "bloqueado_admin" for a in acc)
    assert sim.estado == K.BLOQUEADO
    t0 = sim.t
    sim.durante(500, lambda f: M("pellizco", (0.4 + 0.2 * f, 0.5)))
    sim.durante(300, M("juntos"))
    assert entrada(sim.desde(t0)) == []
    sim.orden(sim.nucleo.desbloquear(sim.t))
    assert sim.base == K.PAUSA
    soltar_al_final(sim)


def test_E36_excepcion_en_el_clasificador_a_mitad_de_arrastre():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=500)
    sim.durante(300, M("pellizco", P0))
    assert not sim.salida.todo_suelto()
    seg = sim.nucleo.seguidor
    original = seg.actualizar

    def falla(*a, **k):
        raise ZeroDivisionError("falla de prueba")
    seg.actualizar = falla
    r = sim.cuadro([M("pellizco", P0)])
    assert isinstance(r.acciones[0], SoltarTodo)
    assert any(isinstance(a, Aviso) and a.clave == "error" for a in r.acciones)
    assert sim.salida.todo_suelto()
    assert sim.base == K.PAUSA
    seg.actualizar = original
    sim.durante(300, M("apuntar", P0))
    assert not sim.nucleo.fatal
    soltar_al_final(sim)


def test_E36b_tres_errores_en_un_minuto_es_fatal():
    sim = Sim()
    seg = sim.nucleo.seguidor

    def falla(*a, **k):
        raise RuntimeError("x")
    seg.actualizar = falla
    for _ in range(3):
        sim.cuadro([M("apuntar")])
    assert sim.nucleo.fatal


# ---------------------------------------------------------------- extras
def test_atajo_alterna_pausa_y_suelta_todo():
    sim = Sim()
    sim.orden(sim.nucleo.alternar_pausa(sim.t))
    assert sim.base == K.ACTIVO
    quieto(sim, ms=500)
    sim.durante(300, M("pellizco", P0))
    acc = sim.orden(sim.nucleo.alternar_pausa(sim.t))
    assert sim.base == K.PAUSA
    assert isinstance(acc[0], SoltarTodo)
    soltar_al_final(sim)


def test_mano_izquierda_principal_mueve_y_hace_clic():
    sim = Sim(cfg={"mano_principal": "izquierda"})
    sim.activar(P0, lado="Left")
    quieto(sim, lado="Left")
    sim.durante(250, M("pellizco", P0, "Left"))
    sim.durante(300, M("apuntar", P0, "Left"))
    assert sim.salida.botones()[-2:] == [("izq", True), ("izq", False)]
    soltar_al_final(sim)


def test_cambia_la_mano_principal_en_pleno_arrastre_suelta():
    sim = Sim()
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(300, M("pellizco", P0))
    sim.durante(400, [M("apuntar", (0.2, 0.5), "Left")])   # se va la derecha, queda otra mano
    assert sim.salida.todo_suelto()
    soltar_al_final(sim)


def test_zoom_una_mano_variante():
    sim = Sim(cfg={"zoom": {"una_mano": True}})
    sim.nucleo.actualizar_umbrales(sim.cfg["senas"], True)
    sim.activar(P0)
    quieto(sim, ms=400)
    sim.durante(200, mano("pellizco_corazon", posicion=(0.5, 0.6), ancla=12))
    t0 = sim.t
    sim.durante(1000, lambda f: mano("pellizco_corazon", posicion=(0.5, 0.6 - 0.2 * f), ancla=12))
    ruedas = [a.delta for a in sim.desde(t0) if isinstance(a, Rueda)]
    assert ruedas and all(d == 120 for d in ruedas) and len(ruedas) <= 8
    assert not [a for a in sim.desde(t0) if isinstance(a, Mover)]
    sim.durante(300, M("apuntar", P0))
    soltar_al_final(sim)


def test_reagarre_en_el_borde_de_la_pantalla():
    sim = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    sim.activar(P0)
    c = (0.74, 0.52)                      # agarra cerca del borde derecho
    sim.durante(300, manos_volante(0, r=0.1, centro=c))
    x_agarre = sim.salida.cursor[0]
    assert x_agarre > 1150
    # giro sostenido: el cursor llega al borde, suelta, vuelve al punto de agarre y vuelve a presionar
    for k in range(1, 31):
        sim.cuadro(manos_volante(2.0 * k, r=0.1, centro=c))
    sim.durante(1200, manos_volante(60, r=0.1, centro=c))
    subidas = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", False)]
    assert subidas
    bajadas = [t for t, ev in sim.salida.eventos if ev == ("boton", "medio", True)]
    assert len(bajadas) >= 2
    assert bajadas[1] - subidas[0] >= 0.6 - 1e-6          # espera 600 ms antes de volver a presionar
    sim.durante(300, [])
    soltar_al_final(sim)


def test_desplazar_apagado_solo_zoom():
    sim = Sim(cfg={"senas": {"desplazar_dos_manos": False}})
    sim.activar(P0)
    sim.durante(200, manos_pinza())
    sim.durante(800, lambda f: manos_pinza(centro=(0.5 + 0.1 * f, 0.5)))
    assert sim.estado != K.DESPLAZANDO
    assert ("boton", "medio", True) not in sim.eventos()
    sim.durante(300, [])
    soltar_al_final(sim)


def test_freecad_estilo_cad_orbita_con_medio_e_izquierdo():
    sim = Sim(modo="3D", perfil="freecad", cfg=DOS_PUNOS)
    sim.activar(P0)
    sim.durante(300, manos_volante(0))
    sim.durante(300, lambda f: manos_volante(10 * f))
    b = sim.salida.botones()
    assert b[:2] == [("medio", True), ("izq", True)]
    sim.durante(300, manos_volante(10, postura="abierta"))
    b = sim.salida.botones()
    assert b[-2:] == [("izq", False), ("medio", False)]
    soltar_al_final(sim)


def test_pellizco_con_otra_mano_a_la_vista_no_hace_clic_al_empezar_zoom():
    sim = Sim()
    sim.activar(P0)
    sim.durante(400, [mano("abierta", posicion=(0.38, 0.5), ancla=9, lado="Left"),
                      mano("apuntar", posicion=(0.62, 0.5), ancla=9)])
    # la principal pellizca un poco antes que la otra
    sim.durante(100, [mano("abierta", posicion=(0.38, 0.5), ancla=9, lado="Left"),
                      mano("pellizco", posicion=(0.62, 0.5), ancla=9)])
    sim.durante(600, manos_pinza(0.12))
    assert not any(ev[0] == "boton" and ev[1] == "izq" for _, ev in sim.salida.eventos)
    sim.durante(300, [])
    soltar_al_final(sim)
