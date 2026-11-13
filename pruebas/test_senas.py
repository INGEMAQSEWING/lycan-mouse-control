"""11.2: clasificador de señas con manos sintéticas (distancia, rotación, izquierda/derecha y ruido)."""
import collections

import numpy as np
import pytest

from lycan_mouse_control import sintetico as s
from lycan_mouse_control.senas import (UMBRALES_FABRICA, Clasificador, Sena, clasificar_una, construir_umbrales,
                                       recortar_calibrado)

U_VAR = construir_umbrales(una_mano_zoom=True)
U = construir_umbrales()
CUADROS = 6   # cada variación se sostiene 6 cuadros (0.2 s) con ruido independiente, como con la cámara


def tasa(postura, esperado, ruido_mm, n=200, umbrales=U_VAR, semilla=1234):
    rng = np.random.default_rng(semilla)
    cuenta = collections.Counter()
    for _ in range(n):
        v = s.variacion_aleatoria(rng, ruido_mm=ruido_mm)
        c = Clasificador(umbrales)
        r = None
        for _f in range(CUADROS):
            m = s.mano(postura, variacion=v, rng=rng)
            r = c.clasificar(m.mundo, m.etiqueta)
        cuenta[r] += 1
    return cuenta[Sena(esperado)] / n, cuenta


@pytest.mark.parametrize("postura,esperado", sorted(s.SENA_ESPERADA.items()))
def test_postura_exacta_un_cuadro(postura, esperado):
    for lado in ("Right", "Left"):
        m = s.mano(postura, lado=lado)
        assert clasificar_una(m.mundo, U_VAR) == Sena(esperado), lado


@pytest.mark.parametrize("postura,esperado", sorted(s.SENA_ESPERADA.items()))
def test_postura_200_variaciones_ruido_2mm(postura, esperado):
    r, cuenta = tasa(postura, esperado, 2.0)
    assert r >= 0.98, cuenta


@pytest.mark.parametrize("postura,esperado", sorted(s.SENA_ESPERADA.items()))
def test_postura_200_variaciones_ruido_4mm(postura, esperado):
    r, cuenta = tasa(postura, esperado, 4.0)
    assert r >= 0.90, cuenta


@pytest.mark.parametrize("postura,esperado", sorted(s.SENA_ESPERADA.items()))
def test_postura_ruido_1mm_un_solo_cuadro(postura, esperado):
    rng = np.random.default_rng(7)
    ok = 0
    for _ in range(100):
        v = s.variacion_aleatoria(rng, ruido_mm=1.0)
        m = s.mano(postura, variacion=v, rng=rng)
        ok += clasificar_una(m.mundo, U_VAR) == Sena(esperado)
    assert ok >= 95


@pytest.mark.parametrize("ruido", [0.0, 1.0, 2.0])
def test_juntos_contra_v_cero_confusiones(ruido):
    rng = np.random.default_rng(99)
    for _ in range(200):
        v = s.variacion_aleatoria(rng, ruido_mm=ruido)
        cj, cv = Clasificador(U), Clasificador(U)
        for _f in range(CUADROS):
            rj = cj.clasificar(s.mano("juntos", variacion=v, rng=rng).mundo)
            rv = cv.clasificar(s.mano("v", variacion=v, rng=rng).mundo)
        assert rj != Sena.V
        assert rv != Sena.ACTIVAR


def test_puno_nunca_es_pellizco_1000_variaciones():
    rng = np.random.default_rng(2024)
    for _ in range(1000):
        v = s.variacion_aleatoria(rng, ruido_mm=2.0)
        m = s.mano("puno", variacion=v, rng=rng)
        assert Clasificador(U).clasificar(m.mundo) != Sena.PELLIZCO


@pytest.mark.parametrize("lado", ["Right", "Left"])
def test_transicion_abierta_a_puno_sin_pellizco_sostenido(lado):
    """Interpolada en 10 pasos a 30 cuadros/s: nunca PELLIZCO 2 cuadros seguidos (66 ms)."""
    c = Clasificador(U)
    seguidos = 0
    maximo = 0
    pasos = [s.intermedia("abierta", "puno", k / 9) for k in range(10)] + [s.construir("puno")] * 5
    for P in pasos:
        m = s.mano(P, lado=lado)
        r = c.clasificar(m.mundo)
        seguidos = seguidos + 1 if r == Sena.PELLIZCO else 0
        maximo = max(maximo, seguidos)
    assert maximo < 2
    assert r == Sena.PUNO


def test_transicion_abierta_a_puno_con_ruido_y_rotaciones():
    rng = np.random.default_rng(5)
    for _ in range(50):
        v = s.variacion_aleatoria(rng, ruido_mm=2.0)
        c = Clasificador(U)
        seguidos = maximo = 0
        for k in range(10):
            r = c.clasificar(s.mano(s.intermedia("abierta", "puno", k / 9), variacion=v, rng=rng).mundo)
            seguidos = seguidos + 1 if r == Sena.PELLIZCO else 0
            maximo = max(maximo, seguidos)
        assert maximo < 2


def _mano_con_p(p_objetivo):
    """Postura de pellizco con el pulgar a la distancia p_objetivo (en palmas) de la punta del índice."""
    from lycan_mouse_control import geometria as g
    P = s.construir("pellizco")
    palma = g.escala_palma(P)
    d = P[4] - P[8]
    d = d / np.linalg.norm(d)
    P[4] = P[8] + d * p_objetivo * palma
    return P


@pytest.mark.parametrize("inicio", [0.6, 0.1])
def test_pellizco_en_el_borde_histeresis_un_cambio(inicio):
    """p oscila entre 0.27 y 0.43 con ruido: como máximo 1 cambio de estado."""
    rng = np.random.default_rng(3)
    c = Clasificador(U)
    for _ in range(6):
        c.clasificar(s.mano(_mano_con_p(inicio)).mundo)
    prev = c.sena == Sena.PELLIZCO
    cambios = 0
    for p in rng.uniform(0.27, 0.43, 90):
        r = c.clasificar(s.mano(_mano_con_p(p), ruido_mm=0.5, rng=rng).mundo) == Sena.PELLIZCO
        cambios += r != prev
        prev = r
    assert cambios <= 1


def test_pellizco_sale_al_abrir():
    c = Clasificador(U)
    for p in [0.1] * 4:
        assert c.clasificar(s.mano(_mano_con_p(p)).mundo) == Sena.PELLIZCO
    for p in [0.7] * 4:
        r = c.clasificar(s.mano(_mano_con_p(p)).mundo)
    assert r != Sena.PELLIZCO


@pytest.mark.parametrize("postura", ["abierta", "puno", "pellizco", "juntos", "v", "apuntar"])
def test_cerca_y_lejos_mismo_resultado(postura):
    a = clasificar_una(s.mano(postura, distancia_m=0.3).mundo, U)
    b = clasificar_una(s.mano(postura, distancia_m=0.9).mundo, U)
    assert a == b


@pytest.mark.parametrize("w", [
    np.full((21, 3), np.nan), np.zeros((21, 3)), np.ones((21, 3)) * 0.1, np.zeros((5, 3)),
    np.full((21, 3), np.inf), "nada", None,
])
def test_datos_raros_devuelven_ninguna(w):
    c = Clasificador(U)
    assert c.clasificar(w) == Sena.NINGUNA


def test_un_punto_nan_en_medio_de_una_secuencia():
    c = Clasificador(U)
    for _ in range(3):
        c.clasificar(s.construir("puno"))
    malo = s.construir("puno")
    malo[8] = np.nan
    assert c.clasificar(malo) == Sena.NINGUNA
    assert c.clasificar(s.construir("puno")) == Sena.PUNO


def test_umbrales_calibrados_se_recortan_a_40_por_ciento():
    u = construir_umbrales({"pellizco": {"entrar": 5.0, "salir": 9.0}, "juntos": {"s_entrar": 0.01}})
    assert u["pellizco"]["entrar"] == pytest.approx(0.28 * 1.4)
    assert u["pellizco"]["salir"] == pytest.approx(0.42 * 1.4)
    assert u["juntos"]["s_entrar"] == pytest.approx(1.25 * 0.6)
    assert recortar_calibrado(float("nan"), 0.28) == 0.28
    assert recortar_calibrado("x", 0.28) == 0.28


def test_umbrales_incoherentes_vuelven_a_fabrica():
    u = construir_umbrales({"pellizco": {"entrar": 0.39, "salir": 0.30}})
    assert u["pellizco"] == UMBRALES_FABRICA["pellizco"]


def test_pellizco_corazon_solo_con_la_variante():
    m = s.mano("pellizco_corazon").mundo
    assert clasificar_una(m, construir_umbrales(una_mano_zoom=False)) != Sena.PELLIZCO_CORAZON
    assert clasificar_una(m, construir_umbrales(una_mano_zoom=True)) == Sena.PELLIZCO_CORAZON


def test_dedo_faltante_no_rompe(rng):
    for postura in s.SENA_ESPERADA:
        m = s.mano(postura, faltante=True, rng=rng)
        r = Clasificador(U).clasificar(m.mundo)
        assert isinstance(r, Sena)


def test_medidas_quedan_disponibles():
    c = Clasificador(U)
    c.clasificar(s.construir("pellizco"))
    d = c.medidas.como_dict()
    assert d["p"] < 0.28 and "indice" in d["doblez"]


def test_puno_tres_dedos_extendidos_cuenta_abrir():
    c = Clasificador(U)
    for _ in range(4):
        c.clasificar(s.construir("abierta"))
    assert c.medidas.extendidos >= 3
    c2 = Clasificador(U)
    for _ in range(4):
        c2.clasificar(s.construir("puno"))
    assert c2.medidas.extendidos < 3
