"""11.5: salida de ratón (sin mover el ratón real): fórmula de coordenadas, estructuras INPUT,
soltar todo, botones invertidos, fallos de SendInput y salida simulada."""
import ctypes
import threading

import pytest

from lycan_mouse_control.acciones import (Bajar, Clic, Esperar, Mover, MoverDelta, Rueda, SoltarTodo, Subir,
                                          Tecla)
from lycan_mouse_control.salida import ErrorEnvio, crear
from lycan_mouse_control.salida import windows as W
from lycan_mouse_control.salida.simulada import SalidaSimulada


@pytest.mark.parametrize("vx,vw", [(0, 1366), (0, 1920), (0, 2560), (0, 3840), (-1920, 3840), (-1366, 1366 * 2)])
def test_formula_de_coordenadas_sin_errores(vx, vw):
    for x in range(vx, vx + vw):
        nx, _ = W.a_absoluto(x, 0, vx, 0, vw, 768)
        assert 0 <= nx <= 65535
        assert vx + (nx * vw) // 65536 == x


def test_formula_vertical_y_redondeo_normal_falla():
    vh = 768
    for y in range(vh):
        _, ny = W.a_absoluto(0, y, 0, 0, 1366, vh)
        assert (ny * vh) // 65536 == y
    malos = sum(1 for x in range(1366) if ((x * 65536 + 683) // 1366 * 1366) // 65536 != x)
    assert malos > 0     # por eso la fórmula con +w/2 está prohibida


def test_estructura_input_de_40_bytes():
    assert ctypes.sizeof(W.INPUT) == 40


class SalidaWindowsSinEnviar(W.SalidaWindows):
    """Construye los INPUT pero no llama a SendInput."""

    def __init__(self, escritorio=(0, 0, 1366, 768), invertidos=False):
        super(W.SalidaWindows, self).__init__()
        self.escritorio = escritorio
        self.invertidos = invertidos
        self.lotes = []
        self.cursor = (100, 100)
        self.falla = False

    def posicion_cursor(self):
        return self.cursor

    def _enviar(self, eventos):
        ins = self.construir(eventos)
        if self.falla:
            raise ErrorEnvio(5, "bloqueado")
        self.lotes.append(ins)
        return len(ins)


def test_construir_banderas_correctas():
    s = SalidaWindowsSinEnviar()
    s.aplicar([Mover(683, 384), Bajar("izq"), Subir("izq"), Clic("der"), Bajar("medio"), Subir("medio"),
               Rueda(120), Rueda(-240), Tecla("shift", True), Tecla("shift", False)])
    planos = [i for lote in s.lotes for i in lote]
    m = planos[0]
    assert m.type == 0 and m.mi.dwFlags == 0x0001 | 0x8000 | 0x4000
    assert m.mi.dwExtraInfo == 0x4C59434E
    assert [p.mi.dwFlags for p in planos[1:7]] == [0x02, 0x04, 0x08, 0x10, 0x20, 0x40]
    assert planos[7].mi.dwFlags == 0x0800 and planos[7].mi.mouseData == 120
    assert ctypes.c_int32(planos[8].mi.mouseData).value == -240
    assert planos[9].type == 1 and planos[9].ki.wVk == 0xA0 and planos[9].ki.dwFlags == 0
    assert planos[10].ki.dwFlags == 0x0002
    # el clic va en UNA sola llamada (down + up)
    assert any(len(l) == 2 and l[0].mi.dwFlags == 0x08 and l[1].mi.dwFlags == 0x10 for l in s.lotes)


def test_botones_invertidos_para_zurdos():
    s = SalidaWindowsSinEnviar(invertidos=True)
    s.aplicar([Clic("izq")])
    assert s.lotes[0][0].mi.dwFlags == 0x08     # el "izquierdo" lógico es el derecho físico


def test_soltar_todo_en_una_llamada_botones_primero():
    s = SalidaWindowsSinEnviar()
    s.aplicar([Tecla("shift", True), Bajar("medio"), Bajar("izq")])
    n = len(s.lotes)
    s.soltar_todo("prueba")
    assert len(s.lotes) == n + 1
    lote = s.lotes[-1]
    tipos = [i.type for i in lote]
    assert tipos == sorted(tipos)              # primero ratón (0) y después teclado (1)
    assert {i.mi.dwFlags for i in lote if i.type == 0} == {0x04, 0x40}
    assert {i.ki.wVk for i in lote if i.type == 1} == {0xA0, 0xA2, 0xA4}
    assert s.todo_suelto()


def test_bajar_dos_veces_no_envia_dos_down():
    s = SalidaSimulada()
    s.aplicar([Bajar("izq"), Bajar("izq"), Subir("izq"), Subir("izq")])
    assert s.botones() == [("izq", True), ("izq", False)]


def test_mover_delta_usa_la_posicion_actual_y_se_limita_al_escritorio():
    s = SalidaSimulada(escritorio=(0, 0, 1366, 768), cursor=(1360, 10))
    s.aplicar([MoverDelta(50, -50)])
    assert s.cursor == (1365, 0)


def test_soltar_todo_en_todos_los_estados():
    for previas in ([], [Bajar("izq")], [Bajar("medio"), Tecla("shift", True)],
                    [Tecla("ctrl", True)], [Bajar("der"), Bajar("izq"), Bajar("medio")]):
        s = SalidaSimulada()
        s.aplicar(previas)
        s.aplicar([SoltarTodo("prueba")])
        assert s.todo_suelto()
        s.soltar_todo("otra vez")              # soltar de más no hace daño
        assert s.todo_suelto()


def test_soltar_todo_seguro_desde_otro_hilo():
    s = SalidaSimulada()
    s.aplicar([Bajar("medio"), Tecla("shift", True)])
    h = threading.Thread(target=s.soltar_todo, args=("hilo",))
    h.start()
    h.join()
    assert s.todo_suelto()


def test_fallo_de_sendinput_lanza_error_y_soltar_no_rompe():
    s = SalidaSimulada()
    s.aplicar([Bajar("izq")])
    s.fallar = True
    with pytest.raises(ErrorEnvio):
        s.aplicar([Mover(1, 1)])
    s.soltar_todo("falla")                      # nunca lanza
    assert s.todo_suelto()
    assert s.probar() is False
    s.fallar = False
    assert s.probar() is True


def test_esperar_no_bloquea_en_la_simulada():
    s = SalidaSimulada()
    s.aplicar([Esperar(20)])
    assert s.eventos[-1][1] == ("esperar", 20)


def test_crear_simulada():
    assert isinstance(crear(True), SalidaSimulada)


def test_salida_windows_real_se_construye_sin_enviar():
    s = W.SalidaWindows()
    vx, vy, vw, vh = s.escritorio
    assert vw > 0 and vh > 0
    x, y = s.posicion_cursor()
    assert isinstance(x, int)
