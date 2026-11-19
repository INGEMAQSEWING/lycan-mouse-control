"""Acciones que produce la lógica pura y que la salida convierte en eventos de Windows.

La lógica de señas y estados nunca toca Windows: devuelve listas de estas acciones.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mover:
    """Mover el puntero a un píxel absoluto del escritorio virtual."""
    x: int
    y: int


@dataclass(frozen=True)
class MoverDelta:
    """Mover el puntero desde donde esté ahora (GetCursorPos) + (dx, dy). Órbita y desplazar."""
    dx: int
    dy: int


@dataclass(frozen=True)
class Bajar:
    boton: str  # 'izq' | 'der' | 'medio'


@dataclass(frozen=True)
class Subir:
    boton: str


@dataclass(frozen=True)
class Clic:
    """Bajar + subir en una sola llamada (no se intercala con otra entrada).
    veces=2: doble clic, también en una sola llamada (1.0.2)."""
    boton: str
    veces: int = 1


@dataclass(frozen=True)
class Pulsar:
    """1.0.2: una combinación de teclas (por ejemplo ("ctrl", "z")). Se bajan todas en orden y se
    suben al revés en UNA llamada. Nunca sale con botones abajo ni sobre la ventana propia."""
    teclas: tuple


@dataclass(frozen=True)
class Rueda:
    delta: int  # múltiplos de 120 salvo perfiles que admiten fracciones
    horizontal: bool = False  # 1.0.3: rueda de lado (abanico a la izquierda / derecha)


@dataclass(frozen=True)
class Tecla:
    tecla: str   # 'shift' | 'ctrl' | 'alt'
    abajo: bool


@dataclass(frozen=True)
class Esperar:
    ms: int


@dataclass(frozen=True)
class SoltarTodo:
    motivo: str = ""


@dataclass(frozen=True)
class Aviso:
    """Mensaje para la interfaz (no llega a Windows)."""
    clave: str
    texto: str = ""


@dataclass(frozen=True)
class Sonido:
    """Sonido para la interfaz: 'activar', 'pausar', 'clic', 'perdida'."""
    nombre: str


ACCIONES_DE_ENTRADA = (Mover, MoverDelta, Bajar, Subir, Clic, Rueda, Tecla, Esperar, SoltarTodo, Pulsar)


def es_de_entrada(a) -> bool:
    """True si la acción llega a Windows (o a la salida simulada)."""
    return isinstance(a, ACCIONES_DE_ENTRADA)


def describir(a) -> str:
    """Texto corto en español para el modo ensayo y el registro."""
    nombres = {"izq": "izquierdo", "der": "derecho", "medio": "del medio"}
    if isinstance(a, Mover):
        return f"Mover a ({a.x}, {a.y})"
    if isinstance(a, MoverDelta):
        return f"Mover {a.dx:+d}, {a.dy:+d}"
    if isinstance(a, Bajar):
        return f"Presionar botón {nombres.get(a.boton, a.boton)}"
    if isinstance(a, Subir):
        return f"Soltar botón {nombres.get(a.boton, a.boton)}"
    if isinstance(a, Clic):
        return ("Doble clic " if a.veces == 2 else "Clic ") + nombres.get(a.boton, a.boton)
    if isinstance(a, Pulsar):
        from .teclas import nombre_envio
        return f"Tecla {nombre_envio(a.teclas)}"
    if isinstance(a, Rueda):
        return f"Rueda {'acercar' if a.delta > 0 else 'alejar'} ({a.delta:+d})"
    if isinstance(a, Tecla):
        return f"{'Presionar' if a.abajo else 'Soltar'} {a.tecla.capitalize()}"
    if isinstance(a, Esperar):
        return f"Esperar {a.ms} ms"
    if isinstance(a, SoltarTodo):
        return "Soltar todo" + (f" ({a.motivo})" if a.motivo else "")
    if isinstance(a, Aviso):
        return a.texto or a.clave
    if isinstance(a, Sonido):
        return f"Sonido {a.nombre}"
    return repr(a)
