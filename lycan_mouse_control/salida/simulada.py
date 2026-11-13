"""Salida simulada: no llega nada a Windows. Anota cada evento con su tiempo y lleva el
estado de botones, teclas y cursor para que las pruebas verifiquen que todo quedó suelto.
Se usa en las pruebas, en el asistente (modo ensayo) y con --simular.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from .base import ErrorEnvio, SalidaBase


class SalidaSimulada(SalidaBase):
    simulada = True

    def __init__(self, escritorio=(0, 0, 1366, 768), cursor=(683, 384), reloj=None, al_enviar=None,
                 max_eventos: int | None = None):
        """max_eventos: con --simular la lista se recorta a los últimos N (si no, crecía sin
        límite: unos 21 MB por hora de uso). Las pruebas y el asistente la usan completa."""
        super().__init__()
        self.escritorio = escritorio
        self.cursor = tuple(cursor)
        self.eventos = deque(maxlen=int(max_eventos)) if max_eventos else []   # (t, evento)
        self.n_eventos = 0               # total enviado (aunque la lista esté recortada)
        self.reloj = reloj or time.perf_counter
        self.fallar = False              # simula SendInput bloqueado
        self.al_enviar = al_enviar       # callback(lista_eventos) para mostrar en pantalla
        self.violaciones: list[str] = []
        self.llamadas = 0
        self._lock_ev = threading.Lock()

    def posicion_cursor(self):
        return self.cursor

    def _dormir(self, ms: int):
        with self._lock_ev:
            self.eventos.append((self.reloj(), ("esperar", ms)))
            self.n_eventos += 1

    def _enviar(self, eventos: list):
        if self.fallar:
            raise ErrorEnvio(5, "SendInput bloqueado (simulado)")
        t = self.reloj()
        self.llamadas += 1
        with self._lock_ev:
            for ev in eventos:
                if ev[0] == "mover":
                    self.cursor = (ev[1], ev[2])
                elif ev[0] == "rueda":
                    if any(k in self.teclas_abajo for k in ("shift", "ctrl")):
                        self.violaciones.append("rueda con modificadores abajo")
                elif ev[0] == "tecla" and not ev[2] and ev[1] == "shift":
                    if "medio" in self.botones_abajo:
                        self.violaciones.append("shift subió antes que el medio")
                self.eventos.append((t, ev))
                self.n_eventos += 1
        if self.al_enviar:
            try:
                self.al_enviar(eventos)
            except Exception:  # noqa: BLE001
                pass

    # ---- ayudas para pruebas ----
    def solo(self, tipo: str) -> list:
        return [ev for _, ev in self.eventos if ev[0] == tipo]

    def botones(self) -> list:
        """Lista de ('izq', True/False) en orden."""
        return [(ev[1], ev[2]) for _, ev in self.eventos if ev[0] == "boton"]

    def limpiar(self):
        with self._lock_ev:
            self.eventos.clear()
