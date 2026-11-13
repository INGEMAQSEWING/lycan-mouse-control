"""Zona activa de la cámara (imagen ya en espejo) -> píxeles de UN monitor."""
from __future__ import annotations

from dataclasses import dataclass, field

BARRA_TAREAS_PX = 48     # alto típico de la barra de tareas de Windows 11 (si no se conoce)


@dataclass(frozen=True)
class Monitor:
    x: int
    y: int
    ancho: int
    alto: int
    principal: bool = True
    # Área de trabajo (sin la barra de tareas) como (izq, arriba, der, abajo) exclusivo, o None.
    trabajo: tuple | None = field(default=None, compare=False)

    @property
    def rect(self):
        return (self.x, self.y, self.x + self.ancho, self.y + self.alto)

    def zona_segura(self, margen: int = 60):
        """Rectángulo (x0, y0, x1, y1) inclusivo, lejos de los bordes y de la barra de tareas.

        Sirve para dejar el cursor al empezar a girar en 3D: un botón del medio sobre la barra
        de tareas abriría otra ventana del programa fijado."""
        if self.trabajo is not None:
            l, t, r, b = self.trabajo
        else:
            l, t, r, b = self.x, self.y, self.x + self.ancho, self.y + self.alto - BARRA_TAREAS_PX
        l, t = max(l, self.x), max(t, self.y)
        r, b = min(r, self.x + self.ancho), min(b, self.y + self.alto)
        mx = min(margen, max((r - l) // 4, 0))
        my = min(margen, max((b - t) // 4, 0))
        return (l + mx, t + my, r - 1 - mx, b - 1 - my)


MONITOR_REFERENCIA = Monitor(0, 0, 1366, 768, True)
ALTO_MIN = 0.30


class Mapeo:
    """Rectángulo (x0, y0, x1, y1) en 0..1 de la imagen -> monitor.

    Si ``ajustar_aspecto`` es verdadero, el alto de la zona se ajusta para que su proporción
    (en píxeles de la cámara) sea la del monitor: un círculo hecho con la mano sale círculo.
    Nunca baja del 30 % del alto de la imagen. Fuera de la zona se recorta al borde.
    """

    def __init__(self, zona=(0.20, 0.25, 0.80, 0.70), monitor: Monitor = MONITOR_REFERENCIA,
                 aspecto_cam: float = 640 / 480, ajustar_aspecto: bool = True):
        self.monitor = monitor
        self.aspecto_cam = aspecto_cam
        self.ajustar = ajustar_aspecto
        self.zona_pedida = tuple(float(v) for v in zona)
        self._calcular()

    def _calcular(self):
        x0, y0, x1, y1 = self.zona_pedida
        x0, x1 = sorted((min(max(x0, 0.0), 1.0), min(max(x1, 0.0), 1.0)))
        y0, y1 = sorted((min(max(y0, 0.0), 1.0), min(max(y1, 0.0), 1.0)))
        if x1 - x0 < 0.05:
            x0, x1 = 0.2, 0.8
        if y1 - y0 < 0.05:
            y0, y1 = 0.25, 0.70
        if self.ajustar and self.monitor.alto > 0:
            asp_mon = self.monitor.ancho / self.monitor.alto
            alto = (x1 - x0) * self.aspecto_cam / asp_mon
            alto = min(max(alto, ALTO_MIN), 1.0)
            cy = (y0 + y1) / 2.0
            y0, y1 = cy - alto / 2.0, cy + alto / 2.0
            if y0 < 0:
                y0, y1 = 0.0, alto
            if y1 > 1:
                y0, y1 = 1.0 - alto, 1.0
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def cambiar_monitor(self, monitor: Monitor):
        self.monitor = monitor
        self._calcular()

    def cambiar_zona(self, zona):
        self.zona_pedida = tuple(float(v) for v in zona)
        self._calcular()

    @property
    def zona(self):
        return (self.x0, self.y0, self.x1, self.y1)

    @property
    def px_por_unidad_x(self) -> float:
        """Píxeles de pantalla por unidad de imagen en x (para mover 1:1 en desplazar)."""
        return (self.monitor.ancho - 1) / (self.x1 - self.x0)

    @property
    def px_por_unidad_y(self) -> float:
        return (self.monitor.alto - 1) / (self.y1 - self.y0)

    def a_pantalla(self, u: float, v: float):
        """(u, v) de la imagen -> (x, y) en píxeles (flotantes) del monitor, recortado."""
        fu = min(max((u - self.x0) / (self.x1 - self.x0), 0.0), 1.0)
        fv = min(max((v - self.y0) / (self.y1 - self.y0), 0.0), 1.0)
        m = self.monitor
        return m.x + fu * (m.ancho - 1), m.y + fv * (m.alto - 1)

    def dentro(self, u: float, v: float) -> bool:
        return self.x0 <= u <= self.x1 and self.y0 <= v <= self.y1

    def cerca_del_borde(self, u: float, v: float, margen: float = 0.08) -> bool:
        """True si el punto está a menos del 8 % del borde de la zona (o fuera)."""
        fu = (u - self.x0) / (self.x1 - self.x0)
        fv = (v - self.y0) / (self.y1 - self.y0)
        return not (margen <= fu <= 1 - margen and margen <= fv <= 1 - margen)
