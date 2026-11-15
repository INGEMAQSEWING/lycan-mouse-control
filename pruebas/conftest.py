"""Ayudas comunes: simulador de secuencias (núcleo + perfiles + salida simulada) y manos."""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from lycan_mouse_control import constantes as K  # noqa: E402
from lycan_mouse_control import perfiles  # noqa: E402
from lycan_mouse_control.acciones import Bajar, Clic, Mover, MoverDelta, Rueda, SoltarTodo, Subir, Tecla  # noqa: E402,F401
from lycan_mouse_control.config import por_defecto  # noqa: E402
from lycan_mouse_control.mapeo import Mapeo, Monitor  # noqa: E402
from lycan_mouse_control.nucleo import Nucleo  # noqa: E402
from lycan_mouse_control.salida.simulada import SalidaSimulada  # noqa: E402
from lycan_mouse_control.sintetico import mano  # noqa: E402


def mezclar(base: dict, extra: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = mezclar(out[k], v)
        else:
            out[k] = v
    return out


def M(postura="apuntar", pos=(0.5, 0.5), lado="Right", **kw):
    """Una mano sintética en la imagen (pos = dónde cae la punta del índice por defecto)."""
    return mano(postura, posicion=pos, lado=lado, **kw)


class Sim:
    """Pasa cuadros sintéticos por Nucleo + Traductor + SalidaSimulada con un reloj propio."""

    def __init__(self, modo="2D", perfil="generico", fps=30.0, cfg=None, monitor=None, t0=100.0):
        self.cfg = mezclar(por_defecto(), cfg)
        self.cfg["modo"] = modo
        self.t = float(t0)
        self.dt = 1.0 / fps
        mon = monitor or Monitor(0, 0, 1366, 768)
        self.salida = SalidaSimulada(escritorio=(mon.x, mon.y, mon.ancho, mon.alto),
                                     cursor=(mon.x + mon.ancho // 2, mon.y + mon.alto // 2),
                                     reloj=lambda: self.t)
        z = self.cfg["zona"]
        self.mapeo = Mapeo((z["x0"], z["y0"], z["x1"], z["y1"]), mon)
        self.nucleo = Nucleo(self.cfg, perfiles.obtener(perfil), self.mapeo,
                             pos_cursor=self.salida.posicion_cursor)
        self.acciones: list = []
        self.resultados: list = []

    # ---- reloj ----
    def poner_fps(self, fps):
        self.dt = 1.0 / fps

    def cuadro(self, manos):
        if manos is None:
            manos = []
        elif not isinstance(manos, (list, tuple)):
            manos = [manos]
        r = self.nucleo.procesar(self.t, list(manos))
        self._aplicar(r.acciones)
        self.resultados.append((self.t, r))
        self.t += self.dt
        return r

    def _aplicar(self, acciones):
        for a in acciones:
            self.acciones.append((self.t, a))
        self.salida.aplicar(acciones)

    def orden(self, acciones):
        """Aplica acciones devueltas por una orden externa (atajo, cambio de modo...)."""
        self._aplicar(acciones)
        return acciones

    def durante(self, ms, manos):
        """Repite cuadros durante ``ms``; ``manos`` puede ser función f(fracción 0..1)."""
        n = max(1, int(round(ms / 1000.0 / self.dt)))
        r = None
        for i in range(n):
            m = manos(i / max(n - 1, 1)) if callable(manos) else manos
            r = self.cuadro(m)
        return r

    # ---- consultas ----
    @property
    def estado(self):
        return self.nucleo.estado

    @property
    def base(self):
        return self.nucleo.maquina.base

    def de_tipo(self, *tipos):
        return [a for _, a in self.acciones if isinstance(a, tipos)]

    def desde(self, t0):
        return [a for t, a in self.acciones if t >= t0]

    def eventos(self, tipo=None):
        return [ev for _, ev in self.salida.eventos if tipo is None or ev[0] == tipo]

    def botones(self):
        return self.salida.botones()

    # ---- secuencias comunes ----
    def activar(self, pos=(0.5, 0.5), lado="Right"):
        """En pausa: seña de activar 400 ms + mano apuntando 900 ms (pasa la ventana de ignorar)."""
        self.durante(400, M("juntos", pos, lado))
        self.durante(900, M("apuntar", pos, lado))
        assert self.base == K.ACTIVO, self.base

    def invariantes(self, final=True):
        verificar_invariantes(self.salida, final)


def verificar_invariantes(salida: SalidaSimulada, final=True):
    """Invariantes de seguridad sobre los eventos enviados."""
    abajo_b, abajo_k = set(), set()
    for _, ev in salida.eventos:
        if ev[0] == "boton":
            if ev[2]:
                assert ev[1] not in abajo_b, f"dos 'bajar' seguidos del botón {ev[1]}"
                abajo_b.add(ev[1])
            else:
                abajo_b.discard(ev[1])
        elif ev[0] == "tecla":
            if ev[2]:
                abajo_k.add(ev[1])
            else:
                if ev[1] == "shift":
                    assert "medio" not in abajo_b, "Shift subió antes que el botón del medio"
                abajo_k.discard(ev[1])
        elif ev[0] == "rueda":
            assert not (abajo_k & {"shift", "ctrl"}), "rueda con Shift/Ctrl abajo"
        elif ev[0] == "pulsar":
            # 1.0.2 paquete A: ninguna tecla sale con botones (o teclas de un gesto) abajo
            assert not abajo_b, f"tecla {ev[1]} con botones abajo: {abajo_b}"
            assert not abajo_k, f"tecla {ev[1]} con teclas abajo: {abajo_k}"
    assert not salida.violaciones, salida.violaciones
    if final:
        assert not abajo_b, f"quedaron botones abajo: {abajo_b}"
        assert not abajo_k, f"quedaron teclas abajo: {abajo_k}"
        assert salida.todo_suelto()


@pytest.fixture
def sim():
    return Sim()


@pytest.fixture(autouse=True)
def _datos_temporales(tmp_path, monkeypatch):
    """Ninguna prueba toca la configuración real del usuario."""
    monkeypatch.setenv("LYCAN_MOUSE_DATOS", str(tmp_path / "datos"))
    yield


@pytest.fixture
def rng():
    return np.random.default_rng(1234)
