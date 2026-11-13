"""Filtros puros: histéresis, antirrebote (en milisegundos reales), promedio exponencial y One Euro.

Todos los tiempos se pasan en SEGUNDOS medidos con time.perf_counter() (o el t_captura
del cuadro). Nunca se cuentan cuadros: así se comportan igual a 15 o a 30 cuadros/s.
"""
from __future__ import annotations

import math


class Histeresis:
    """Estado booleano que solo cambia al cruzar el umbral contrario.

    menor_es_dentro=True: entra cuando valor < entrar y sale cuando valor > salir.
    menor_es_dentro=False: entra cuando valor > entrar y sale cuando valor < salir.
    Un valor NaN conserva el estado.
    """

    def __init__(self, entrar: float, salir: float, menor_es_dentro: bool = True, inicial: bool = False):
        self.entrar = float(entrar)
        self.salir = float(salir)
        self.menor = menor_es_dentro
        self.dentro = inicial

    def actualizar(self, valor: float) -> bool:
        if valor is None or not math.isfinite(valor):
            return self.dentro
        if self.menor:
            if not self.dentro and valor < self.entrar:
                self.dentro = True
            elif self.dentro and valor > self.salir:
                self.dentro = False
        else:
            if not self.dentro and valor > self.entrar:
                self.dentro = True
            elif self.dentro and valor < self.salir:
                self.dentro = False
        return self.dentro

    def reiniciar(self, estado: bool = False):
        self.dentro = estado


class Antirrebote:
    """Confirma un cambio solo cuando el valor crudo se mantiene ms_entrar (o ms_salir)."""

    def __init__(self, ms_entrar: float, ms_salir: float, inicial: bool = False):
        self.s_entrar = ms_entrar / 1000.0
        self.s_salir = ms_salir / 1000.0
        self.estado = inicial
        self._desde = None   # momento en que el crudo empezó a diferir del estado
        self.t_cambio = None  # momento del último cambio confirmado
        self.t_inicio_crudo = None  # cuando empezó el crudo que llevó al estado actual

    def actualizar(self, crudo: bool, t: float) -> bool:
        crudo = bool(crudo)
        if crudo == self.estado:
            self._desde = None
            return self.estado
        if self._desde is None:
            self._desde = t
        espera = self.s_entrar if crudo else self.s_salir
        if t - self._desde >= espera - 1e-9:
            self.estado = crudo
            self.t_cambio = t
            self.t_inicio_crudo = self._desde
            self._desde = None
        return self.estado

    @property
    def pendiente_desde(self):
        return self._desde

    def reiniciar(self, estado: bool = False):
        self.estado = estado
        self._desde = None
        self.t_cambio = None
        self.t_inicio_crudo = None


class PromedioExp:
    def __init__(self, alfa: float = 0.5):
        self.alfa = float(alfa)
        self.valor = None

    def actualizar(self, x: float) -> float:
        if x is None or not math.isfinite(x):
            return self.valor if self.valor is not None else float("nan")
        if self.valor is None or not math.isfinite(self.valor):
            self.valor = float(x)
        else:
            self.valor = self.alfa * float(x) + (1.0 - self.alfa) * self.valor
        return self.valor

    def reiniciar(self):
        self.valor = None


def _alfa(cutoff: float, dt: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuro:
    """Filtro 1€ (Casiez 2012): poco temblor quieto y poco retraso en movimiento.

    cutoff = mincutoff + beta·|derivada filtrada|; alfa = 1/(1 + tau/dt); tau = 1/(2π·cutoff).
    dt sale del tiempo real de cada cuadro.
    """

    def __init__(self, mincutoff: float = 0.5, beta: float = 0.015, dcutoff: float = 1.0):
        self.mincutoff = float(mincutoff)
        self.beta = float(beta)
        self.dcutoff = float(dcutoff)
        self.reset()

    def reset(self):
        self._x = None
        self._crudo = None
        self._dx = 0.0
        self._t = None

    @property
    def valor(self):
        return self._x

    def __call__(self, x: float, t: float) -> float:
        return self.filtrar(x, t)

    def filtrar(self, x: float, t: float) -> float:
        x = float(x)
        if not math.isfinite(x):
            return self._x if self._x is not None else x
        if self._x is None or self._t is None:
            self._x, self._crudo, self._dx, self._t = x, x, 0.0, t
            return x
        dt = t - self._t
        if dt <= 0:
            dt = 1e-3
        dt = min(dt, 0.5)  # tras una pausa larga no se acumula un salto enorme
        self._t = t
        dx = (x - self._crudo) / dt
        self._crudo = x
        self._dx = self._dx + _alfa(self.dcutoff, dt) * (dx - self._dx)
        cutoff = self.mincutoff + self.beta * abs(self._dx)
        self._x = self._x + _alfa(cutoff, dt) * (x - self._x)
        return self._x
