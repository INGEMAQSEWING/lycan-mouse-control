"""Ronda 2 de arreglos: cada prueba cubre una falla encontrada por los probadores de la ronda 2.

LÃ³gica (seÃ±as, mÃ¡quina de estados, puntero, perfiles), salida y pantallas, configuraciÃ³n,
motor, y la interfaz (ventana principal, asistente, Opciones).
"""
import math
import sys
import threading
import time
import tkinter as tk
from types import SimpleNamespace

import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles as P
from lycan_mouse_control.acciones import Rueda
from lycan_mouse_control.config import Configuracion, por_defecto
from lycan_mouse_control.estados import MaquinaEstados
from lycan_mouse_control.mapeo import Monitor
from lycan_mouse_control.motor import Motor, Vista
from lycan_mouse_control.salida.simulada import SalidaSimulada
from lycan_mouse_control.senas import Medidas, Sena
from lycan_mouse_control.sintetico import intermedia, mano

P0 = (0.5, 0.48)


def H(postura, pos=P0, lado="Right", **kw):
    """Mano con el CENTRO de la palma fijo (asÃ­ se cierra o se abre sin desplazarse)."""
    return mano(postura, posicion=pos, lado=lado, ancla="centro", **kw)


def bajadas(sim, t0, boton):
    return [t for t, ev in sim.salida.eventos if t >= t0 and ev == ("boton", boton, True)]


def activo(modo="2D", **kw):
    s = Sim(modo=modo, **kw)
    s.activar(P0)
    return s


# ======================================================== 1. hueco de un cuadro al empezar la pinza
@pytest.mark.parametrize("modo", ["2D", "3D"])
@pytest.mark.parametrize("hueco", [1, 2, 3])
def test_hueco_de_la_otra_mano_al_empezar_la_pinza_no_hace_clic(modo, hueco):
    s = activo(modo)
    t0 = s.t

    def par(f=0.0):
        return [H("pellizco", (0.62 + 0.1 * f, 0.5), "Right"), H("pellizco", (0.38 - 0.1 * f, 0.5), "Left")]
    s.durante(100, par())
    for _ in range(hueco):
        s.cuadro([H("pellizco", (0.62, 0.5), "Right")])     # MediaPipe pierde la izquierda
    s.durante(600, par)
    s.durante(300, [H("abierta", (0.62, 0.5), "Right"), H("abierta", (0.38, 0.5), "Left")])
    assert not bajadas(s, t0, "izq"), "clic izquierdo fantasma en mitad del zoom"
    assert any(ev[0] == "rueda" for t, ev in s.salida.eventos if t >= t0), "el zoom tiene que seguir"
    s.invariantes(final=False)


# ======================================================== 2. la mano sale del cuadro con una seÃ±a corta
@pytest.mark.parametrize("modo", ["2D", "3D"])
@pytest.mark.parametrize("postura,n", [("pellizco", 1), ("pellizco", 2), ("puno", 3), ("puno", 5)])
def test_sena_corta_y_la_mano_sale_del_cuadro_no_hace_clic(modo, postura, n):
    s = activo(modo)
    s.durante(300, H("abierta"))
    t0 = s.t
    for _ in range(n):
        s.cuadro([H(postura)])
    s.durante(400, [])                                       # la mano ya no se ve
    assert not [ev for t, ev in s.salida.eventos if t >= t0 and ev[0] == "boton" and ev[2]]
    s.invariantes()


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_activar_corto_y_la_mano_sale_no_activa(n):
    s = Sim(modo="2D")
    s.durante(500, H("abierta"))
    for _ in range(n):
        s.cuadro([H("juntos")])
    s.durante(400, [])
    assert s.base == K.PAUSA


def test_segunda_sena_corta_y_la_mano_sale_no_pausa():
    s = activo()
    s.durante(300, H("apuntar"))
    s.durante(300, H("juntos"))           # primera seÃ±a completa
    s.durante(300, H("apuntar"))
    for _ in range(3):                    # segunda: 3 cuadros y la mano se va
        s.cuadro([H("juntos")])
    s.durante(400, [])
    assert s.base == K.ACTIVO


def test_arrastre_en_curso_sigue_si_se_pierde_un_cuadro():
    s = activo()
    s.durante(300, H("apuntar"))
    t0 = s.t
    s.durante(300, H("pellizco"))
    assert bajadas(s, t0, "izq")
    s.cuadro([])                          # un cuadro sin mano: el botÃ³n sigue abajo
    assert "izq" in s.salida.botones_abajo
    s.durante(200, H("pellizco"))
    assert "izq" in s.salida.botones_abajo
    s.durante(300, H("apuntar"))
    assert "izq" not in s.salida.botones_abajo
    s.invariantes(final=False)


# ======================================================== 3. un cuadro suelto de ACTIVAR no es una seÃ±a
def _maquina_explicita():
    img = H("apuntar").img
    m = MaquinaEstados(dict(por_defecto(), modo="2D"))

    def seg(sena):
        p = SimpleNamespace(id=1, sena=sena, img=img, centro=img[[0, 5, 9, 13, 17], :2].mean(axis=0),
                            detectada=True, sospechosa=False, medidas=Medidas())
        return SimpleNamespace(principal=p, pistas=[p])
    reloj = {"t": 0.0}

    def correr(sena, n):
        for _ in range(n):
            m.paso(reloj["t"], seg(sena))
            reloj["t"] += 1 / 30
    m.activar(0.0)
    correr(Sena.APUNTAR, 40)                 # pasa la ventana de ignorar tras activar
    return m, correr


@pytest.mark.parametrize("entre", [Sena.NINGUNA, Sena.V])
@pytest.mark.parametrize("n1,n2", [(1, 1), (1, 2), (4, 1)])
def test_parpadeos_de_activar_entre_v_o_ninguna_no_pausan(entre, n1, n2):
    m, correr = _maquina_explicita()
    correr(entre, 9)
    correr(Sena.ACTIVAR, n1)
    correr(entre, 9)
    correr(Sena.ACTIVAR, n2)
    correr(entre, 15)
    assert m.base == K.ACTIVO


@pytest.mark.parametrize("entre", [Sena.NINGUNA, Sena.V, Sena.APUNTAR])
def test_doble_sena_de_verdad_si_pausa(entre):
    m, correr = _maquina_explicita()
    correr(entre, 9)
    correr(Sena.ACTIVAR, 4)
    correr(entre, 9)
    correr(Sena.ACTIVAR, 4)
    correr(entre, 15)
    assert m.base == K.PAUSA


@pytest.mark.parametrize("semilla", [1, 2, 3])
@pytest.mark.parametrize("t", [0.2, 0.25])
def test_indice_y_corazon_casi_juntos_con_temblor_no_se_pausa_solo(semilla, t):
    rng = np.random.default_rng(semilla)
    s = activo()
    P_ = intermedia("juntos", "v", t)
    s.durante(5000, lambda f: mano(P_, posicion=P0, ancla="centro", ruido_mm=2.0, rng=rng))
    assert s.base == K.ACTIVO


# ======================================================== 4. puÃ±o flojo con temblor
@pytest.mark.parametrize("t", [0.3, 0.35, 0.4, 0.45])
@pytest.mark.parametrize("ruido", [1.0, 2.0])
def test_puno_flojo_con_temblor_no_hace_clics_izquierdos(t, ruido):
    rng = np.random.default_rng(11)
    s = activo()
    t0 = s.t
    P_ = intermedia("relajada", "puno", t)
    s.durante(10000, lambda f: mano(P_, posicion=P0, ancla="centro", ruido_mm=ruido, rng=rng))
    assert not bajadas(s, t0, "izq")


def test_puno_en_curso_tiene_histeresis():
    from lycan_mouse_control.senas import Clasificador
    c = Clasificador()
    for _ in range(10):
        c.clasificar(intermedia("relajada", "puno", 0.45))     # ~99Â°: entra
    assert c._en_curso
    for _ in range(5):
        c.clasificar(intermedia("relajada", "puno", 0.25))     # ~75Â°: sigue (sale con < 72Â°)
    assert c._en_curso
    for _ in range(10):
        c.clasificar(intermedia("relajada", "pellizco", 0.9))  # pellizco real: sale
    assert not c._en_curso


def test_pellizco_real_despues_de_un_puno_sigue_funcionando():
    s = activo()
    s.durante(300, H("apuntar"))
    s.durante(400, H("puno"))
    s.durante(700, H("apuntar"))
    t0 = s.t
    s.durante(300, H("pellizco"))
    assert bajadas(s, t0, "izq")
    s.durante(300, H("apuntar"))
    s.invariantes(final=False)


# ======================================================== 5. monitor conectado sin cambiar la principal
def test_salida_windows_usa_el_escritorio_nuevo(monkeypatch):
    if sys.platform != "win32":
        pytest.skip("solo Windows")
    from lycan_mouse_control.salida import windows as W
    monkeypatch.setattr(W, "escritorio_virtual", lambda: (0, 0, 1366, 768))
    s = W.SalidaWindows()
    # se conecta un monitor de 1920x1080 a la IZQUIERDA; la principal sigue igual
    monkeypatch.setattr(W, "escritorio_virtual", lambda: (-1920, 0, 3286, 1080))
    for x, y in [(683, 384), (0, 0), (1365, 767)]:
        ev = s.construir([("mover",) + s._limitar(x, y)])[0]
        assert W.de_absoluto(ev.mi.dx, ev.mi.dy, -1920, 0, 3286, 1080) == (x, y)
    # y al desconectarlo
    monkeypatch.setattr(W, "escritorio_virtual", lambda: (0, 0, 1366, 768))
    ev = s.construir([("mover",) + s._limitar(683, 384)])[0]
    assert W.de_absoluto(ev.mi.dx, ev.mi.dy, 0, 0, 1366, 768) == (683, 384)


def test_motor_nota_el_cambio_de_escritorio_con_la_misma_principal(monkeypatch):
    from lycan_mouse_control.mapeo import Mapeo
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.sistema import pantallas
    from lycan_mouse_control.sistema import ventanas_win as vw
    principal = Monitor(0, 0, 1366, 768, True, trabajo=(0, 0, 1366, 720))
    escritorio = {"v": (0, 0, 1366, 768)}
    monkeypatch.setattr(pantallas, "escritorio_virtual", lambda: escritorio["v"])
    monkeypatch.setattr(pantallas, "elegir", lambda *_a, **_k: principal)
    monkeypatch.setattr(vw, "es_propia", lambda: True)
    monkeypatch.setattr(vw, "primer_plano_bloqueado", lambda: False)

    class SalidaConPantalla(SalidaSimulada):
        def __init__(self):
            super().__init__()
            self.actualizaciones = 0

        def actualizar_pantalla(self):
            self.actualizaciones += 1
    sal = SalidaConPantalla()
    m = Motor(por_defecto(), sal, sistema=False)
    m.monitor = principal
    m.mapeo = Mapeo(monitor=principal)
    m.nucleo = Nucleo(por_defecto(), mapeo=m.mapeo)
    m._escritorio = escritorio["v"]
    m.sistema = True
    ahora = time.perf_counter()
    m._t_rev_pantalla = ahora                      # la revisiÃ³n de 5 s todavÃ­a no toca
    m._t_rev_admin = m._t_rev_perfil = ahora
    m._t_rev_escritorio = 0.0
    m._revisiones(0.0)
    assert sal.actualizaciones == 0                # nada cambiÃ³
    escritorio["v"] = (-1920, 0, 3286, 1080)       # se conecta un monitor a la izquierda
    m._t_rev_escritorio = 0.0
    m._revisiones(0.0)
    assert sal.actualizaciones == 1
    assert m._escritorio == (-1920, 0, 3286, 1080)


# ======================================================== 6. pellizco cerrado despacio
@pytest.mark.parametrize("dur", [300, 400, 500])
@pytest.mark.parametrize("ruido", [0.0, 0.5])
def test_E9b_pellizco_lento_con_la_palma_quieta_cae_donde_estaba(dur, ruido):
    rng = np.random.default_rng(5)
    s = Sim()
    c = (0.45, 0.72)

    def W(post):
        return mano(post, posicion=c, ancla="centro", ruido_mm=ruido, rng=rng)
    s.durante(400, W("juntos"))
    s.durante(1400, W("apuntar"))
    antes = s.salida.cursor
    n = int(dur / 1000 * 30)
    for i in range(n):
        s.cuadro(W(intermedia("apuntar", "pellizco", (i + 1) / n)))
    s.durante(300, W("pellizco"))
    cursor = None
    al_bajar = None
    for _, ev in s.salida.eventos:
        if ev[0] == "mover":
            cursor = (ev[1], ev[2])
        if ev == ("boton", "izq", True):
            al_bajar = cursor
            break
    assert al_bajar is not None
    assert math.dist(al_bajar, antes) <= 4, (al_bajar, antes)


# ======================================================== 7. FreeCAD con estilo Blender
CFG_FREECAD = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<FCParameters><FCParamGroup Name="Root"><FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences">
<FCParamGroup Name="View"><FCText Name="NavigationStyle">Gui::{estilo}</FCText></FCParamGroup>
</FCParamGroup></FCParamGroup></FCParamGroup></FCParameters>"""


def test_freecad_lee_el_estilo_de_navegacion(tmp_path):
    assert P.leer_estilo_freecad(CFG_FREECAD.format(estilo="BlenderNavigationStyle")) == "blender"
    assert P.leer_estilo_freecad(CFG_FREECAD.format(estilo="CADNavigationStyle")) == "cad"
    assert P.leer_estilo_freecad("<FCParameters/>") is None
    carpeta = tmp_path / "FreeCAD" / "v1-0"
    carpeta.mkdir(parents=True)
    (carpeta / "user.cfg").write_text(CFG_FREECAD.format(estilo="BlenderNavigationStyle"), encoding="utf-8")
    assert P.estilo_freecad(str(tmp_path)) == "blender"
    assert P.estilo_freecad(str(tmp_path / "no_existe")) is None


def test_freecad_en_automatico_usa_el_perfil_del_estilo():
    ruta = "C:/Program Files/FreeCAD/bin/FreeCAD.exe"
    assert P.perfil_para_exe(ruta).clave == "freecad"
    assert P.perfil_para_exe(ruta, estilo_freecad="cad").clave == "freecad"
    p = P.perfil_para_exe(ruta, estilo_freecad="blender")
    assert p.clave == "freecad_blender"
    assert p.desplazar == P.SHIFT_MEDIO and p.orbitar == P.MEDIO
    # el estilo de FreeCAD no cambia los demÃ¡s programas
    assert P.perfil_para_exe("SketchUp.exe", estilo_freecad="blender").clave == "sketchup"


# ======================================================== 8. zoom de EDWIN CNC 3D sin acumular
def _gesto_zoom(s, n):
    def par(sep):
        return [H("pellizco", (0.5 + sep / 2, 0.5), "Right"), H("pellizco", (0.5 - sep / 2, 0.5), "Left")]
    for _ in range(n):
        s.durante(300, par(0.10))
        s.durante(800, lambda f: par(0.10 + 0.06 * f))
        s.durante(200, par(0.16))
        s.durante(800, lambda f: par(0.16 - 0.06 * f))
        s.durante(200, par(0.10))
        s.durante(400, [H("abierta", (0.55, 0.5), "Right"), H("abierta", (0.45, 0.5), "Left")])
        s.durante(300, [H("abierta", (0.55, 0.5), "Right")])


def test_zoom_edwin3d_separar_y_juntar_no_se_acumula():
    s = Sim(modo="3D", perfil="edwin3d")
    s.activar(P0)
    s.durante(300, H("abierta"))
    t0 = s.t
    _gesto_zoom(s, 3)
    ruedas = [ev[1] for t, ev in s.salida.eventos if t >= t0 and ev[0] == "rueda"]
    assert sum(r for r in ruedas if r > 0) > 0 and sum(r for r in ruedas if r < 0) < 0
    assert all(r % 120 == 0 for r in ruedas if r < 0), "alejar sigue siendo por muescas enteras"
    assert abs(sum(ruedas)) <= 60 * 3, f"neto {sum(ruedas)}: la vista se corre de un gesto a otro"


def test_traductor_redondea_el_resto_de_alejar():
    tr = P.Traductor(P.PERFILES["edwin3d"])
    assert tr.fraccion(-0.8) == []                 # -96: menos de una muesca, no sale nada
    assert tr.cerrar_fraccion() == [Rueda(-120)]   # al terminar se redondea
    assert tr.fraccion(-0.3) == []
    assert tr.cerrar_fraccion() == []              # -36: menos de media muesca, se descarta
    tr2 = P.Traductor(P.PERFILES["sketchup"])
    assert tr2.cerrar_fraccion() == []


# ======================================================== 9. atajos con teclas especiales
@pytest.mark.parametrize("tecla", ["Espacio", "Space", "Insert", "Supr", "Delete", "Inicio", "Home", "Fin",
                                   "End", "Pausa", "Pause", "F1", "F5", "F12", "M", "7"])
def test_atajo_ida_y_vuelta(tecla):
    if sys.platform != "win32":
        pytest.skip("solo Windows")
    from lycan_mouse_control.sistema import atajos as A
    for mods in ("Ctrl+Alt+", "Ctrl+Shift+", "Alt+"):
        m, v = A.interpretar(mods + tecla)
        texto = A.texto_atajo(m, v)
        assert "0x" not in texto
        assert A.interpretar(texto) == (m, v)


def test_todas_las_teclas_especiales_tienen_nombre():
    if sys.platform != "win32":
        pytest.skip("solo Windows")
    from lycan_mouse_control.sistema import atajos as A
    for nombre, vk in A.TECLAS_ESPECIALES.items():
        assert vk in A.NOMBRES_TECLA, nombre
        assert A.interpretar("Ctrl+Alt+" + A.NOMBRES_TECLA[vk])[1] == vk


# ======================================================== 10. config.json bloqueado al arrancar
def _bloquear_archivo(ruta):
    import ctypes
    import ctypes.wintypes as wt
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.argtypes = (wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE)
    k32.CreateFileW.restype = wt.HANDLE
    k32.CloseHandle.argtypes = (wt.HANDLE,)
    GENERIC_READ, OPEN_EXISTING = 0x80000000, 3
    h = k32.CreateFileW(str(ruta), GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)   # sin compartir
    assert h not in (None, wt.HANDLE(-1).value), ctypes.get_last_error()
    return lambda: k32.CloseHandle(h)


def test_config_bloqueada_al_arrancar_no_se_pierde(tmp_path):
    if sys.platform != "win32":
        pytest.skip("solo Windows")
    import json
    ruta = tmp_path / "config.json"
    datos = por_defecto()
    datos["primera_vez"] = False
    datos["modo"] = "3D"
    datos["calibracion"]["fecha"] = "2026-11-10 10:00"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    antes = ruta.read_bytes()
    soltar = _bloquear_archivo(ruta)
    try:
        cfg = Configuracion(ruta)
        t0 = time.perf_counter()
        cfg.cargar()
        assert time.perf_counter() - t0 < 2.0
        assert cfg.solo_lectura
        assert cfg.datos["primera_vez"] is False          # no vuelve a salir el asistente
        assert cfg.aviso and "sin cambiar su archivo" in cfg.aviso
        assert not list(tmp_path.glob("config.daÃ±ado-*"))
    finally:
        soltar()
    # al salir (app._finalizar -> guardar_seguro) NO se escribe encima
    assert cfg.guardar_seguro() is False
    assert ruta.read_bytes() == antes
    # la siguiente vez se lee bien
    cfg2 = Configuracion(ruta)
    cfg2.cargar()
    assert cfg2.datos["modo"] == "3D" and cfg2.datos["calibracion"]["fecha"] == "2026-11-10 10:00"
    assert not cfg2.solo_lectura


def test_config_bloqueada_un_momento_se_lee_al_reintentar(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    ruta = tmp_path / "config.json"
    datos = por_defecto()
    datos["modo"] = "3D"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    leer = Path.read_text
    intentos = {"n": 0}

    def read_text(self, *a, **k):
        if self == ruta and intentos["n"] < 2:
            intentos["n"] += 1
            raise PermissionError(13, "El archivo estÃ¡ en uso")
        return leer(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", read_text)
    cfg = Configuracion(ruta)
    cfg.cargar()
    assert intentos["n"] == 2
    assert cfg.datos["modo"] == "3D" and not cfg.solo_lectura and cfg.aviso is None


def test_config_danada_que_no_se_puede_apartar_no_se_escribe_encima(tmp_path, monkeypatch):
    import os
    ruta = tmp_path / "config.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")

    def reemplazo_denegado(a, b):
        raise PermissionError(13, "Acceso denegado")
    monkeypatch.setattr(os, "replace", reemplazo_denegado)
    cfg = Configuracion(ruta)
    cfg.cargar()
    assert cfg.solo_lectura
    monkeypatch.undo()
    assert cfg.guardar_seguro() is False
    assert ruta.read_text(encoding="utf-8") == "{ esto no es json"


# ======================================================== 11. cÃ¡mara perdida
def test_cuadros_por_segundo_en_cero_si_no_llegan_cuadros():
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    ahora = time.perf_counter()
    for k in range(30):
        m.stats.cuadro(ahora - 1.0 + k / 30)
    assert m.fps_vigente(ahora) > 20
    assert m.fps_vigente(ahora + 1.5) == 0.0


def test_camara_perdida_se_vuelve_a_avisar():
    from lycan_mouse_control.app import App
    from lycan_mouse_control.ui.textos import t
    avisos, programados = [], []
    falsa = SimpleNamespace(
        cerrando=False,
        motor=SimpleNamespace(camara=SimpleNamespace(estado="PERDIDA"), error_inicio=None),
        ventana=SimpleNamespace(mostrar_aviso=lambda txt, s=5: avisos.append((txt, s))),
        root=SimpleNamespace(after=lambda ms, f: programados.append(ms)),
        _revisar_camara=lambda: None)
    App._revisar_camara(falsa)
    assert avisos == [(t("aviso_camara_perdida"), 8)]
    assert programados == [8000]


# ======================================================== 12. el motor no muere por un error
class _Camara:
    def __init__(self):
        self.n, self.estado, self._vivo = 0, "FUNCIONANDO", False

    def is_alive(self):
        return self._vivo

    def start(self):
        self._vivo = True

    def ultimo(self, despues_de=0, espera=0.1):
        from lycan_mouse_control.captura import Cuadro
        time.sleep(1 / 30)
        self.n += 1
        return Cuadro(np.zeros((480, 640, 3), np.uint8), time.perf_counter(), self.n)

    def detener(self):
        self._vivo = False


def _esperar(cond, s=5.0):
    fin = time.perf_counter() + s
    while time.perf_counter() < fin:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_error_fuera_del_nucleo_no_mata_el_motor():
    det = SimpleNamespace(procesar=lambda img: [H("apuntar")], ms_ultimo=1.0)
    m = Motor(por_defecto(), SalidaSimulada(), camara=_Camara(), detector=det, sistema=False)
    original = m._comodidad
    llamadas = {"n": 0}

    def comodidad_que_falla(t, res):
        llamadas["n"] += 1
        if llamadas["n"] == 30:
            raise ValueError("cannot convert float NaN to integer (prueba)")
        return original(t, res)
    m._comodidad = comodidad_que_falla
    m.start()
    try:
        assert m.listo.wait(5)
        m.ordenes.put(("pausar",))
        assert _esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
        assert _esperar(lambda: llamadas["n"] > 30)
        assert m.is_alive()
        avisos = []
        while not m.avisos.empty():
            avisos.append(m.avisos.get())
        assert any(getattr(a, "clave", "") == "error" for a in avisos)
        assert m.nucleo.maquina.base == K.PAUSA          # se pausÃ³
        m.ordenes.put(("pausar",))                       # y los atajos siguen funcionando
        assert _esperar(lambda: m.nucleo.maquina.base == K.ACTIVO)
    finally:
        m.detener()
        m.join(3)
    assert m.salida.todo_suelto()


# ======================================================== interfaz
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


def test_ventana_avisa_si_el_motor_murio(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    from test_interfaz import AppFalsa, bombear
    app = AppFalsa(tmp_path)
    listo, parar = threading.Event(), threading.Event()
    listo.set()
    app.motor.is_alive = lambda: False
    app.motor.listo, app.motor._parar, app.motor.error_inicio = listo, parar, None
    v = VentanaPrincipal(root, app)
    bombear(root, 200)
    assert v.lbl_aviso.cget("text") == t("aviso_motor_detenido")
    assert v.lbl_aviso.winfo_manager() == "place"
    app.cerrando = True


def test_ventana_no_avisa_si_el_motor_se_detuvo_a_proposito(root, tmp_path):
    from lycan_mouse_control.ui.textos import t
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    from test_interfaz import AppFalsa, bombear
    app = AppFalsa(tmp_path)
    listo, parar = threading.Event(), threading.Event()
    listo.set()
    parar.set()
    app.motor.is_alive = lambda: False
    app.motor.listo, app.motor._parar, app.motor.error_inicio = listo, parar, None
    v = VentanaPrincipal(root, app)
    bombear(root, 200)
    assert v.lbl_aviso.cget("text") != t("aviso_motor_detenido")
    app.cerrando = True


def test_video_gris_con_la_camara_perdida(root, tmp_path):
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    from test_interfaz import AppFalsa, bombear
    app = AppFalsa(tmp_path)
    v = VentanaPrincipal(root, app)
    app.motor.vistas.put(Vista(estado=K.PAUSA, camara="PERDIDA", imagen=None, fps=0.0))
    bombear(root, 150)
    assert v.lbl_sin_imagen.winfo_manager() == "place"
    assert v.lbl_fps.cget("text") == ""
    app.motor.vistas.put(Vista(estado=K.PAUSA, camara="FUNCIONANDO", imagen=np.zeros((240, 320, 3), np.uint8),
                               fps=30.0))
    bombear(root, 150)
    assert v.lbl_sin_imagen.winfo_manager() == ""
    app.cerrando = True


def test_nombres_de_sena_caben_en_la_franja(root):
    import tkinter.font as tkfont
    from lycan_mouse_control.ui.comun import LETRA
    from lycan_mouse_control.ui.textos import TXT
    f = tkfont.Font(root=root, family=LETRA, size=20, weight="bold")
    for clave, texto in TXT.items():
        if clave.startswith("sena_"):
            assert f.measure(texto) < 316, (clave, texto, f.measure(texto))


def test_franja_achica_la_letra_de_un_texto_largo(root, tmp_path):
    from lycan_mouse_control.ui.ventana_principal import ANCHO_SENA, VentanaPrincipal
    from test_interfaz import AppFalsa
    import tkinter.font as tkfont
    from lycan_mouse_control.ui.comun import LETRA
    app = AppFalsa(tmp_path)
    v = VentanaPrincipal(root, app)
    largo = "UN TEXTO BASTANTE MÃS LARGO QUE LA FRANJA"
    tam = v.tam_sena(largo)
    assert tam < 20
    if tkfont.Font(root=root, family=LETRA, size=12, weight="bold").measure(largo) <= ANCHO_SENA:
        assert tkfont.Font(root=root, family=LETRA, size=tam, weight="bold").measure(largo) <= ANCHO_SENA
    assert v.tam_sena("PUÃ‘O") == 20
    app.cerrando = True


def test_una_sola_ventana_de_opciones(root, tmp_path):
    from lycan_mouse_control.app import App
    from test_ronda1_interfaz import AppModo
    from test_interfaz import bombear

    class AppUnica(AppModo):
        abrir_opciones = App.abrir_opciones
    app = AppUnica(tmp_path, "2D")
    app.root = root
    app._opciones = None
    a = app.abrir_opciones()
    b = app.abrir_opciones()
    assert a is b
    bombear(root, 50)
    a.cancelar()
    c = app.abrir_opciones()
    assert c is not a
    c.cancelar()


def test_cancelar_no_borra_lo_que_otra_ventana_guardo(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from test_ronda1_interfaz import AppModo
    app = AppModo(tmp_path, "2D")
    a = VentanaOpciones(root, app)
    b = VentanaOpciones(root, app)
    a.cfg["comodidad"]["sonidos"] = False
    a.guardar()
    assert app.cfg.datos["comodidad"]["sonidos"] is False
    b.cancelar()
    assert app.cfg.datos["comodidad"]["sonidos"] is False
    assert app.ordenes[-1][1]["comodidad"]["sonidos"] is False


def test_asistente_pausar_va_al_final():
    from lycan_mouse_control.ui.asistente import pasos_para
    for modo in ("2D", "3D"):
        claves = [p.clave for p in pasos_para(modo)]
        assert claves[-1] == "pausar"
    assert [p.clave for p in pasos_para("3D")][-4:] == ["girar", "desplazar", "soltar", "pausar"]


def test_asistente_avisa_que_esta_en_pausa(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    from test_ronda1_interfaz import AppModo
    from test_interfaz import bombear
    app = AppModo(tmp_path, "3D")
    app.root = root
    a = Asistente(root, app)
    try:
        a.i = [p.clave for p in a.pasos].index("girar")
        a._mostrar()
        app.ultima_vista = Vista(estado=K.PAUSA, modo="3D", imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 200)
        assert a.lbl_pista.cget("text") == t("as_reactivar")
        app.ultima_vista = Vista(estado=K.ACTIVO, modo="3D", imagen=np.zeros((240, 320, 3), np.uint8))
        bombear(root, 200)
        assert a.lbl_pista.cget("text") != t("as_reactivar")
    finally:
        a.cerrar()


def test_paso_camara_no_dice_luz_bien_sin_imagen():
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    yo = SimpleNamespace()
    nan = float("nan")
    assert Asistente.texto_camara(yo, Vista(camara="OCUPADA", brillo=nan), 100.0) == t("aviso_camara_ocupada")
    assert Asistente.texto_camara(yo, Vista(camara="NO_ABRE", brillo=nan), 100.0) == t("aviso_no_camara")
    txt = Asistente.texto_camara(yo, Vista(camara="FUNCIONANDO", brillo=nan, manos=0), 100.0)
    assert txt == t("as_sin_imagen") and t("cal_luz_ok") not in txt
    yo2 = SimpleNamespace()
    txt = Asistente.texto_camara(yo2, Vista(camara="FUNCIONANDO", brillo=120.0, manos=1), 100.0)
    assert txt == t("cal_luz_ok")
    # una vista suelta sin cuadro nuevo justo despuÃ©s no cambia el texto
    txt = Asistente.texto_camara(yo2, Vista(camara="FUNCIONANDO", brillo=nan, manos=1), 100.3)
    assert txt == t("cal_luz_ok")
    txt = Asistente.texto_camara(yo2, Vista(camara="FUNCIONANDO", brillo=nan, manos=1), 102.0)
    assert txt == t("as_sin_imagen")
