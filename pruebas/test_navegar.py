"""1.0.3 «Señas para navegar»: clic empujando el dedo y scroll abanicando la mano.

Con manos sintéticas y con los videos reales del usuario (pruebas/datos_reales/abanico_*.npz,
puntos de la mano sacados de sus videos con herramientas/video_a_npz.py; no hay imágenes).
"""
import json
import os
import sys

import pytest

from conftest import M, Sim
from lycan_mouse_control import sintetico as s
from lycan_mouse_control.acciones import Bajar, Clic, Rueda
from lycan_mouse_control.config import FABRICA, Configuracion
from lycan_mouse_control.gestos_navegar import tamano_aparente

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "herramientas"))
from grabar import reproducir  # noqa: E402

DATOS = os.path.join(RAIZ, "pruebas", "datos_reales")
P = (0.55, 0.45)


def preparar(perfil="generico", cfg=None):
    sim = Sim(perfil=perfil, cfg=cfg)
    sim.activar(P)
    sim.durante(600, M("apuntar", P))
    return sim


def apuntar(sim, ms, dist=0.5, pos=P, **kw):
    sim.durante(ms, lambda f: s.mano("apuntar", posicion=pos, distancia_m=dist, **kw))


def empujar(sim, desde=0.5, hasta=0.40, ms=250, pos=P):
    """La mano apuntando se acerca a la cámara (la punta del índice queda en el mismo sitio)."""
    sim.durante(ms, lambda f: s.mano("apuntar", posicion=pos, distancia_m=desde + (hasta - desde) * f))


def clics(sim, desde=0.0):
    return [a for a in sim.desde(desde) if isinstance(a, Clic) and a.boton == "izq"]


def bajar_izq(sim, desde=0.0):
    return [a for a in sim.desde(desde) if isinstance(a, Bajar) and a.boton == "izq"]


def ruedas(sim, desde=0.0):
    return [a for a in sim.desde(desde) if isinstance(a, Rueda)]


# ------------------------------------------------------------------ medida del tamaño
def test_el_tamano_crece_al_acercar_y_casi_no_cambia_al_girar():
    lejos = s.mano("apuntar", distancia_m=0.5)
    cerca = s.mano("apuntar", distancia_m=0.42)
    girada = s.mano("apuntar", distancia_m=0.5, rot=(0.0, 35.0, 0.0))
    inclinada = s.mano("apuntar", distancia_m=0.5, rot=(30.0, 0.0, 0.0))
    a = tamano_aparente(lejos.img, lejos.mundo, 4 / 3)
    b = tamano_aparente(cerca.img, cerca.mundo, 4 / 3)
    assert b / a > 1.15
    for m in (girada, inclinada):
        c = tamano_aparente(m.img, m.mundo, 4 / 3)
        assert abs(c / a - 1.0) < 0.06, c / a


def test_tamano_sin_datos_no_revienta():
    assert tamano_aparente(None, None, 1.0) != tamano_aparente(None, None, 1.0)   # nan
    m = s.mano("apuntar")
    assert tamano_aparente(m.img, None, 4 / 3) != tamano_aparente(m.img, None, 4 / 3)


# ------------------------------------------------------------------ clic empujando
def test_empujar_hace_un_clic_izquierdo_donde_apuntaba():
    sim = preparar()
    apuntar(sim, 400)
    antes = sim.salida.cursor
    t0 = sim.t
    empujar(sim)
    assert len(clics(sim, t0)) == 1
    assert bajar_izq(sim, t0) == []
    dx = abs(sim.salida.cursor[0] - antes[0])
    dy = abs(sim.salida.cursor[1] - antes[1])
    assert dx <= 3 and dy <= 3, (antes, sim.salida.cursor)
    apuntar(sim, 400)                 # retirar la mano: el puntero se suelta, no hay otro clic
    assert len(clics(sim, t0)) == 1
    sim.invariantes()


def test_retirar_la_mano_suelta_el_puntero():
    sim = preparar()
    apuntar(sim, 400)
    empujar(sim)
    assert sim.nucleo.maquina.empujando()
    apuntar(sim, 300)                 # de vuelta a 0,5 m
    assert not sim.nucleo.maquina.empujando()
    t0 = sim.t
    sim.durante(400, lambda f: s.mano("apuntar", posicion=(P[0] + 0.15 * f, P[1])))
    assert sim.salida.cursor != None  # noqa: E711
    movs = [a for a in sim.desde(t0) if type(a).__name__ == "Mover"]
    assert movs, "el puntero vuelve a seguir al dedo"


def test_empujar_a_medias_y_volver_no_hace_clic():
    sim = preparar()
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim, 0.5, 0.47, 150)          # empieza a empujar (el puntero se queda quieto)...
    empujar(sim, 0.47, 0.5, 150)          # ... y se arrepiente
    apuntar(sim, 600)
    assert clics(sim, t0) == []
    assert not sim.nucleo.maquina.empujando()


def test_acercar_la_mano_muy_despacio_no_hace_clic():
    sim = preparar()
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim, 0.5, 0.40, 3000)         # 10 cm en 3 s: es acomodarse, no empujar
    assert clics(sim, t0) == []


def test_mover_el_puntero_rapido_no_cuenta_como_empujar():
    sim = preparar()
    apuntar(sim, 400, pos=(0.30, 0.45))
    t0 = sim.t
    sim.durante(250, lambda f: s.mano("apuntar", posicion=(0.30 + 0.4 * f, 0.45),
                                      distancia_m=0.5 - 0.1 * f))
    assert clics(sim, t0) == []


def test_girar_la_mano_apuntando_no_hace_clic():
    sim = preparar()
    apuntar(sim, 400)
    t0 = sim.t
    sim.durante(250, lambda f: s.mano("apuntar", posicion=P, rot=(0.0, 35.0 * f, 0.0)))
    sim.durante(250, lambda f: s.mano("apuntar", posicion=P, rot=(25.0 * f, 35.0, 0.0)))
    assert clics(sim, t0) == []


def test_dos_empujones_seguidos_caen_en_el_mismo_punto():
    sim = preparar()
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim)
    p1 = sim.salida.cursor
    empujar(sim, 0.40, 0.5, 130)          # retira rápido, un poco corrido
    sim.durante(120, lambda f: s.mano("apuntar", posicion=(P[0] + 0.01, P[1]), distancia_m=0.5))
    empujar(sim, 0.5, 0.40, 200, pos=(P[0] + 0.01, P[1]))
    assert len(clics(sim, t0)) == 2
    assert sim.salida.cursor == p1


def test_empujar_apagado_no_hace_clic():
    sim = preparar(cfg={"navegar": {"empujar": False}})
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim)
    assert clics(sim, t0) == []


def test_fuerza_del_empujon():
    sim = preparar(cfg={"navegar": {"empujar_fuerza": 0.40}})
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim)                          # 0,5 -> 0,4 m = crece ~25 %: no alcanza el 40 %
    assert clics(sim, t0) == []


def test_empujar_funciona_en_programas_de_diseno():
    sim = preparar(perfil="sketchup")
    apuntar(sim, 400)
    t0 = sim.t
    empujar(sim)
    assert len(clics(sim, t0)) == 1


def test_empujar_en_pausa_no_hace_nada():
    sim = preparar()
    sim.orden(sim.nucleo.pausar(sim.t))
    t0 = sim.t
    apuntar(sim, 400)
    empujar(sim)
    assert clics(sim, t0) == []


# ------------------------------------------------------------------ abanico (sintético)
def golpe(sim, desde, hasta, cuadros=6, vuelta="apuntar", vuelta_cuadros=12):
    """Golpe con la mano abierta y vuelta floja (como remar)."""
    for m in s.trayecto("abierta", desde, hasta, cuadros):
        sim.cuadro(m)
    sim.durante(100, s.en("abierta", hasta))
    for m in s.trayecto(vuelta, hasta, desde, vuelta_cuadros):
        sim.cuadro(m)
    sim.durante(200, s.en(vuelta, desde))


@pytest.mark.parametrize("hasta,horizontal,signo", [
    ((0.55, 0.25), False, +1),    # arriba = rueda hacia arriba
    ((0.55, 0.75), False, -1),    # abajo
    ((0.80, 0.50), True, +1),     # derecha = rueda de lado a la derecha
    ((0.30, 0.50), True, -1),     # izquierda
])
def test_abanico_mueve_la_pagina_para_ese_lado(hasta, horizontal, signo):
    sim = preparar()
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    t0 = sim.t
    golpe(sim, (0.55, 0.50), hasta)
    r = ruedas(sim, t0)
    assert r, "el golpe tiene que mover la página"
    assert all(a.horizontal is horizontal and (a.delta > 0) == (signo > 0) for a in r), r
    assert clics(sim, t0) == [] and bajar_izq(sim, t0) == []
    sim.invariantes()


def test_la_vuelta_floja_no_mueve_la_pagina_al_reves():
    sim = preparar()
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    t0 = sim.t
    for _ in range(3):
        golpe(sim, (0.55, 0.55), (0.55, 0.25))
    r = ruedas(sim, t0)
    assert len(r) >= 3 and all(a.delta > 0 for a in r)


def test_mover_la_mano_apuntando_rapido_no_mueve_la_pagina():
    sim = preparar()
    t0 = sim.t
    for m in s.trayecto("apuntar", (0.55, 0.50), (0.55, 0.20), 6):
        sim.cuadro(m)
    sim.durante(300, s.en("apuntar", (0.55, 0.20)))
    assert ruedas(sim, t0) == []


def test_abanico_lento_no_cuenta():
    sim = preparar()
    sim.durante(400, s.en("abierta", (0.55, 0.50)))
    t0 = sim.t
    for m in s.trayecto("abierta", (0.55, 0.50), (0.55, 0.30), 30):   # 1 s: mover la mano
        sim.cuadro(m)
    sim.durante(300, s.en("abierta", (0.55, 0.30)))
    assert ruedas(sim, t0) == []


def test_soltar_el_brazo_en_diagonal_no_cuenta():
    sim = preparar()
    sim.durante(400, s.en("abierta", (0.55, 0.40)))
    t0 = sim.t
    for m in s.trayecto("abierta", (0.55, 0.40), (0.85, 0.70), 6):
        sim.cuadro(m)
    sim.durante(300, s.en("abierta", (0.85, 0.70)))
    assert ruedas(sim, t0) == []


def test_mientras_abanica_el_puntero_se_queda_quieto():
    sim = preparar()
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    antes = sim.salida.cursor
    golpe(sim, (0.55, 0.55), (0.55, 0.25), vuelta_cuadros=8)
    for m in s.trayecto("abierta", (0.55, 0.55), (0.55, 0.25), 6):
        sim.cuadro(m)
    assert abs(sim.salida.cursor[0] - antes[0]) <= 3 and abs(sim.salida.cursor[1] - antes[1]) <= 3


def test_en_diseno_el_abanico_no_hace_nada():
    sim = preparar(perfil="sketchup")
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    t0 = sim.t
    golpe(sim, (0.55, 0.50), (0.55, 0.25))
    assert [r for r in ruedas(sim, t0) if r.horizontal or r.delta > 0] == []


def test_abanico_apagado():
    sim = preparar(cfg={"navegar": {"abanico": False}})
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    t0 = sim.t
    golpe(sim, (0.55, 0.50), (0.55, 0.25))
    assert ruedas(sim, t0) == []


def test_invertir_el_abanico():
    sim = preparar(cfg={"navegar": {"invertir": True}})
    sim.durante(400, s.en("apuntar", (0.55, 0.50)))
    t0 = sim.t
    golpe(sim, (0.55, 0.50), (0.55, 0.25))
    r = ruedas(sim, t0)
    assert r and all(a.delta < 0 for a in r)


# ------------------------------------------------------------------ videos reales del usuario
def correr_video(nombre, perfil="generico"):
    datos, _ = reproducir(os.path.join(DATOS, nombre + ".npz"))
    sim = Sim(perfil=perfil)
    sim.orden(sim.nucleo.maquina.activar(sim.t))
    t0 = sim.t
    for t, manos in datos:
        sim.t = t0 + t
        r = sim.nucleo.procesar(sim.t, manos)
        sim._aplicar(r.acciones)
    return sim


@pytest.mark.parametrize("video,horizontal,signo", [
    ("abanico_subir", False, +1),
    ("abanico_bajar", False, -1),
    ("abanico_derecha", True, +1),
    ("abanico_izquierda", True, -1),
])
def test_videos_reales_del_usuario(video, horizontal, signo):
    sim = correr_video(video)
    r = ruedas(sim)
    assert len(r) >= 2, f"{video}: se esperaban al menos 2 golpes, hubo {len(r)}"
    malos = [a for a in r if a.horizontal is not horizontal or (a.delta > 0) != (signo > 0)]
    assert malos == [], f"{video}: golpes para el lado equivocado: {malos}"
    assert clics(sim) == [] and bajar_izq(sim) == [], "abanicar no puede hacer clic"
    assert not [a for a in sim.acciones if isinstance(a[1], Clic)], "ni clic derecho"
    sim.invariantes()


@pytest.mark.parametrize("video", ["abanico_subir", "abanico_bajar", "abanico_derecha", "abanico_izquierda"])
def test_videos_reales_en_diseno_no_mueven_la_pagina(video):
    sim = correr_video(video, perfil="sketchup")
    assert clics(sim) == []


# ------------------------------------------------------------------ configuración
def test_valores_de_fabrica_de_la_103():
    assert FABRICA["navegar"] == {"abanico": True, "empujar": True, "abanico_paso": 3,
                                  "empujar_fuerza": 0.15, "invertir": False}
    assert FABRICA["scroll"]["palma"] is False
    assert FABRICA["gestos"]["barrido"] is False


def test_config_de_la_102_apaga_la_palma_y_el_barrido(tmp_path):
    ruta = tmp_path / "config.json"
    vieja = json.loads(json.dumps(FABRICA))
    del vieja["navegar"]
    vieja["scroll"]["palma"] = True
    vieja["gestos"]["barrido"] = True
    ruta.write_text(json.dumps(vieja), encoding="utf-8")
    d = Configuracion(ruta).cargar()
    assert d["scroll"]["palma"] is False and d["gestos"]["barrido"] is False
    assert d["navegar"]["abanico"] is True and d["navegar"]["empujar"] is True


def test_config_de_la_103_respeta_lo_que_el_usuario_prendio(tmp_path):
    ruta = tmp_path / "config.json"
    nueva = json.loads(json.dumps(FABRICA))
    nueva["scroll"]["palma"] = True
    nueva["navegar"]["empujar_fuerza"] = 0.25
    ruta.write_text(json.dumps(nueva), encoding="utf-8")
    d = Configuracion(ruta).cargar()
    assert d["scroll"]["palma"] is True and d["navegar"]["empujar_fuerza"] == 0.25


@pytest.mark.parametrize("valor", [0.0, 0.9, "mucho", None, -1])
def test_fuerza_fuera_de_rango_vuelve_a_fabrica(tmp_path, valor):
    ruta = tmp_path / "config.json"
    nueva = json.loads(json.dumps(FABRICA))
    nueva["navegar"]["empujar_fuerza"] = valor
    ruta.write_text(json.dumps(nueva), encoding="utf-8")
    d = Configuracion(ruta).cargar()
    assert d["navegar"]["empujar_fuerza"] == 0.15


# ------------------------------------------------------------------ pestaña «Navegar»
from test_ronda1_interfaz import AppModo, root  # noqa: E402,F401 - fixture


def test_pestana_navegar_cambia_la_config(root, tmp_path):  # noqa: F811
    from test_paquete_a_interfaz import _textos
    from test_paquete_c_interfaz import _abrir_pestana
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op, f, i, nombres = _abrir_pestana(root, app, "op_navegar")
    try:
        assert nombres.index(t("op_navegar")) == nombres.index(t("op_palma")) - 1
        textos = _textos(f)
        for clave in ("op_empujar", "op_empujar_fuerza", "op_abanico", "op_abanico_paso",
                      "op_abanico_invertir"):
            assert t(clave) in textos, clave
        op._set(["navegar", "abanico"], False)
        op._set(["navegar", "empujar_fuerza"], 0.25)
        assert op.cfg["navegar"]["abanico"] is False
        assert op.cfg["navegar"]["empujar_fuerza"] == 0.25
    finally:
        op.cancelar()


def test_textos_de_las_senas_nuevas():
    from lycan_mouse_control.ui.textos import PALABRAS_PROHIBIDAS, TXT
    for clave in ("sena_empujando", "sena_abanico_arriba", "sena_abanico_abajo", "sena_abanico_der",
                  "sena_abanico_izq", "op_navegar", "ay_empujar", "ay_abanico"):
        assert TXT.get(clave), clave
        assert not any(pal in TXT[clave].lower() for pal in PALABRAS_PROHIBIDAS)
