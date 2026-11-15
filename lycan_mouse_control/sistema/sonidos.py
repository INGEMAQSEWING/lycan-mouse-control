"""Sonidos cortos en un hilo aparte (winsound.Beep bloquea mientras suena)."""
from __future__ import annotations

import queue
import threading

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None

TONOS = {
    "activar": [(880, 60)],
    "pausar": [(440, 60), (330, 60)],
    "clic": [(1200, 15)],
    "perdida": [(300, 120)],
    "scroll": [(660, 40), (990, 40)],       # 1.0.2 paquete C: empieza a pasar página
}


class Sonidos:
    def __init__(self, activos: bool = True):
        self.activos = activos
        self._cola: queue.Queue = queue.Queue(maxsize=8)
        self._hilo = threading.Thread(target=self._bucle, daemon=True, name="sonidos")
        self._hilo.start()

    def tocar(self, nombre: str):
        if not self.activos or winsound is None or nombre not in TONOS:
            return
        try:
            self._cola.put_nowait(nombre)
        except queue.Full:
            pass

    def _bucle(self):
        while True:
            nombre = self._cola.get()
            if nombre is None:
                return
            for f, ms in TONOS.get(nombre, ()):
                try:
                    winsound.Beep(f, ms)
                except RuntimeError:
                    pass

    def cerrar(self):
        try:
            self._cola.put_nowait(None)
        except queue.Full:
            pass
