"""Prueba de humo de la interfaz: se crean y se cierran las ventanas sin errores (sin cámara real)."""
import queue
import tkinter as tk

import numpy as np
import pytest

from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Aviso, Sonido
from lycan_mouse_control.config import Configuracion
from lycan_mouse_control.motor import Vista
from lycan_mouse_control.salida.simulada import SalidaSimulada


class MotorFalso:
    def __init__(self):
        self.vistas = queue.Queue(maxsize=1)
        self.avisos = queue.Queue()
        self.ordenes = queue.Queue()
        self.salida = SalidaSimulada()


class AppFalsa:
    def __init__(self, tmp_path):
        self.cfg = Configuracion(tmp_path / "config.json")
        self.cfg.cargar()
        self.motor = MotorFalso()
        self.cola_atajos = queue.Queue()
        self.cerrando = False
        self.ultima_vista = None
        self.sonidos = type("S", (), {"tocar": lambda self, n: None, "activos": True})()
        self.ordenes = []
        self.pintadas = 0

    def orden(self, *a):
        self.ordenes.append(a)

    def salida_actual(self):
        return self.motor.salida

    def al_pintar(self, v):
        self.pintadas += 1

    def indicador_aviso(self, a):
        pass

    def aplicar_comodidad(self):
        pass

    def mostrar_aviso(self, t):
        pass

    def salir_seguro(self):
        self.cerrando = True

    abrir_opciones = abrir_asistente = abrir_ayuda = abrir_registros = reiniciar_admin = alternar_ventana = \
        lambda self: None


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass


def bombear(root, ms=300):
    import time
    fin = time.monotonic() + ms / 1000
    while time.monotonic() < fin:
        root.update()
        time.sleep(0.01)


def test_ventana_principal_pinta_vistas_y_avisos(root, tmp_path):
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    app = AppFalsa(tmp_path)
    v = VentanaPrincipal(root, app)
    root.deiconify()
    for estado in (K.PAUSA, K.ACTIVO, K.ARRASTRANDO, K.GIRANDO_3D, K.SIN_MANO, K.BLOQUEADO):
        app.motor.vistas.put(Vista(estado=estado, imagen=np.zeros((240, 320, 3), np.uint8), etiqueta="clic_izquierdo",
                                   fps=29.5, sena="PELLIZCO", medidas={"p": 0.1, "doblez": {}}))
        bombear(root, 120)
    app.motor.avisos.put(Aviso("sena_larga"))
    app.motor.avisos.put(Sonido("clic"))
    bombear(root, 200)
    assert "Seña muy larga" in v.lbl_aviso.cget("text")
    assert app.pintadas >= 5
    v._alternar_diag()
    v.alternar_mini()
    app.motor.vistas.put(Vista(estado=K.ACTIVO, imagen=np.zeros((240, 320, 3), np.uint8)))
    bombear(root, 150)
    v.alternar_mini()
    app.cola_atajos.put("pausar")
    bombear(root, 150)
    assert ("pausar",) in app.ordenes
    assert app.motor.salida.rect_propio is not None
    app.cerrando = True


def test_opciones_ayuda_asistente_se_abren(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.ayuda import VentanaAyuda
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppFalsa(tmp_path)
    app.root = root
    app.ultima_vista = Vista(estado=K.PAUSA, imagen=np.zeros((240, 320, 3), np.uint8), medidas={"p": 0.3, "s": 1.0})
    op = VentanaOpciones(root, app)
    bombear(root, 200)
    op.cancelar()
    assert ("config",) == app.ordenes[-1][:1]
    VentanaAyuda(root, "3D", True).win.destroy()
    a = Asistente(root, app)
    assert app.ordenes[-1][:2] == ("ensayo", True)
    for _ in range(len(a.pasos) - 1):
        a.siguiente()
        bombear(root, 40)
    a.terminar()
    assert app.ordenes[-1][:2] == ("ensayo", False)
    assert app.cfg.datos["primera_vez"] is False


def test_indicador_junto_al_cursor(root):
    from lycan_mouse_control.ui.indicador_cursor import Indicador
    ind = Indicador(root, lambda: (200, 200), simulado=True)
    ind.actualizar(Vista(estado=K.ACTIVO, etiqueta="clic_izquierdo", cursor=(300, 300)))
    bombear(root, 50)
    ind.actualizar(Vista(estado=K.PAUSA))
    ind.destruir()


def test_calibracion_pantalla_corre(root, tmp_path):
    from lycan_mouse_control.ui import calibracion as UC
    app = AppFalsa(tmp_path)
    app.ultima_vista = Vista(estado=K.PAUSA, brillo=120.0, ancho_mano=0.15, punta=(0.5, 0.5),
                             medidas={"p": 0.3, "s": 1.0, "a": 5.0})
    fin = []
    c = UC.Calibracion(root, app, fin.append)
    c.pack()
    bombear(root, 300)
    assert c.lbl_fase.cget("text")
    c.destroy()
