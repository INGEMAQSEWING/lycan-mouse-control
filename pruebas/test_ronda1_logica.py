"""Ronda 1 de arreglos: cada prueba cubre una falla encontrada por los probadores.

Lógica pura (señas, máquina de estados, puntero, perfiles), salida, configuración, cámara y
arranque del programa (sin ventanas).
"""
import json
import math
import signal
import sys
import threading
import time

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Bajar, Clic, Rueda
from lycan_mouse_control.mapeo import Mapeo, Monitor
from lycan_mouse_control.puntero import Puntero
from lycan_mouse_control.senas import Clasificador, Sena
from lycan_mouse_control.sintetico import intermedia, mano

P0 = (0.5, 0.48)


def H(postura, pos=P0, lado="Right", **kw):
    """Mano con el CENTRO de la palma fijo (así se cierra o se abre sin desplazarse)."""
    return mano(postura, posicion=pos, lado=lado, ancla="centro", **kw)


def bajadas(sim, t0, boton):
    return [t for t, ev in sim.salida.eventos if t >= t0 and ev == ("boton", boton, True)]


def soltar_al_final(sim):
    sim.durante(300, [])
    sim.orden(sim.nucleo.pausar(sim.t))
    sim.invariantes()


# ======================================================== 1. puño flojo = pellizco fantasma
@pytest.mark.parametrize("t", [0.3, 0.4, 0.5, 0.6, 0.7])
def test_puno_a_medio_cerrar_no_es_pellizco(t):
    c = Clasificador()
    s = None
    for _ in range(8):
        s = c.clasificar(intermedia("relajada", "puno", t))
    assert s != Sena.PELLIZCO


def test_pellizco_real_sigue_siendo_pellizco():
    for a in ("apuntar", "abierta"):
        c = Clasificador()
        for _ in range(8):
            s = c.clasificar(intermedia(a, "pellizco", 1.0))
        assert s == Sena.PELLIZCO


@pytest.mark.parametrize("modo", ["2D", "3D"])
@pytest.mark.parametrize("ms", [200, 400, 700, 1000])
def test_cerrar_la_mano_da_clic_derecho_y_no_izquierdo(modo, ms):
    sim = Sim(modo)
    sim.activar(P0)
    sim.durante(600, H("relajada"))
    t0 = sim.t
    sim.durante(ms, lambda f: H(intermedia("relajada", "puno", f)))
    sim.durante(600, H("puno"))
    assert not bajadas(sim, t0, "izq"), "clic izquierdo fantasma al cerrar la mano"
    assert any(isinstance(a, Clic) and a.boton == K.DER for t, a in sim.acciones if t >= t0)
    soltar_al_final(sim)


@pytest.mark.parametrize("modo", ["2D", "3D"])
@pytest.mark.parametrize("ms", [300, 400, 500, 700, 1000])
def test_abrir_el_puno_despacio_no_hace_clic_izquierdo(modo, ms):
    sim = Sim(modo)
    sim.activar(P0)
    sim.durante(400, H("relajada"))
    sim.durante(100, lambda f: H(intermedia("relajada", "puno", f)))     # puño rápido
    sim.durante(600, H("puno"))
    t0 = sim.t
    sim.durante(ms, lambda f: H(intermedia("puno", "relajada", f)))      # se abre con calma
    sim.durante(800, H("relajada"))
    assert not bajadas(sim, t0, "izq"), "clic izquierdo encima del menú contextual"
    soltar_al_final(sim)


# ======================================================== 2. volver la mano no presiona solo
@pytest.mark.parametrize("perdida", [200, 300, 1000])
def test_2d_arrastre_perdido_al_volver_pellizcando_no_vuelve_a_presionar(perdida):
    sim = Sim()
    sim.activar(P0)
    sim.durante(300, H("pellizco", (0.5, 0.5)))
    sim.durante(300, lambda f: H("pellizco", (0.5 + 0.1 * f, 0.5)))
    assert sim.salida.botones()[-1] == ("izq", True)
    sim.durante(perdida, [])
    assert sim.salida.botones()[-1] == ("izq", False)
    t0 = sim.t
    sim.durante(400, lambda f: H("pellizco", (0.7 + 0.05 * f, 0.55)))
    assert not bajadas(sim, t0, "izq")
    # después de abrir la mano el clic vuelve a funcionar
    sim.durante(300, H("apuntar", (0.75, 0.55)))
    t1 = sim.t
    sim.durante(250, H("pellizco", (0.75, 0.55)))
    assert bajadas(sim, t1, "izq")
    sim.durante(300, H("apuntar", (0.75, 0.55)))
    soltar_al_final(sim)


def _punos(izq=True, der=True, postura="puno"):
    out = []
    if izq:
        out.append(H(postura, (0.3, 0.5), "Left"))
    if der:
        out.append(H(postura, (0.7, 0.5), "Right"))
    return out


@pytest.mark.parametrize("perdida", [300, 1000])
@pytest.mark.parametrize("cual", ["una", "las_dos"])
def test_3d_giro_perdido_al_volver_en_puno_no_vuelve_a_agarrar(perdida, cual):
    sim = Sim("3D")
    sim.activar(P0)
    sim.durante(600, _punos())
    assert sim.salida.botones()[-1] == ("medio", True)
    sim.durante(perdida, _punos(izq=False) if cual == "una" else [])
    assert sim.salida.botones()[-1] == ("medio", False)
    t0 = sim.t
    sim.durante(600, _punos())
    assert not bajadas(sim, t0, "medio"), "el botón del medio se volvió a presionar solo"
    assert not any(isinstance(a, Clic) for t, a in sim.acciones if t >= t0)
    # se abren las manos y se vuelve a agarrar: ahora sí gira
    sim.durante(300, _punos(postura="abierta"))
    t1 = sim.t
    sim.durante(600, _punos())
    assert bajadas(sim, t1, "medio")
    sim.durante(300, _punos(postura="abierta"))
    soltar_al_final(sim)


# ======================================================== 3. cambio de mano principal
@pytest.mark.parametrize("modo", ["2D", "3D"])
@pytest.mark.parametrize("postura_izq", ["puno", "pellizco"])
def test_se_retira_la_derecha_y_la_izquierda_cerrada_no_hace_clic(modo, postura_izq):
    sim = Sim(modo)
    sim.activar((0.7, 0.5))
    sim.durante(800, [H(postura_izq, (0.3, 0.6), "Left"), H("apuntar", (0.7, 0.5), "Right")])
    t0 = sim.t
    sim.durante(1000, [H(postura_izq, (0.3, 0.6), "Left")])
    assert not [ev for t, ev in sim.salida.eventos if t >= t0 and ev[0] == "boton" and ev[2]]
    assert sim.estado == K.ACTIVO
    # con una seña neutra la izquierda ya puede hacer clic
    sim.durante(300, [H("apuntar", (0.3, 0.6), "Left")])
    t1 = sim.t
    sim.durante(250, [H("pellizco", (0.3, 0.6), "Left")])
    assert bajadas(sim, t1, "izq")
    sim.durante(300, [H("apuntar", (0.3, 0.6), "Left")])
    soltar_al_final(sim)


def test_cambio_de_mano_reinicia_el_filtro_del_puntero():
    sim = Sim()
    sim.activar((0.7, 0.5))
    sim.durante(800, [H("apuntar", (0.3, 0.6), "Left"), H("apuntar", (0.7, 0.5), "Right")])
    m = sim.nucleo.maquina
    sim.durante(400, [H("apuntar", (0.3, 0.6), "Left")])
    # tras el cambio el historial del puntero solo tiene cuadros de la mano nueva (sin arrastrar
    # el filtro desde la posición vieja de la derecha, x ~ 990)
    assert m.puntero.hist
    assert all(x < 700 for _, x, _ in m.puntero.hist)


# ======================================================== 4. latencia de la seña de activar
@pytest.mark.parametrize("d1,hueco,d2,esperado", [
    (150, 300, 300, K.PAUSA),        # una seña de 150 ms cuenta
    (300, 300, 150, K.PAUSA),        # una segunda de 150 ms cuenta
    (300, 650, 300, K.PAUSA),        # hueco menor que 700 ms
    (300, 100, 300, K.PAUSA),
    (300, 750, 300, K.ACTIVO),       # hueco mayor que 700 ms
    (100, 300, 300, K.ACTIVO),       # primera demasiado corta
    (300, 300, 100, K.ACTIVO),       # segunda demasiado corta
    (1600, 300, 300, K.ACTIVO),      # primera demasiado larga
])
def test_matriz_de_tiempos_de_la_doble_sena(d1, hueco, d2, esperado):
    sim = Sim()
    sim.activar(P0)
    sim.durante(300, H("apuntar"))
    sim.durante(d1, H("juntos"))
    sim.durante(hueco, H("apuntar"))
    sim.durante(d2, H("juntos"))
    sim.durante(900, H("apuntar"))
    assert sim.base == esperado


# ======================================================== 5. abrir el pellizco no arrastra
@pytest.mark.parametrize("n", [2, 3, 5, 8])
def test_abrir_el_pellizco_con_cuadros_intermedios_no_arrastra(n):
    s = Sim()
    pc = (0.5, 0.85)

    def W(p):
        return mano(p, posicion=pc, ancla=0)          # muñeca quieta
    s.durante(400, W("juntos"))
    s.durante(1200, W("apuntar"))
    for i in range(n + 1):
        s.cuadro(W(intermedia("apuntar", "pellizco", i / n)))
    s.durante(200, W("pellizco"))
    for i in range(n + 1):
        s.cuadro(W(intermedia("pellizco", "apuntar", i / n)))
    s.durante(400, W("apuntar"))
    ev = [e for _, e in s.salida.eventos]
    i_b = max(i for i, e in enumerate(ev) if e == ("boton", "izq", True))
    i_s = next(i for i, e in enumerate(ev) if i > i_b and e == ("boton", "izq", False))
    pos = None
    for e in ev[:i_b]:
        if e[0] == "mover":
            pos = (e[1], e[2])
    for e in ev[i_b:i_s]:
        if e[0] == "mover":
            assert math.hypot(e[1] - pos[0], e[2] - pos[1]) <= 4, f"arrastre de {e} desde {pos}"
    assert not s.nucleo.maquina.puntero.arrastrando
    s.invariantes(final=False)


def test_arrastre_de_verdad_sigue_funcionando_con_los_nudillos():
    sim = Sim()
    sim.activar(P0)
    sim.durante(400, H("apuntar"))
    sim.durante(200, H("pellizco"))
    x0 = sim.salida.cursor[0]
    sim.durante(500, lambda f: H("pellizco", (0.5 + 0.15 * f, 0.48)))
    assert sim.salida.cursor[0] - x0 > 200
    assert sim.nucleo.maquina.puntero.arrastrando
    sim.durante(300, H("apuntar", (0.65, 0.48)))
    soltar_al_final(sim)


# ======================================================== 6. modo relativo con la misma ganancia
def test_relativo_misma_distancia_mueve_lo_mismo_en_x_y_en_y():
    mapeo = Mapeo(monitor=Monitor(0, 0, 1366, 768))
    d_px_cam = 40.0                                     # misma distancia física en la imagen

    def recorrido(du, dv):
        p = Puntero(mapeo, {"modo": "relativo"})
        t = 0.0
        p.observar(t, 0.5, 0.5)
        x0, y0 = p._rel_pos
        for k in range(1, 11):
            t += 1 / 30
            p.observar(t, 0.5 + du * k / 10, 0.5 + dv * k / 10)
        return p._rel_pos[0] - x0, p._rel_pos[1] - y0
    dx, _ = recorrido(d_px_cam / 640, 0.0)
    _, dy = recorrido(0.0, d_px_cam / 480)
    assert dx > 10
    assert dy == pytest.approx(dx, rel=0.02)


# ======================================================== 7. agarrar fuera de la zona activa
def _volante(ang, c, r=0.10):
    a = math.radians(ang)
    dx, dy = r * math.cos(a), r * math.sin(a) * 4 / 3
    return [mano("puno", posicion=(c[0] - dx, c[1] - dy), ancla="centro", lado="Left"),
            mano("puno", posicion=(c[0] + dx, c[1] + dy), ancla="centro", lado="Right")]


@pytest.mark.parametrize("c", [(0.5, 0.78), (0.5, 0.9), (0.15, 0.52), (0.85, 0.52), (0.5, 0.16)])
def test_agarrar_fuera_de_la_zona_no_pega_el_cursor_al_borde(c):
    sim = Sim(modo="3D", perfil="sketchup")
    sim.activar(P0)
    t0 = sim.t
    sim.durante(2000, _volante(0, c))
    abajo = [(t, ev) for t, ev in sim.salida.eventos if t >= t0 and ev == ("boton", "medio", True)]
    assert len(abajo) == 1, "el botón del medio se presiona y suelta sin parar"
    x, y = sim.salida.cursor
    assert 5 <= x <= 1366 - 1 - 5
    assert 5 <= y <= 768 - 48 - 1, "el cursor quedó sobre la barra de tareas"
    antes = sim.salida.cursor
    n0 = len(sim.salida.eventos)
    sim.durante(500, lambda f: _volante(25 * f, c))
    movs = [(e[1], e[2]) for _, e in list(sim.salida.eventos)[n0:] if e[0] == "mover"]
    assert any(math.hypot(x - antes[0], y - antes[1]) > 20 for x, y in movs), "el giro no mueve el cursor"
    sim.durante(300, [mano("abierta", posicion=(c[0] - 0.1, c[1]), ancla="centro", lado="Left"),
                      mano("abierta", posicion=(c[0] + 0.1, c[1]), ancla="centro", lado="Right")])
    soltar_al_final(sim)


def test_zona_segura_usa_el_area_de_trabajo():
    m = Monitor(0, 0, 1366, 768, trabajo=(0, 0, 1366, 720))
    x0, y0, x1, y1 = m.zona_segura(60)
    assert (x0, y0) == (60, 60) and x1 == 1366 - 61 and y1 == 720 - 61
    m2 = Monitor(0, 0, 1366, 768)                      # sin dato: se supone barra de 48 px
    assert m2.zona_segura(60)[3] == 768 - 48 - 61


# ======================================================== 8. EDWIN 3D: alejar en muescas enteras
def _pinza(d, centro=(0.5, 0.5)):
    return [mano("pellizco", posicion=(centro[0] - d / 2, centro[1]), ancla="centro", lado="Left"),
            mano("pellizco", posicion=(centro[0] + d / 2, centro[1]), ancla="centro", lado="Right")]


@pytest.mark.parametrize("ms", [400, 900, 1500])
def test_edwin3d_separar_y_juntar_lo_mismo_vuelve_igual(ms):
    sim = Sim(modo="3D", perfil="edwin3d")
    sim.activar(P0)
    sim.durante(200, _pinza(0.20))
    sim.durante(ms, lambda f: _pinza(0.20 * (1 + 0.4 * f)))
    sim.durante(ms, lambda f: _pinza(0.20 * (1.4 - 0.4 * f)))
    deltas = [a.delta for a in sim.de_tipo(Rueda)]
    assert any(d > 0 for d in deltas) and any(d < 0 for d in deltas)
    assert abs(sum(deltas)) <= 120
    for d in deltas:
        if d < 0:
            assert d % 120 == 0, f"alejar fraccionario ({d}): EDWIN 3D lo amplifica"
    sim.durante(300, [])
    soltar_al_final(sim)


def test_perfil_personalizado_puede_pedir_alejar_entero():
    from lycan_mouse_control import perfiles as P
    pp = P.cargar_personalizados({"x": {"nombre": "X", "rueda_fraccion": True, "alejar_entero": True}})
    assert pp["x"].alejar_entero
    assert P.PERFILES["edwin3d"].alejar_entero
    assert not P.PERFILES["blender"].alejar_entero


# ======================================================== 12. orden al soltar todo
def test_soltar_todo_suelta_el_izquierdo_antes_que_el_medio():
    from lycan_mouse_control.acciones import Tecla
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    s = SalidaSimulada()
    s.aplicar([Tecla("shift", True), Bajar("medio"), Bajar("izq"), Bajar("der")])
    s.limpiar()
    s.soltar_todo("prueba")
    botones = [ev[1] for _, ev in s.eventos if ev[0] == "boton"]
    assert botones == ["izq", "der", "medio"]
    assert s.todo_suelto()


# ======================================================== 15. memoria de la salida simulada
def test_salida_de_simular_no_crece_sin_limite():
    from lycan_mouse_control.salida import crear
    from lycan_mouse_control.acciones import Mover
    s = crear(True)
    for k in range(5000):
        s.aplicar([Mover(k % 1000, k % 700)])
    assert len(s.eventos) <= 2000
    assert s.n_eventos == 5000
    s.soltar_todo("fin")
    assert s.todo_suelto()


def test_salida_simulada_de_pruebas_guarda_todo():
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    from lycan_mouse_control.acciones import Mover
    s = SalidaSimulada()
    for k in range(3000):
        s.aplicar([Mover(k % 1000, 5)])
    assert len(s.eventos) == s.n_eventos == 3000
    assert s.eventos[100:101]          # el asistente corta la lista con índices


# ======================================================== 9 y 13. configuración
def test_guardar_sin_permiso_termina_enseguida(tmp_path, monkeypatch):
    import builtins
    import tempfile
    from lycan_mouse_control import config as C
    cfg = C.Configuracion(tmp_path / "config.json")
    cfg.cargar()

    def prohibido(*a, **k):
        raise AssertionError("no se debe usar tempfile.mkstemp (en Windows reintenta sin fin)")
    monkeypatch.setattr(tempfile, "mkstemp", prohibido)
    abrir = builtins.open

    def open_denegado(ruta, modo="r", *a, **k):
        if "w" in modo and str(ruta).endswith(".tmp"):
            raise PermissionError(13, "Acceso denegado", str(ruta))
        return abrir(ruta, modo, *a, **k)
    monkeypatch.setattr(builtins, "open", open_denegado)
    t0 = time.perf_counter()
    with pytest.raises(OSError):
        cfg.guardar()
    assert cfg.guardar_seguro() is False
    assert time.perf_counter() - t0 < 1.0
    assert not (tmp_path / "config.json.tmp").exists()


def test_guardar_si_falla_el_reemplazo_no_deja_temporal(tmp_path, monkeypatch):
    import os
    from lycan_mouse_control import config as C
    cfg = C.Configuracion(tmp_path / "config.json")
    cfg.cargar()

    def reemplazo_denegado(a, b):
        raise PermissionError(13, "Acceso denegado")
    monkeypatch.setattr(os, "replace", reemplazo_denegado)
    t0 = time.perf_counter()
    assert cfg.guardar_seguro() is False
    assert time.perf_counter() - t0 < 1.0
    assert not (tmp_path / "config.json.tmp").exists()


def test_guardar_normal_sigue_funcionando(tmp_path):
    from lycan_mouse_control import config as C
    cfg = C.Configuracion(tmp_path / "config.json")
    cfg.cargar()
    cfg.datos["modo"] = "3D"
    assert cfg.guardar_seguro()
    assert json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))["modo"] == "3D"


def test_config_con_anidamiento_profundo_se_restablece(tmp_path):
    from lycan_mouse_control import config as C
    ruta = tmp_path / "config.json"
    ruta.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    cfg = C.Configuracion(ruta)
    datos = cfg.cargar()
    assert datos == C.por_defecto()
    assert cfg.aviso
    assert list(tmp_path.glob("config.dañado-*.json"))


def test_registro_que_no_se_puede_crear_queda_anotado(tmp_path, monkeypatch):
    from lycan_mouse_control import registro
    import logging.handlers

    def falla(*a, **k):
        raise PermissionError(13, "Acceso denegado")
    monkeypatch.setattr(logging.handlers, "RotatingFileHandler", falla)
    monkeypatch.setattr(registro, "RotatingFileHandler", falla, raising=False)
    registro.configurar(tmp_path / "reg")
    assert registro.ERROR
    monkeypatch.undo()
    registro.configurar(tmp_path / "reg2")
    assert registro.ERROR is None


# ======================================================== 10. cámara ocupada
class _CapLenta:
    """Imitación de cv2.VideoCapture que entrega a ``fps`` cuadros/s."""

    def __init__(self, fps):
        self.fps = fps
        self.liberada = False

    def isOpened(self):
        return True

    def set(self, *a):
        return True

    def get(self, *a):
        return 0.0

    def read(self):
        time.sleep(1.0 / self.fps)
        return True, np.zeros((48, 64, 3), np.uint8)

    def release(self):
        self.liberada = True


def _camara_rapida_de_medir():
    from lycan_mouse_control.captura import Camara
    c = Camara(0)
    c.MEDIR_S = 0.25
    return c


def test_camara_lenta_al_abrir_se_suelta_y_se_marca_ocupada(monkeypatch):
    import cv2
    from lycan_mouse_control import captura
    caps = []

    def fabrica(*a, **k):
        caps.append(_CapLenta(4))
        return caps[-1]
    monkeypatch.setattr(cv2, "VideoCapture", fabrica)
    c = _camara_rapida_de_medir()
    assert c._abrir() is False
    assert c.estado == captura.OCUPADA
    assert caps[0].liberada
    # tras varios intentos lentos se usa igual (puede ser poca luz)
    ok = False
    for _ in range(captura.Camara.INTENTOS_LENTA):
        ok = c._abrir()
        if ok:
            break
    assert ok and c.cap is not None


def test_camara_rapida_se_acepta_al_primer_intento(monkeypatch):
    import cv2
    monkeypatch.setattr(cv2, "VideoCapture", lambda *a, **k: _CapLenta(60))
    c = _camara_rapida_de_medir()
    assert c._abrir() is True
    assert c.fps_al_abrir > 20


def test_camara_lenta_mucho_rato_se_reabre_con_espera_creciente():
    c = _camara_rapida_de_medir()
    c.fps_reales = 1.0
    t = 1000.0
    assert not c._lenta_hay_que_reabrir(t, t - 2)            # todavía no pasan 5 s
    assert c._lenta_hay_que_reabrir(t, t - 6)                # primera reapertura
    assert not c._lenta_hay_que_reabrir(t + 10, t + 3)       # muy pronto para otra
    assert c._lenta_hay_que_reabrir(t + 30, t + 20)
    assert c._espera_reabrir > c.REABRIR_MIN_S
    c.fps_reales = 30.0
    assert not c._lenta_hay_que_reabrir(t + 1000, t + 900)


def test_motor_distingue_camara_lenta_de_equipo_lento():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.detector = type("D", (), {"ms_ultimo": 24.0})()
    assert m._causa_lentitud() == "camara_lenta"
    m.detector.ms_ultimo = 90.0
    assert m._causa_lentitud() == "lento"


def test_aviso_de_lentitud_no_espera_60_cuadros():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.nucleo = Nucleo(por_defecto())
    m.detector = type("D", (), {"ms_ultimo": 24.0})()
    res = m.nucleo.procesar(0.0, [])
    for k in range(15):                       # 1 cuadro por segundo durante 15 s
        m.stats.cuadro(float(k))
        m._comodidad(float(k), res)
    avisos = []
    while not m.avisos.empty():
        avisos.append(m.avisos.get().clave)
    assert "camara_lenta" in avisos


def test_no_avisa_lentitud_si_la_camara_ya_se_recupero():
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.nucleo = Nucleo(por_defecto())
    m.detector = type("D", (), {"ms_ultimo": 24.0})()
    res = m.nucleo.procesar(0.0, [])
    t = 0.0
    for k in range(8):                        # 8 s a 1 cuadro/s (cámara ocupada)...
        t = float(k)
        m.stats.cuadro(t)
        m._comodidad(t, res)
    for k in range(90):                       # ...y se recupera a 30 cuadros/s
        t += 1 / 30
        m.stats.cuadro(t)
        m._comodidad(t, res)
    avisos = []
    while not m.avisos.empty():
        avisos.append(m.avisos.get().clave)
    assert "camara_lenta" not in avisos and "lento" not in avisos


# ======================================================== 11 y 14. arranque del programa
@pytest.fixture
def ganchos_intactos():
    viejos = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGINT", "SIGTERM", "SIGBREAK")
              if hasattr(signal, n)}
    eh, teh = sys.excepthook, threading.excepthook
    yield
    for n, h in viejos.items():
        signal.signal(getattr(signal, n), h)
    sys.excepthook, threading.excepthook = eh, teh


def test_argumento_camara_no_queda_guardado(tmp_path, ganchos_intactos):
    from lycan_mouse_control import app as A
    from lycan_mouse_control.config import Configuracion
    a = A.App(A.argumentos(["--simular", "--camara", "5", "--modo", "3D"]))
    assert a.motor.cfg["camara"]["indice"] == 5
    assert a.motor.cfg["modo"] == "3D"
    assert a.cfg.datos["camara"]["indice"] == 0
    # una orden de configuración (Opciones) sigue usando la cámara de esta sesión
    cfg = json.loads(json.dumps(a.cfg.datos))
    a.orden("config", cfg)
    assert a.motor.ordenes.get_nowait()[1]["camara"]["indice"] == 5
    a._finalizar()
    guardado = Configuracion(a.cfg.ruta)
    guardado.cargar()
    assert guardado.datos["camara"]["indice"] == 0
    assert guardado.datos["modo"] == "2D"


def test_segunda_copia_en_prueba_no_muestra_cuadro_y_sale(tmp_path):
    from lycan_mouse_control import app as A
    informe = tmp_path / "informe.json"
    args = A.argumentos(["--simular", "--prueba-segundos", "5", "--informe", str(informe)])
    with pytest.raises(SystemExit) as e:
        A.ya_abierto_en_prueba(args)
    assert e.value.code == 2
    assert json.loads(informe.read_text(encoding="utf-8")) == {"error": "ya abierto"}


def test_error_al_crear_la_app_queda_en_el_registro(monkeypatch):
    from lycan_mouse_control import app as A
    from lycan_mouse_control.sistema import ventanas_win

    def revienta(args):
        raise RuntimeError("falla de prueba")
    monkeypatch.setattr(A, "App", revienta)
    monkeypatch.setattr(ventanas_win, "instancia_unica", lambda m: True)
    registros = []
    monkeypatch.setattr(A.log, "exception", lambda *a, **k: registros.append(a))
    with pytest.raises(SystemExit) as e:
        A.main(["--simular", "--prueba-segundos", "1"])
    assert e.value.code == 1
    assert registros


def test_error_de_arranque_se_muestra_sin_codigo():
    from lycan_mouse_control import app as A
    from lycan_mouse_control.ui.textos import t
    avisos = []
    falsa = type("F", (), {})()
    falsa.cerrando = False
    falsa.motor = type("Mo", (), {"error_inicio": "RuntimeError('cv2 roto')", "camara": None})()
    falsa.ventana = type("V", (), {"mostrar_aviso": lambda self, txt, s=5: avisos.append(txt)})()
    falsa.root = type("R", (), {"after": lambda self, ms, f: None})()
    falsa._revisar_camara = lambda: None
    A.App._revisar_camara(falsa)
    assert avisos == [t("aviso_no_arranca")]
    assert "RuntimeError" not in avisos[0] and "(" not in avisos[0].split(".")[0]
