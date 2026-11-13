"""11.2: medidas puras de la mano."""
import math

import numpy as np
import pytest

from lycan_mouse_control import geometria as g
from lycan_mouse_control import sintetico as s


def test_ang_valores_conocidos():
    assert g.ang((1, 0, 0), (1, 0, 0)) == pytest.approx(0, abs=0.01)
    assert g.ang((1, 0, 0), (0, 1, 0)) == pytest.approx(90)
    assert g.ang((1, 0, 0), (-1, 0, 0)) == pytest.approx(180)
    assert g.ang((1, 0, 0), (1, 1, 0)) == pytest.approx(45)


def test_ang_vector_cero_no_rompe():
    v = g.ang((0, 0, 0), (1, 0, 0))
    assert math.isnan(v) or 0 <= v <= 180


@pytest.mark.parametrize("dist", [0.3, 0.5, 0.9])
def test_escala_palma_igual_a_cualquier_distancia(dist):
    ref = g.escala_palma(s.mano("abierta", distancia_m=0.5).mundo)
    m = s.mano("abierta", distancia_m=dist)
    assert abs(g.escala_palma(m.mundo) - ref) / ref < 0.02
    assert 0.07 < ref < 0.10   # típico 0.075-0.095 m


def test_escala_palma_en_imagen_si_cambia_con_la_distancia():
    cerca = s.mano("abierta", distancia_m=0.3).img
    lejos = s.mano("abierta", distancia_m=0.9).img
    assert g.escala_palma(cerca[:, :2].tolist() and np.c_[cerca[:, :2], np.zeros(21)]) > \
        2 * g.escala_palma(np.c_[lejos[:, :2], np.zeros(21)])


def test_doblez_recto_y_cerrado_bajo_200_rotaciones(rng):
    for _ in range(200):
        rot = tuple(rng.uniform(-40, 40, 3))
        ab = s.mano("abierta", rot=rot).mundo
        pu = s.mano("puno", rot=rot).mundo
        for dedo in ("indice", "corazon", "anular", "menique"):
            assert g.doblez(ab, dedo) < 40
            assert g.doblez(pu, dedo) > 150


def test_pellizco_y_separaciones():
    pel = s.mano("pellizco").mundo
    ab = s.mano("abierta").mundo
    assert g.pellizco(pel) < 0.2
    assert g.pellizco(ab) > 0.8
    assert g.separacion_ic(s.mano("juntos").mundo) < 1.25
    assert g.separacion_ic(s.mano("v").mundo) > 1.9
    assert g.angulo_ic(s.mano("juntos").mundo) < 10
    assert g.angulo_ic(s.mano("v").mundo) > 20
    assert g.pellizco_corazon(s.mano("pellizco_corazon").mundo) < 0.2


def test_pulgar_recogido_y_punta_cerca():
    pu = s.mano("puno").mundo
    assert g.punta_cerca_palma(pu, 12) < 0.55
    assert g.punta_cerca_palma(s.mano("abierta").mundo, 12) > 1.0
    assert isinstance(g.pulgar_recogido(pu), bool)


def test_razon_dedo():
    assert g.razon_dedo(s.mano("abierta").mundo, "indice") > 1.2
    assert g.razon_dedo(s.mano("puno").mundo, "indice") < 1.0


def test_centro_y_normal():
    w = s.construir("abierta")
    c = g.centro_palma(w)
    assert c.shape == (3,)
    n = g.normal_palma(w)
    assert np.linalg.norm(n) > 0


@pytest.mark.parametrize("w", [
    np.full((21, 3), np.nan),
    np.zeros((21, 3)),
    np.ones((21, 3)),
    np.zeros((20, 3)),
    "texto",
    None,
])
def test_puntos_validos_detecta_datos_raros(w):
    assert g.puntos_validos(w) is False


def test_puntos_validos_mano_buena():
    assert g.puntos_validos(s.construir("abierta"))


def test_doblez_por_indices_o_nombre():
    w = s.construir("puno")
    assert g.doblez(w, "indice") == pytest.approx(g.doblez(w, (5, 6, 7, 8)))
