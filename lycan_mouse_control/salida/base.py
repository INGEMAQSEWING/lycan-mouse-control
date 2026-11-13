"""Interfaz común de las salidas (Windows real y simulada).

La base lleva la cuenta de lo presionado (bajo Lock) y aplica las reglas de seguridad:
- ``Bajar`` no hace nada si el botón ya está abajo (nunca dos "down" seguidos).
- Nunca se envía rueda con Shift o Ctrl abajo: antes se termina el arrastre.
- No se presiona nada con el puntero sobre la ventana propia.
- ``soltar_todo()``: en UNA llamada suelta primero los botones y luego Shift, Ctrl y Alt.
  Es seguro desde cualquier hilo.
"""
from __future__ import annotations

import logging
import threading
import time

from ..acciones import (Aviso, Bajar, Clic, Esperar, Mover, MoverDelta, Rueda, SoltarTodo, Subir, Tecla,
                        es_de_entrada)
from ..constantes import ALT, CTRL, SHIFT

log = logging.getLogger("lycan")


class ErrorEnvio(OSError):
    """SendInput entregó menos eventos de los pedidos (pantalla bloqueada, UAC...)."""


class SalidaBase:
    simulada = False

    def __init__(self):
        self._lock = threading.RLock()
        self.botones_abajo: list[str] = []
        self.teclas_abajo: list[str] = []
        self.rect_propio = None          # (l, t, r, b) de la ventana de Lycan Mouse Control
        self.foco_propio = False         # la ventana activa es la nuestra
        self.escritorio = (0, 0, 1366, 768)  # x, y, ancho, alto del escritorio virtual
        self.ultimo_motivo = ""
        self.contador_soltar = 0

    # ---- lo que implementa cada salida ----
    def _enviar(self, eventos: list):  # pragma: no cover - abstracto
        """eventos: ('mover', x, y) | ('boton', b, abajo) | ('rueda', delta) | ('tecla', k, abajo)."""
        raise NotImplementedError

    def posicion_cursor(self):  # pragma: no cover - abstracto
        raise NotImplementedError

    def _dormir(self, ms: int):
        time.sleep(ms / 1000.0)

    # ---- utilidades ----
    def _sobre_ventana_propia(self) -> bool:
        if self.rect_propio is None:
            return False
        try:
            x, y = self.posicion_cursor()
        except Exception:  # noqa: BLE001
            return False
        l, t, r, b = self.rect_propio
        return l <= x < r and t <= y < b

    def _limitar(self, x: int, y: int):
        vx, vy, vw, vh = self.escritorio
        return min(max(int(x), vx), vx + vw - 1), min(max(int(y), vy), vy + vh - 1)

    # ---- API ----
    def aplicar(self, acciones) -> list:
        """Aplica una lista de acciones. Devuelve avisos (p. ej. puntero sobre la ventana propia).
        Lanza ErrorEnvio si Windows rechazó los eventos."""
        avisos = []
        for a in acciones or ():
            if a is None or not es_de_entrada(a):
                continue
            with self._lock:
                if isinstance(a, Mover):
                    self._enviar([("mover",) + self._limitar(a.x, a.y)])
                elif isinstance(a, MoverDelta):
                    x, y = self.posicion_cursor()
                    self._enviar([("mover",) + self._limitar(x + a.dx, y + a.dy)])
                elif isinstance(a, Bajar):
                    if a.boton in self.botones_abajo:
                        continue
                    if self.foco_propio or self._sobre_ventana_propia():
                        avisos.append(Aviso("sobre_ventana"))
                        continue
                    self._enviar([("boton", a.boton, True)])
                    self.botones_abajo.append(a.boton)
                elif isinstance(a, Subir):
                    if a.boton not in self.botones_abajo:
                        continue
                    self.botones_abajo.remove(a.boton)
                    self._enviar([("boton", a.boton, False)])
                elif isinstance(a, Clic):
                    if self.foco_propio or self._sobre_ventana_propia():
                        avisos.append(Aviso("sobre_ventana"))
                        continue
                    if a.boton in self.botones_abajo:
                        continue
                    self._enviar([("boton", a.boton, True), ("boton", a.boton, False)])
                elif isinstance(a, Rueda):
                    if self.foco_propio:
                        continue
                    if SHIFT in self.teclas_abajo or CTRL in self.teclas_abajo:
                        # nunca rueda con modificadores: primero se termina el arrastre
                        self._soltar(motivo="rueda con modificadores")
                    if a.delta:
                        self._enviar([("rueda", int(a.delta))])
                elif isinstance(a, Tecla):
                    if a.abajo:
                        if a.tecla in self.teclas_abajo:
                            continue
                        self._enviar([("tecla", a.tecla, True)])
                        self.teclas_abajo.append(a.tecla)
                    else:
                        if a.tecla not in self.teclas_abajo:
                            continue
                        self.teclas_abajo.remove(a.tecla)
                        self._enviar([("tecla", a.tecla, False)])
                elif isinstance(a, Esperar):
                    self._dormir(int(a.ms))
                elif isinstance(a, SoltarTodo):
                    self._soltar(a.motivo)
        return avisos

    def _soltar(self, motivo: str = ""):
        eventos = [("boton", b, False) for b in list(self.botones_abajo)]
        # por seguridad siempre se sueltan Shift, Ctrl y Alt aunque no figuren
        eventos += [("tecla", k, False) for k in (SHIFT, CTRL, ALT)]
        self.botones_abajo.clear()
        self.teclas_abajo.clear()
        self.ultimo_motivo = motivo
        self.contador_soltar += 1
        try:
            self._enviar(eventos)
        except Exception as e:  # noqa: BLE001 - soltar de más no hace daño; nunca romper aquí
            log.warning("soltar_todo no pudo enviar (%s): %s", motivo, e)

    def soltar_todo(self, motivo: str = ""):
        """Suelta todo lo presionado. Seguro desde cualquier hilo y llamado varias veces."""
        with self._lock:
            hubo = bool(self.botones_abajo or self.teclas_abajo)
            self._soltar(motivo)
        if hubo:
            log.info("Soltar todo: %s", motivo or "sin motivo")

    def probar(self) -> bool:
        """Envío inocuo para saber si Windows vuelve a aceptar eventos."""
        try:
            with self._lock:
                x, y = self.posicion_cursor()
                self._enviar([("mover",) + self._limitar(x, y)])
            return True
        except Exception:  # noqa: BLE001
            return False

    def todo_suelto(self) -> bool:
        return not self.botones_abajo and not self.teclas_abajo
