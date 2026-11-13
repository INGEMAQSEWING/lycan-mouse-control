"""Velocidad del puntero y del giro 3D (versión 1.0.1)."""
import copy

import pytest

from lycan_mouse_control.config import FABRICA, validar
from lycan_mouse_control.ui.opciones import (poner_velocidad_giro, poner_velocidad_puntero,
                                             velocidad_de_giro, velocidad_de_zona)


def _cfg():
    return copy.deepcopy(FABRICA)


@pytest.mark.parametrize("vel", range(1, 11))
def test_ida_y_vuelta_y_dentro_de_la_imagen(vel):
    c = _cfg()
    poner_velocidad_puntero(c, vel)
    z = c["zona"]
    assert 0.0 <= z["x0"] < z["x1"] <= 1.0 and 0.0 <= z["y0"] < z["y1"] <= 1.0
    assert velocidad_de_zona(z) == vel
    assert validar(c)["zona"] == z          # la configuración la acepta tal cual


def test_mas_lento_es_zona_mas_grande_y_menos_ganancia():
    lento, rapido = _cfg(), _cfg()
    poner_velocidad_puntero(lento, 1)
    poner_velocidad_puntero(rapido, 10)
    ancho = lambda c: c["zona"]["x1"] - c["zona"]["x0"]  # noqa: E731
    assert ancho(lento) > ancho(rapido)
    assert lento["puntero"]["relativo"]["gmax"] < rapido["puntero"]["relativo"]["gmax"]


def test_conserva_el_centro_de_la_calibracion_y_no_se_sale():
    c = _cfg()
    c["zona"].update({"x0": 0.0, "x1": 0.3, "y0": 0.6, "y1": 0.9})   # pegada a un borde
    poner_velocidad_puntero(c, 1)
    z = c["zona"]
    assert z["x0"] == 0.0 and z["x1"] <= 1.0 and z["y1"] <= 1.0 and z["y0"] >= 0.0
    c = _cfg()
    poner_velocidad_puntero(c, 8)
    assert (c["zona"]["x0"] + c["zona"]["x1"]) / 2 == pytest.approx(0.5, abs=0.002)


def test_valores_fuera_de_rango_se_limitan():
    c = _cfg()
    poner_velocidad_puntero(c, 99)
    assert velocidad_de_zona(c["zona"]) == 10
    poner_velocidad_puntero(c, -3)
    assert velocidad_de_zona(c["zona"]) == 1


@pytest.mark.parametrize("vel", range(1, 11))
def test_giro_ida_y_vuelta(vel):
    c = _cfg()
    poner_velocidad_giro(c, vel)
    assert velocidad_de_giro(c["orbita"]) == vel
    v = validar(c)["orbita"]
    assert v == c["orbita"]


def test_giro_de_fabrica_queda_en_el_medio():
    assert velocidad_de_giro(FABRICA["orbita"]) == 5
    assert velocidad_de_zona(FABRICA["zona"]) == 6
