"""Motor con cámara y detector falsos (sin cámara real ni ratón real), E35 y arranque del programa."""
import queue
import threading
import time

import numpy as np
import pytest

from conftest import M
from lycan_mouse_control import constantes as K
from lycan_mouse_control.captura import Cuadro
from lycan_mouse_control.config import por_defecto
from lycan_mouse_control.motor import Motor, Vista
from lycan_mouse_control.salida.simulada import SalidaSimulada
from lycan_mouse_control.sintetico import mano


class CamaraFalsa:
    """Entrega cuadros negros a ~30 por segundo con su tiempo real."""

    def __init__(self, fps=30):
        self.n = 0
        self.dt = 1.0 / fps
        self.estado = "FUNCIONANDO"
        self._vivo = False
        self.t_ult = time.perf_counter()

    def is_alive(self):
        return self._vivo

    def start(self):
        self._vivo = True

    def ultimo(self, despues_de=0, espera=0.1):
        falta = self.dt - (time.perf_counter() - self.t_ult)
        if falta > 0:
            time.sleep(falta)
        self.t_ult = time.perf_counter()
        self.n += 1
        return Cuadro(np.zeros((480, 640, 3), np.uint8), self.t_ult, self.n)

    def detener(self):
        self._vivo = False


class DetectorFalso:
    """Devuelve las manos que diga el guion según el tiempo transcurrido."""

    def __init__(self, guion):
        self.guion = guion
        self.t0 = None
        self.ms_ultimo = 1.0
        self.fallar = False

    def procesar(self, img):
        if self.fallar:
            raise RuntimeError("MediaPipe falló (prueba)")
        if self.t0 is None:
            self.t0 = time.perf_counter()
        return self.guion(time.perf_counter() - self.t0)


def esperar(cond, segundos=5.0):
    fin = time.perf_counter() + segundos
    while time.perf_counter() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return False


def armar(guion, salida=None):
    cfg = por_defecto()
    salida = salida or SalidaSimulada()
    m = Motor(cfg, salida, camara=CamaraFalsa(), detector=DetectorFalso(guion), sistema=False)
    m.start()
    assert m.listo.wait(5)
    return m, salida


def guion_activar_y_clic(t):
    if t < 0.5:
        return [M("juntos")]
    if t < 1.5:
        return [M("apuntar")]
    if t < 1.8:
        return [M("pellizco")]
    return [M("apuntar")]


def test_motor_corre_y_publica_vistas():
    m, s = armar(guion_activar_y_clic)
    try:
        assert esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        assert esperar(lambda: ("izq", False) in s.botones(), 6)
        v = m.vistas.get(timeout=2)
        assert isinstance(v, Vista)
        assert v.imagen is not None and v.imagen.shape == (240, 320, 3)
        assert v.fps > 10
        assert v.punta is not None
    finally:
        m.detener()
        m.join(3)
    assert s.todo_suelto()


def test_motor_atajo_pausar_y_cambiar_modo():
    m, s = armar(lambda t: [M("apuntar")])
    try:
        m.ordenes.put(("pausar",))
        assert esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        m.ordenes.put(("modo",))
        assert esperar(lambda: m.nucleo.modo == "3D")
        assert m.nucleo.maquina.base == K.PAUSA
        m.ordenes.put(("dibujo_fino",))
        assert esperar(lambda: m.nucleo.maquina.puntero.dibujo_fino)
    finally:
        m.detener()
        m.join(3)
    assert s.todo_suelto()


def test_E35_sendinput_falla_pausa_avisa_y_sigue():
    m, s = armar(guion_activar_y_clic)
    try:
        assert esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        s.fallar = True
        assert esperar(lambda: m.nucleo.maquina.base == K.BLOQUEADO, 3)
        avisos = []
        while not m.avisos.empty():
            avisos.append(m.avisos.get())
        assert any(getattr(a, "clave", "") == "bloqueado_envio" for a in avisos)
        assert m.is_alive()
        # el motor sigue vivo; al volver Windows a aceptar eventos, se reintenta (aquí sin sistema: a mano)
        s.fallar = False
        m.ordenes.put(("pausar",))
    finally:
        m.detener()
        m.join(3)
    assert s.todo_suelto()


def test_error_de_mediapipe_no_mata_el_motor():
    det = DetectorFalso(lambda t: [M("apuntar")])
    cfg = por_defecto()
    s = SalidaSimulada()
    m = Motor(cfg, s, camara=CamaraFalsa(), detector=det, sistema=False)
    m.start()
    try:
        assert m.listo.wait(5)
        m.ordenes.put(("pausar",))
        assert esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        det.fallar = True
        assert esperar(lambda: m.nucleo.maquina.base == K.PAUSA, 3)
        det.fallar = False
        time.sleep(0.3)
        assert m.is_alive()
    finally:
        m.detener()
        m.join(3)


def test_camara_sin_cuadros_el_motor_sigue_vivo():
    class CamaraMuda(CamaraFalsa):
        def ultimo(self, despues_de=0, espera=0.1):
            time.sleep(espera)
            return None
    s = SalidaSimulada()
    m = Motor(por_defecto(), s, camara=CamaraMuda(), detector=DetectorFalso(lambda t: []), sistema=False)
    m.start()
    try:
        assert m.listo.wait(5)
        m.ordenes.put(("pausar",))
        assert esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        time.sleep(0.6)
        assert m.is_alive()
        assert m.nucleo.estado == K.SIN_MANO
        m.ordenes.put(("camara_perdida",))
        assert esperar(lambda: m.nucleo.maquina.base == K.PAUSA)
    finally:
        m.detener()
        m.join(3)


def test_modo_ensayo_cambia_a_salida_simulada_y_vuelve():
    real = SalidaSimulada()
    m, _ = armar(guion_activar_y_clic, salida=real)
    ensayo = SalidaSimulada()
    try:
        m.ordenes.put(("ensayo", True, ensayo))
        assert esperar(lambda: m.salida is ensayo)
        m.ordenes.put(("ensayo", False))
        assert esperar(lambda: m.salida is real)
    finally:
        m.detener()
        m.join(3)


def test_nueva_configuracion_rearma_el_nucleo():
    m, s = armar(lambda t: [M("apuntar")])
    try:
        cfg = por_defecto()
        cfg["modo"] = "3D"
        m.ordenes.put(("config", cfg))
        assert esperar(lambda: m.nucleo.modo == "3D")
    finally:
        m.detener()
        m.join(3)


# ---------------------------------------------------------------- programa
def test_argumentos():
    from lycan_mouse_control.app import argumentos
    a = argumentos(["--simular", "--prueba-segundos", "3", "--modo", "3D"])
    assert a.simular and a.prueba_segundos == 3 and a.modo == "3D" and not a.check


def test_check_carga_mediapipe_sin_camara():
    from lycan_mouse_control.app import check
    assert check() == 0


def test_asistente_cuenta_logros():
    from lycan_mouse_control.ui.asistente import contar_logros, pasos_para
    ev = [(0, ("mover", 10, 10)), (0, ("boton", "izq", True)), (0, ("boton", "izq", False)),
          (0, ("boton", "izq", True)), (0, ("mover", 200, 10)), (0, ("boton", "izq", False)),
          (0, ("boton", "izq", True)), (0, ("boton", "izq", False))]
    assert contar_logros("clic", ev) == 4          # 3 clics + 1 arrastre
    assert contar_logros("derecho", [(0, ("boton", "der", True))]) == 1
    assert contar_logros("zoom", [(0, ("rueda", 120))] * 3) == 3
    v = Vista(estado=K.ACTIVO)
    assert contar_logros("activar", [], v) == 1
    extra = {}
    contar_logros("pausar", [], v, extra)
    assert contar_logros("pausar", [], Vista(estado=K.PAUSA), extra) == 1
    giro = [(0, ("boton", "medio", True))] + [(0, ("mover", i, 0)) for i in range(12)]
    assert contar_logros("girar", giro) == 1
    assert contar_logros("soltar", [(0, ("boton", "medio", False))]) == 1
    assert len(pasos_para("2D")) == 13 and len(pasos_para("3D")) == 16
