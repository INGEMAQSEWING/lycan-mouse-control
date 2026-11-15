"""Núcleo puro: Seguidor (identidad + clasificador por mano) + Máquina de estados.

Recibe las manos detectadas de cada cuadro y devuelve un Resultado con las acciones.
Si algo falla dentro, devuelve SoltarTodo + pausa (nunca deja botones presionados).
"""
from __future__ import annotations

import logging
import time
from collections import deque

from .acciones import Aviso, SoltarTodo
from .estados import MaquinaEstados, Resultado
from .mapeo import Mapeo
from .perfiles import GENERICO, Perfil
from .seguidor import Seguidor
from .senas import construir_umbrales

log = logging.getLogger("lycan")


class Nucleo:
    def __init__(self, config: dict, perfil: Perfil = GENERICO, mapeo: Mapeo | None = None, pos_cursor=None):
        self.config = config
        cam = config.get("camara") or {}
        aspecto = float(cam.get("ancho", 640)) / float(cam.get("alto", 480) or 480)
        self.umbrales = construir_umbrales(config.get("senas"), una_mano_zoom=(config.get("zoom") or {}).get("una_mano"))
        self.seguidor = Seguidor(self.umbrales, config.get("mano_principal", "derecha"), aspecto)
        self.maquina = MaquinaEstados(config, perfil, mapeo, pos_cursor)
        self.errores: deque = deque()
        self.fatal = False
        self.ultimo_error: str = ""

    # ---- atajos a la máquina ----
    @property
    def estado(self) -> str:
        return self.maquina.estado_visible()

    @property
    def modo(self) -> str:
        return self.maquina.modo

    def actualizar_umbrales(self, cfg_senas: dict, una_mano_zoom: bool):
        self.umbrales = construir_umbrales(cfg_senas, una_mano_zoom=una_mano_zoom)
        self.seguidor.actualizar_umbrales(self.umbrales)
        self.maquina.zoom_una_mano = bool(una_mano_zoom)

    def procesar(self, t: float, manos) -> Resultado:
        try:
            self.seguidor.actualizar(t, manos)
            return self.maquina.paso(t, self.seguidor)
        except Exception as e:  # noqa: BLE001
            return self.por_error(t, e)

    def por_error(self, t: float, e: BaseException) -> Resultado:
        """Excepción en la lógica: soltar todo, pausar y avisar. 3 errores en 1 minuto = fatal."""
        log.exception("Error en la lógica de señas: %s", e)
        self.ultimo_error = repr(e)
        ahora = time.monotonic()
        self.errores.append(ahora)
        while self.errores and ahora - self.errores[0] > 60:
            self.errores.popleft()
        if len(self.errores) >= 3:
            self.fatal = True
        acc = [SoltarTodo("error")]
        try:
            acc += [a for a in self.maquina.pausar(t, "error") if not isinstance(a, SoltarTodo)]
        except Exception:  # noqa: BLE001
            self.maquina.base = "PAUSA"
        try:
            self.seguidor.reiniciar()
        except Exception:  # noqa: BLE001
            pass
        aviso = Aviso("error")
        return Resultado(acciones=acc + [aviso], estado="PAUSA", base="PAUSA", avisos=[aviso],
                         modo=self.maquina.modo)

    # ---- órdenes ----
    def alternar_pausa(self, t):
        return self.maquina.alternar_pausa(t)

    def pausar(self, t, motivo="pausa"):
        return self.maquina.pausar(t, motivo)

    def cambiar_modo(self, t, modo):
        return self.maquina.cambiar_modo(t, modo)

    def cambiar_perfil(self, t, perfil):
        return self.maquina.cambiar_perfil(t, perfil)

    def bloquear(self, t, motivo):
        return self.maquina.bloquear(t, motivo)

    def desbloquear(self, t):
        return self.maquina.desbloquear(t)

    # ---- 1.0.2 paquete A: tecla de clic ----
    def tecla_clic(self, t, abajo):
        return self.maquina.tecla_clic(t, abajo)

    def frenar(self, t):
        return self.maquina.frenar(t)

    def otra_tecla(self, t):
        return self.maquina.otra_tecla(t)
