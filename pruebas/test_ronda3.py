"""Ronda 3 de arreglos: puño fantasma, reactivar con el atajo, modo relativo, atajos repetidos,
rangos de config.json, «valores de fábrica» con Cancelar y workflow de GitHub con Python 3.10."""
import io
import os
import queue
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import numpy as np
import pytest

from conftest import RAIZ, Sim, M
from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Bajar, Clic, Mover
from lycan_mouse_control.config import FABRICA, Configuracion, validar
from lycan_mouse_control.mapeo import Mapeo, Monitor
from lycan_mouse_control.puntero import Puntero
from lycan_mouse_control.senas import Sena
from lycan_mouse_control.sintetico import intermedia
from test_interfaz import bombear, root  # noqa: F401 (fixture)
from test_ronda1_interfaz import AppModo


def _clics_der(s, t0):
    return [t for t, a in s.acciones if t >= t0 and isinstance(a, Clic) and a.boton == K.DER]


def _bajar_izq(s, t0):
    return [t for t, a in s.acciones if t >= t0 and isinstance(a, Bajar) and a.boton == K.IZQ]


# ======================================================== 1. clic derecho fantasma
@pytest.mark.parametrize("fps", [30, 25, 20])
def test_un_cuadro_de_ninguna_dentro_del_puno_no_repite_el_clic_derecho(fps):
    s = Sim(fps=fps)
    s.activar()
    t0 = s.t
    for _ in range(int(fps * 0.8)):
        s.cuadro(M("puno"))
    s.cuadro(M(intermedia("puno", "abierta", 0.45)))       # el clasificador da NINGUNA
    assert s.nucleo.seguidor.principal.sena == Sena.NINGUNA
    for _ in range(int(fps * 1.0)):
        s.cuadro(M("puno"))
    assert len(_clics_der(s, t0)) == 1
    s.durante(300, M("apuntar"))
    s.invariantes()


@pytest.mark.parametrize("semilla", [1, 2, 3, 9])
@pytest.mark.parametrize("desde,mezcla", [("abierta", 0.85), ("relajada", 0.8), ("juntos", 0.85),
                                          ("v", 0.85)])
def test_puno_flojo_con_temblor_da_un_solo_clic_derecho(desde, mezcla, semilla):
    rng = np.random.default_rng(semilla)
    P = intermedia(desde, "puno", mezcla)
    s = Sim()
    s.activar()
    t0 = s.t
    s.durante(4000, lambda f: M(P, ruido_mm=2.0, rng=rng))
    assert len(_clics_der(s, t0)) <= 1
    assert not s.de_tipo(Bajar)


def test_puno_abrir_la_mano_y_otro_puno_si_da_dos_clics_derechos():
    s = Sim()
    s.activar()
    t0 = s.t
    s.durante(400, M("puno"))
    s.durante(400, M("abierta"))
    s.durante(400, M("puno"))
    assert len(_clics_der(s, t0)) == 2
    s.durante(300, M("apuntar"))
    s.invariantes()


def test_puno_y_medio_segundo_de_ninguna_rearma_el_clic_derecho():
    s = Sim()
    s.activar()
    t0 = s.t
    s.durante(400, M("puno"))
    s.durante(700, M(intermedia("puno", "abierta", 0.45)))
    s.durante(400, M("puno"))
    assert len(_clics_der(s, t0)) == 2


def test_ninguna_intercalada_antes_del_clic_no_acumula_la_espera_del_puno():
    """Una mano ambigua (casi siempre NINGUNA con algún cuadro suelto de PUNO) no hace clic."""
    s = Sim()
    s.activar()
    t0 = s.t
    ni = M(intermedia("puno", "abierta", 0.45))
    for _ in range(15):
        s.cuadro(M("puno"))
        s.cuadro(ni)
    assert _clics_der(s, t0) == []


# ======================================================== 2. reactivar con el atajo
@pytest.mark.parametrize("postura", ["pellizco", "puno"])
def test_reactivar_con_el_atajo_en_pellizco_o_puno_no_presiona_nada(postura):
    s = Sim()
    s.activar()
    s.durante(200, M("apuntar"))
    s.durante(300, M(postura))
    s.orden(s.nucleo.alternar_pausa(s.t))                   # pausa (suelta todo)
    assert s.base == K.PAUSA
    s.durante(500, M(postura))
    s.orden(s.nucleo.alternar_pausa(s.t))                   # reactiva con la mano en la seña
    assert s.base == K.ACTIVO
    ta = s.t
    s.durante(800, M(postura))
    assert _bajar_izq(s, ta) == [] and _clics_der(s, ta) == []
    # después de una seña neutra todo vuelve a funcionar
    s.durante(300, M("apuntar"))
    t1 = s.t
    s.durante(400, M(postura))
    assert (_bajar_izq(s, t1) if postura == "pellizco" else _clics_der(s, t1))
    s.durante(300, M("apuntar"))
    s.invariantes()


def test_activar_tras_guardar_opciones_con_la_mano_en_pellizco_no_arrastra():
    """motor.py recrea el Nucleo al guardar Opciones y lo activa directo."""
    s = Sim()
    s.durante(200, M("pellizco"))
    s.orden(s.nucleo.maquina.activar(s.t))
    ta = s.t
    s.durante(800, M("pellizco"))
    assert _bajar_izq(s, ta) == []
    s.invariantes()


def test_reactivar_con_el_atajo_con_dos_punos_no_empieza_a_girar():
    def L(p):
        return M(p, (0.35, 0.5), "Left", ancla="centro")

    def R(p):
        return M(p, (0.65, 0.5), "Right", ancla="centro")
    s = Sim(modo="3D")
    s.activar(pos=(0.65, 0.5))
    s.orden(s.nucleo.alternar_pausa(s.t))
    s.durante(300, [L("puno"), R("puno")])
    s.orden(s.nucleo.alternar_pausa(s.t))
    ta = s.t
    s.durante(800, [L("puno"), R("puno")])
    assert not [a for t, a in s.acciones if t >= ta and isinstance(a, Bajar)]
    assert s.estado != K.GIRANDO_3D
    s.invariantes()


# ======================================================== 3. modo relativo
def test_modo_relativo_al_activar_sigue_desde_el_cursor_real():
    s = Sim(cfg={"puntero": {"modo": "relativo"}})
    s.durante(1500, lambda f: M("apuntar", (0.3 + 0.4 * f, 0.5)))   # en pausa: no acumula
    assert not s.eventos("mover")
    s.salida.cursor = (100, 100)                                      # el usuario movió el ratón
    t0 = s.t
    s.durante(400, M("juntos", (0.7, 0.5)))
    s.durante(900, M("apuntar", (0.7, 0.5)))
    assert s.base == K.ACTIVO
    movs = [a for t, a in s.acciones if t >= t0 and isinstance(a, Mover)]
    if movs:
        assert abs(movs[0].x - 100) <= 2 and abs(movs[0].y - 100) <= 2
    assert abs(s.salida.cursor[0] - 100) <= 2 and abs(s.salida.cursor[1] - 100) <= 2


def test_modo_relativo_reset_olvida_la_posicion_y_toma_la_del_cursor():
    mon = Monitor(0, 0, 1366, 768)
    cursor = [(683, 384)]
    p = Puntero(Mapeo((0.2, 0.25, 0.8, 0.7), mon), {"modo": "relativo"}, pos_cursor=lambda: cursor[0])
    for i in range(20):
        p.observar(i / 30, 0.3 + i * 0.02, 0.5)
    assert p._rel_pos[0] > 900
    p.reset()
    assert p._rel_pos is None
    cursor[0] = (50, 60)
    p.observar(1.0, 0.5, 0.5)
    assert p._rel_pos == (50.0, 60.0)
    # sin función de cursor: el centro del monitor; un cursor fuera del monitor se recorta
    q = Puntero(Mapeo((0.2, 0.25, 0.8, 0.7), mon), {"modo": "relativo"})
    q.observar(0.0, 0.5, 0.5)
    assert q._rel_pos == (683.0, 384.0)
    r = Puntero(Mapeo((0.2, 0.25, 0.8, 0.7), mon), {"modo": "relativo"}, pos_cursor=lambda: (3000, -50))
    r.observar(0.0, 0.5, 0.5)
    assert r._rel_pos == (1365.0, 0.0)


def test_modo_relativo_en_pausa_no_acumula_movimiento():
    s = Sim(cfg={"puntero": {"modo": "relativo"}})
    s.durante(1000, lambda f: M("apuntar", (0.3 + 0.4 * f, 0.5)))
    pos = s.nucleo.maquina.puntero._rel_pos
    assert pos is None or abs(pos[0] - 683) <= 2


# ======================================================== 4. atajos repetidos
def test_atajo_repetido_detecta_combinaciones_iguales_aunque_se_escriban_distinto():
    from lycan_mouse_control.ui.opciones import atajo_repetido
    base = dict(FABRICA["atajos"])
    assert atajo_repetido(base) is None
    a = dict(base, pausar="Ctrl+Alt+F9", salir="Ctrl+Alt+F9")
    assert atajo_repetido(a) == ("Ctrl+Alt+F9", "pausar", "salir")
    b = dict(base, ventana="ctrl+alt+f10", modo="Alt+Ctrl+F10")
    assert atajo_repetido(b) == ("Ctrl+Alt+F10", "ventana", "modo")


def test_opciones_no_guarda_atajos_repetidos(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    op._entradas["pausar"].set("Ctrl+Alt+F9")
    op._entradas["salir"].set("Alt+ctrl+f9")
    op.guardar()
    assert op.win.winfo_exists()                          # no se cerró: no se guardó
    assert "ya está asignado" in op.lbl_atajo.cget("text")
    assert "Pausar" in op.lbl_atajo.cget("text") and "Salir" in op.lbl_atajo.cget("text")
    assert app.cfg.datos["atajos"]["salir"] == FABRICA["atajos"]["salir"]
    assert not app.cfg.ruta.exists() or "F9" not in app.cfg.ruta.read_text(encoding="utf-8")
    op._entradas["salir"].set("Ctrl+Alt+X")
    op.guardar()
    assert app.cfg.datos["atajos"]["pausar"] == "Ctrl+Alt+F9"
    assert app.cfg.datos["atajos"]["salir"] == "Ctrl+Alt+X"


def test_orden_de_registro_salir_primero():
    from lycan_mouse_control.sistema.atajos import orden_registro
    filas = orden_registro({"pausar": "a", "salir": "b", "ventana": "c"})
    assert [n for _, n, _ in filas] == ["salir", "pausar", "ventana"]
    assert dict((n, i) for i, n, _ in filas) == {"pausar": 1, "salir": 2, "ventana": 3}


def test_hilo_atajos_repetidos_gana_salir_y_el_aviso_no_culpa_a_otro_programa():
    from lycan_mouse_control.sistema import atajos as A
    h = A.HiloAtajos({"pausar": "Ctrl+Alt+Shift+F11", "salir": "Ctrl+Alt+Shift+F11"}, queue.Queue())
    h.start()
    assert h.listo.wait(5)
    try:
        nombres = [n for n, _ in h.fallidos]
        assert "pausar" in nombres and "salir" not in nombres
        txt = dict(h.fallidos)["pausar"]
        assert "repetido" in txt and "otro programa" not in txt and "Salir" in txt
        if h.registrados:                         # si ningún otro programa lo tiene tomado
            assert list(h.registrados.values()) == ["salir"]
    finally:
        h.detener()
        h.join(2)


# ======================================================== 5. rangos de config.json
@pytest.mark.parametrize("valor", [[66, 1000000000], [-5, 1e9], [66, 10], [5000, 66], [66, float("inf")]])
def test_tiempos_del_pellizco_fuera_de_rango_vuelven_a_fabrica(valor):
    pr = []
    c = validar({"senas": {"tiempos_ms": {"pellizco": valor}}}, problemas=pr)
    assert c["senas"]["tiempos_ms"]["pellizco"] == [66, 66]
    assert any("pellizco" in p for p in pr)


def test_tiempos_del_pellizco_validos_se_respetan():
    c = validar({"senas": {"tiempos_ms": {"pellizco": [80, 120.4]}}})
    assert c["senas"]["tiempos_ms"]["pellizco"] == [80, 120]


def test_doblez_fuera_de_rango_vuelve_a_fabrica():
    c = validar({"senas": {"doblez": {"extendido": [60, 900]}}})
    assert c["senas"]["doblez"]["extendido"] == FABRICA["senas"]["doblez"]["extendido"]


@pytest.mark.parametrize("valor,esperado", [(0, 0), (0.001, 5), (3, 5), (5, 5), (20, 20), (61, 20)])
def test_descanso_es_cero_o_desde_cinco_minutos(valor, esperado):
    c = validar({"comodidad": {"descanso_min": valor}})
    assert c["comodidad"]["descanso_min"] == esperado


def test_campos_enteros_se_redondean_y_los_angulos_calibrados_conservan_decimales():
    pr = []
    c = validar({"camara": {"indice": 1.4, "fps": 30.0}, "senas": {"juntos": {"a_entrar": 11.734}}}, problemas=pr)
    assert c["camara"]["indice"] == 1 and isinstance(c["camara"]["indice"], int)
    assert c["camara"]["fps"] == 30 and isinstance(c["camara"]["fps"], int)
    assert c["senas"]["juntos"]["a_entrar"] == 11.734
    assert not any("a_entrar" in p for p in pr)


def test_pellizco_con_tiempo_de_soltar_enorme_sin_validar_no_deja_el_boton_pegado():
    s = Sim(cfg={"senas": {"tiempos_ms": {"pellizco": [66, 1000000000]}}})
    s.activar()
    s.durante(300, M("apuntar"))
    s.durante(150, M("pellizco"))
    d = 200 / s.mapeo.px_por_unidad_x
    s.durante(600, lambda f: M("pellizco", (0.5 + d * f, 0.5)))
    s.durante(1500, M("apuntar", (0.5 + d, 0.5)))
    assert s.estado == K.ACTIVO
    assert not s.salida.botones_abajo
    s.invariantes()


# ======================================================== 6. valores de fábrica y Cancelar
class AppComodidad(AppModo):
    def __init__(self, tmp_path):
        super().__init__(tmp_path, "2D")
        self.comodidad_aplicada = 0
        self._opciones = None

    def aplicar_comodidad(self):
        self.comodidad_aplicada += 1


def _app_con_ajustes(tmp_path):
    app = AppComodidad(tmp_path)
    app.cfg.datos["comodidad"]["opacidad"] = 0.7
    app.cfg.datos["calibracion"] = {"fecha": "2026-11-12", "luz": 120.0, "tam_mano": 0.2}
    app.cfg.datos["atajos"]["pausar"] = "Ctrl+Alt+F9"
    app.cfg.guardar_seguro(app.cfg.datos)
    return app


def test_fabrica_pregunta_y_si_dice_que_no_no_cambia_nada(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = _app_con_ajustes(tmp_path)
    op = VentanaOpciones(root, app)
    preguntas = []
    op._preguntar = lambda txt: preguntas.append(txt) or False
    assert op.fabrica() is None
    assert preguntas and "calibración" in preguntas[0] and "atajos se conservan" in preguntas[0]
    assert op.win.winfo_exists()
    assert app.cfg.datos["comodidad"]["opacidad"] == 0.7
    assert not [o for o in app.ordenes if o[0] == "config"]
    op.cancelar()


def test_fabrica_y_cancelar_conserva_la_calibracion_y_las_opciones(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = _app_con_ajustes(tmp_path)
    op = VentanaOpciones(root, app)
    op._preguntar = lambda txt: True
    nueva = op.fabrica()
    assert nueva is not None and nueva is not op and app._opciones is nueva
    # la ventana nueva muestra fábrica, pero lo guardado sigue intacto
    assert nueva.cfg["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]
    assert nueva.cfg["calibracion"]["fecha"] is None
    assert nueva.cfg["atajos"]["pausar"] == "Ctrl+Alt+F9"            # los atajos se conservan
    assert app.cfg.datos["comodidad"]["opacidad"] == 0.7
    assert app.cfg.datos["calibracion"]["fecha"] == "2026-11-12"
    assert app.ordenes[-1][0] == "config"
    assert app.ordenes[-1][1]["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]   # en vivo
    bombear(root, 50)
    nueva.cancelar()
    assert app.cfg.datos["comodidad"]["opacidad"] == 0.7
    assert app.cfg.datos["calibracion"]["fecha"] == "2026-11-12"
    assert app.ordenes[-1][1]["comodidad"]["opacidad"] == 0.7
    assert app.comodidad_aplicada >= 1
    disco = Configuracion(app.cfg.ruta)
    disco.cargar()
    assert disco.datos["calibracion"]["fecha"] == "2026-11-12"


def test_fabrica_y_guardar_restablece_pero_conserva_atajos(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = _app_con_ajustes(tmp_path)
    op = VentanaOpciones(root, app)
    op._preguntar = lambda txt: True
    nueva = op.fabrica()
    nueva.guardar()
    assert app.cfg.datos["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]
    assert app.cfg.datos["calibracion"]["fecha"] is None
    assert app.cfg.datos["atajos"]["pausar"] == "Ctrl+Alt+F9"
    assert app.cfg.datos["primera_vez"] is False


def test_cancelar_vuelve_a_aplicar_la_comodidad(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppComodidad(tmp_path)
    op = VentanaOpciones(root, app)
    op.cancelar()
    assert app.comodidad_aplicada == 1


# ======================================================== 7. workflow con Python 3.10 sin filter=
def _codigo_extraccion(rel):
    wf = (RAIZ / rel).read_text(encoding="utf-8")
    linea = next(ln for ln in wf.splitlines() if "PYI_SRC=" in ln and "tarfile" in ln)
    m = re.search(r'python -c "(.*)"\)"\s*$', linea)
    assert m, linea
    return m.group(1)


@pytest.mark.parametrize("rel", [".github/workflows/windows.yml", "empaquetado/lycan-mouse-windows.yml"])
def test_workflow_descomprime_pyinstaller_con_python_310(rel, tmp_path):
    codigo = _codigo_extraccion(rel)
    assert "filter='data')" not in codigo.replace("{'filter': 'data'}", "")
    pyi = tmp_path / "pyi"
    pyi.mkdir()
    with tarfile.open(pyi / "pyinstaller-6.22.3.tar.gz", "w:gz") as t:
        datos = b"hola"
        info = tarfile.TarInfo("pyinstaller-6.22.3/bootloader/wscript")
        info.size = len(datos)
        t.addfile(info, io.BytesIO(datos))
    env = dict(os.environ, RUNNER_TEMP=str(tmp_path))
    r = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, text=True, env=env,
                       cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stderr
    salida = Path(r.stdout.strip())
    assert salida == pyi / "pyinstaller-6.22.3"
    assert (salida / "bootloader" / "wscript").read_bytes() == b"hola"

