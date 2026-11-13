"""Mapeo zona -> pantalla y seguidor de manos (identidad, etiqueta por votos, mano principal)."""
import numpy as np
import pytest

from lycan_mouse_control import sintetico as s
from lycan_mouse_control.mapeo import Mapeo, Monitor
from lycan_mouse_control.seguidor import Seguidor
from lycan_mouse_control.senas import Sena


def test_zona_de_fabrica_coincide_con_la_especificacion():
    m = Mapeo((0.20, 0.25, 0.80, 0.70), Monitor(0, 0, 1366, 768))
    x0, y0, x1, y1 = m.zona
    assert (x0, x1) == (0.2, 0.8)
    assert y1 - y0 == pytest.approx(0.45, abs=0.002)


def test_mapeo_esquinas_y_recorte():
    m = Mapeo((0.2, 0.25, 0.8, 0.7), Monitor(0, 0, 1366, 768))
    x0, y0, x1, y1 = m.zona
    assert m.a_pantalla(x0, y0) == (0, 0)
    assert m.a_pantalla(x1, y1) == pytest.approx((1365, 767))
    assert m.a_pantalla(-1, -1) == (0, 0)
    assert m.a_pantalla(5, 5) == pytest.approx((1365, 767))


def test_mapeo_monitor_con_origen_negativo():
    m = Mapeo((0.2, 0.25, 0.8, 0.7), Monitor(-1920, 0, 1920, 1080))
    assert m.a_pantalla(0, 0)[0] == -1920
    assert m.a_pantalla(1, 1)[0] == pytest.approx(-1)


def test_mapeo_alto_minimo_30_por_ciento():
    m = Mapeo((0.4, 0.4, 0.6, 0.6), Monitor(0, 0, 3840, 1080))
    assert m.y1 - m.y0 >= 0.30 - 1e-9


def test_mapeo_un_circulo_sale_circulo():
    m = Mapeo((0.2, 0.25, 0.8, 0.7), Monitor(0, 0, 1366, 768))
    w_cam = (m.x1 - m.x0) * 640
    h_cam = (m.y1 - m.y0) * 480
    assert w_cam / h_cam == pytest.approx(1366 / 768, rel=0.01)


def test_mapeo_zona_invalida_vuelve_a_fabrica():
    m = Mapeo((0.5, 0.5, 0.51, 0.5))
    assert m.x1 - m.x0 > 0.3


def test_cerca_del_borde():
    m = Mapeo()
    assert m.cerca_del_borde(m.x0 + 0.01, 0.5)
    assert not m.cerca_del_borde(0.5, (m.y0 + m.y1) / 2)


def test_seguidor_identidad_estable_al_cambiar_el_orden():
    seg = Seguidor()
    a = s.mano("abierta", posicion=(0.3, 0.5), lado="Left")
    b = s.mano("abierta", posicion=(0.7, 0.5), lado="Right")
    seg.actualizar(0.0, [a, b])
    ids = {round(p.img[9, 0], 2): p.id for p in seg.pistas}
    seg.actualizar(0.033, [b, a])          # MediaPipe cambió el orden
    ids2 = {round(p.img[9, 0], 2): p.id for p in seg.pistas}
    assert ids == ids2


def test_seguidor_etiqueta_por_mayoria():
    seg = Seguidor()
    for k in range(15):
        lado = "Right" if k != 7 else "Left"        # un cuadro con la etiqueta equivocada
        seg.actualizar(k / 30, [s.mano("abierta", lado=lado)])
    assert seg.pistas[0].etiqueta == "Right"


def test_seguidor_conserva_150ms_y_predice():
    seg = Seguidor()
    for k in range(10):
        seg.actualizar(k / 30, [s.mano("abierta", posicion=(0.4 + 0.01 * k, 0.5))])
    t = 9 / 30
    seg.actualizar(t + 0.05, [])
    assert len(seg.pistas) == 1 and not seg.pistas[0].detectada
    seg.actualizar(t + 0.14, [])
    assert len(seg.pistas) == 1
    seg.actualizar(t + 0.16, [])
    assert seg.pistas == []


def test_seguidor_mano_principal_derecha_o_izquierda():
    for principal, esperado in (("derecha", "Right"), ("izquierda", "Left")):
        seg = Seguidor(mano_principal=principal)
        a = s.mano("abierta", posicion=(0.3, 0.5), lado="Left")
        b = s.mano("abierta", posicion=(0.7, 0.5), lado="Right")
        seg.actualizar(0.0, [a, b])
        assert seg.principal.etiqueta == esperado


def test_seguidor_una_sola_mano_es_la_principal_aunque_sea_la_otra():
    seg = Seguidor(mano_principal="derecha")
    seg.actualizar(0.0, [s.mano("apuntar", lado="Left")])
    assert seg.principal is not None


def test_seguidor_salto_sospechoso():
    seg = Seguidor()
    seg.actualizar(0.0, [s.mano("abierta", posicion=(0.4, 0.5))])
    seg.actualizar(0.033, [s.mano("abierta", posicion=(0.58, 0.5))])
    assert seg.pistas[0].sospechosa


def test_seguidor_clasifica_cada_mano():
    seg = Seguidor()
    for k in range(5):
        seg.actualizar(k / 30, [s.mano("puno", posicion=(0.3, 0.5), lado="Left"),
                                s.mano("pellizco", posicion=(0.7, 0.5), lado="Right")])
    senas = {p.etiqueta: p.sena for p in seg.pistas}
    assert senas == {"Left": Sena.PUNO, "Right": Sena.PELLIZCO}
    assert [p.etiqueta for p in seg.por_x()] == ["Left", "Right"]


def test_seguidor_ignora_manos_con_nan():
    seg = Seguidor()
    m = s.mano("abierta")
    m.img[:] = np.nan
    seg.actualizar(0.0, [m])
    assert seg.pistas == []
