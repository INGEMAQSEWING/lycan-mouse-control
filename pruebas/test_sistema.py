"""11.5: atajos (AltGr con ToUnicode, error 1409), registro de errores, textos y calibración."""
import logging
import sys

import numpy as np
import pytest

from lycan_mouse_control import calibracion as CAL
from lycan_mouse_control import registro
from lycan_mouse_control.sistema import atajos as A
from lycan_mouse_control.ui import textos as T


# ---------------------------------------------------------------- atajos
@pytest.mark.parametrize("texto,mods,vk", [
    ("Ctrl+Alt+M", A.MOD_CONTROL | A.MOD_ALT, ord("M")),
    ("ctrl + alt + x", A.MOD_CONTROL | A.MOD_ALT, ord("X")),
    ("Ctrl+Alt+F9", A.MOD_CONTROL | A.MOD_ALT, 0x78),
    ("Alt+Shift+2", A.MOD_ALT | A.MOD_SHIFT, ord("2")),
])
def test_interpretar_atajos(texto, mods, vk):
    assert A.interpretar(texto) == (mods, vk)


@pytest.mark.parametrize("texto", ["", "M", "Shift+M", "Ctrl+Alt", "Ctrl+Alt+Ñandú", None])
def test_atajos_invalidos(texto):
    with pytest.raises(A.AtajoInvalido):
        A.interpretar(texto)


def test_texto_atajo_ida_y_vuelta():
    for t in ("Ctrl+Alt+M", "Ctrl+Alt+F9", "Ctrl+Alt+X"):
        assert A.texto_atajo(*A.interpretar(t)) == t


def test_ctrl_alt_q_escribe_arroba_en_teclado_latinoamericano():
    hkl = A.teclado_latinoamericano()
    if hkl is None:
        pytest.skip("El teclado latinoamericano no está instalado")
    assert A.produce_caracter(*A.interpretar("Ctrl+Alt+Q"), hkl=hkl) == "@"
    for t in ("Ctrl+Alt+M", "Ctrl+Alt+X", "Ctrl+Alt+O", "Ctrl+Alt+P"):
        assert A.produce_caracter(*A.interpretar(t), hkl=hkl) is None, t


def test_ctrl_alt_d_libre_o_alternativa():
    hkl = A.teclado_latinoamericano()
    if hkl is None:
        pytest.skip("El teclado latinoamericano no está instalado")
    car = A.produce_caracter(*A.interpretar("Ctrl+Alt+D"), hkl=hkl)
    if car:
        assert A.produce_caracter(*A.interpretar("Ctrl+Alt+F9"), hkl=hkl) is None


def test_error_1409_texto_correcto():
    txt = A.texto_error_registro("Ctrl+Alt+M", 1409)
    assert txt == "El atajo Ctrl+Alt+M ya lo usa otro programa. Puede cambiarlo en Opciones > Atajos."
    assert "código 5" in A.texto_error_registro("Ctrl+Alt+M", 5)


def test_hilo_de_atajos_registra_y_se_detiene():
    import queue
    cola = queue.Queue()
    # combinaciones raras para no chocar con nada del usuario
    h = A.HiloAtajos({"x": "Ctrl+Alt+Shift+F11", "malo": "Ctrl+Alt+Q", "invalido": "M"}, cola)
    h.start()
    assert h.listo.wait(5)
    nombres = [n for n, _ in h.fallidos]
    assert "invalido" in nombres
    if A.produce_caracter(*A.interpretar("Ctrl+Alt+Q")):
        assert "malo" in nombres
    h.detener()
    h.join(3)
    assert not h.is_alive()


# ---------------------------------------------------------------- registro
def test_registro_crea_carpeta_y_rota(tmp_path):
    ruta = registro.configurar(tmp_path / "reg", max_bytes=2000)
    log = logging.getLogger("lycan")
    for i in range(200):
        log.info("línea de prueba número %d con tildes áéíóú", i)
    assert ruta.exists()
    copias = list((tmp_path / "reg").glob("registro.txt*"))
    assert 2 <= len(copias) <= 4
    assert "tildes" in ruta.read_text(encoding="utf-8")


def test_registro_funciona_sin_consola(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    registro.configurar(tmp_path / "r2")
    print("esto no debe romper nada")
    sys.stderr.write("tampoco esto")


def test_ganchos_de_excepcion_llaman_al_fallar(tmp_path):
    import threading
    registro.configurar(tmp_path / "r3")
    vistos = []
    viejo_hook, viejo_th = sys.excepthook, threading.excepthook
    try:
        registro.instalar_ganchos(vistos.append)
        h = threading.Thread(target=lambda: 1 / 0)
        h.start()
        h.join()
        assert vistos and isinstance(vistos[0], ZeroDivisionError)
    finally:
        sys.excepthook, threading.excepthook = viejo_hook, viejo_th


# ---------------------------------------------------------------- textos
def test_textos_sin_jerga():
    for clave, txt in T.TXT.items():
        bajo = " " + txt.lower() + " "
        for palabra in T.PALABRAS_PROHIBIDAS:
            assert palabra not in bajo, (clave, palabra)


def test_textos_obligatorios_de_la_especificacion():
    obligatorios = [
        "PAUSADO — haga la seña de activar (índice y corazón juntos) para empezar",
        "ACTIVO — mueva el dedo índice",
        "SIN MANO — se soltaron todos los botones",
        "Modo 3D: dos manos cerradas para girar el modelo.",
        "Girar el modelo: cierre las dos manos como si agarrara un volante y gírelas. Abra las manos para soltar.",
        "Mover el dibujo: haga pellizco con las dos manos y muévalas juntas.",
        "Acercar o alejar: con pellizco en las dos manos, sepárelas o júntelas.",
        "Junte el dedo índice y el corazón, estirados y pegados, como diciendo «dos». Sosténgalos un momento (un cuarto de segundo).",
        "Se cerrará Lycan Mouse Control y el ratón volverá a funcionar normal.",
        "Su equipo va lento: cierre otros programas o baje la resolución.",
    ]
    todos = set(T.TXT.values())
    for o in obligatorios:
        assert o in todos, o


def test_hay_texto_para_cada_estado_y_aviso():
    from lycan_mouse_control import constantes as K
    from lycan_mouse_control.acciones import Aviso
    for e in K.COLORES_ESTADO:
        assert "estado_" + e in T.TXT and "ayuda_" + e in T.TXT
    for clave in ("sena_larga", "pausa_sin_mano", "sobre_ventana", "bloqueado_admin", "bloqueado_envio", "error",
                  "camara_perdida", "lento", "brazo_alto"):
        assert T.texto_aviso(Aviso(clave)) != clave
    assert "SketchUp" in T.texto_aviso(Aviso("perfil", "SketchUp"))
    assert T.t("clave_que_no_existe") == "clave_que_no_existe"


def test_textos_tratan_de_usted():
    tuteo = (" tú ", " haz ", " mueve tu", " tu mano", " puedes ")
    for txt in T.TXT.values():
        bajo = " " + txt.lower() + " "
        for p in tuteo:
            assert p not in bajo, txt


# ---------------------------------------------------------------- calibración
def test_luz_y_distancia():
    assert CAL.evaluar_luz(40) == "poca"
    assert CAL.evaluar_luz(230) == "mucha"
    assert CAL.evaluar_luz(120) == "ok"
    # sin imagen no se puede decir que la luz está bien (ronda 2)
    assert CAL.evaluar_luz(float("nan")) == "sin_dato"
    assert CAL.evaluar_luz(None) == "sin_dato"
    assert CAL.evaluar_distancia(0.05) == "cerca"
    assert CAL.evaluar_distancia(0.30) == "lejos"
    assert CAL.evaluar_distancia(0.15) == "ok"
    assert CAL.evaluar_distancia(None) == "sin_mano"


def test_zona_comoda(rng):
    pts = np.c_[rng.uniform(0.35, 0.65, 150), rng.uniform(0.4, 0.6, 150)]
    z = CAL.calcular_zona(pts)
    x0, y0, x1, y1 = z
    assert x1 - x0 >= 0.30 - 1e-9 and y1 - y0 >= 0.30 - 1e-9
    assert 0 <= x0 < 0.4 and 0.6 < x1 <= 1
    assert CAL.calcular_zona([]) is None
    assert CAL.calcular_zona([(0.5, 0.5)] * 3) is None
    z2 = CAL.calcular_zona(np.c_[rng.uniform(0.0, 0.2, 50), rng.uniform(0.9, 1.0, 50)])
    assert z2[0] >= 0 and z2[3] <= 1


def _medidas(p, s, a, n=40, rng=None, ruido=0.01):
    rng = rng or np.random.default_rng(0)
    return [{"p": p + rng.normal(0, ruido), "s": s + rng.normal(0, ruido * 5), "a": a + rng.normal(0, 1)}
            for _ in range(n)]


def test_umbrales_calibrados():
    m = {"abierta": _medidas(1.2, 1.6, 8), "pellizco": _medidas(0.12, 1.6, 15),
         "juntos": _medidas(0.9, 0.95, 3), "v": _medidas(1.0, 2.6, 28), "puno": _medidas(0.5, 0.9, 4)}
    senas, problemas = CAL.calcular_umbrales(m)
    assert problemas == []
    p = senas["pellizco"]
    assert p["entrar"] < p["salir"]
    assert 0.28 * 0.6 <= p["entrar"] <= 0.28 * 1.4
    j = senas["juntos"]
    assert j["s_entrar"] < j["s_salir"] and j["a_entrar"] < j["a_salir"]
    v = senas["v"]
    assert v["s_entrar"] > v["s_salir"]


def test_calibracion_con_posturas_que_se_traslapan_pide_repetir():
    m = {"abierta": _medidas(0.5, 1.6, 8, ruido=0.2), "pellizco": _medidas(0.45, 1.6, 15, ruido=0.2),
         "juntos": _medidas(0.9, 1.0, 3), "v": _medidas(1.0, 2.6, 28)}
    _, problemas = CAL.calcular_umbrales(m)
    assert ("pellizco", "traslape") in problemas


def test_calibracion_sin_muestras():
    _, problemas = CAL.calcular_umbrales({})
    assert len(problemas) == 4


def test_calibracion_recorta_a_40_por_ciento():
    m = {"abierta": _medidas(5.0, 1.6, 8), "pellizco": _medidas(3.0, 1.6, 15)}
    senas, _ = CAL.calcular_umbrales(m)
    assert senas["pellizco"]["entrar"] == pytest.approx(0.28 * 1.4, abs=1e-3)
