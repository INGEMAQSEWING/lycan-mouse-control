"""Máquina de estados principal (sección 4 de la especificación). Lógica PURA.

Recibe las pistas de manos (ya clasificadas por el Seguidor) y el tiempo real, y devuelve
una lista de acciones. No importa ctypes, cv2 ni tkinter.

Estados: PAUSA (inicial), ACTIVO (con subestados ESPERA / UN_TOQUE), BLOQUEADO.
Estados visibles derivados: ARRASTRANDO, GIRANDO_3D, DESPLAZANDO, SIN_MANO.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import constantes as K
from .acciones import (Aviso, Bajar, Clic, Esperar, Mover, MoverDelta, Rueda, SoltarTodo, Sonido, Subir,
                       Tecla)
from .filtros import OneEuro
from .mapeo import Mapeo
from .perfiles import GENERICO, Combinacion, Perfil, Traductor
from .puntero import Puntero
from .senas import Sena

ESPERA, UN_TOQUE = "ESPERA", "UN_TOQUE"
LATENCIA_ACTIVAR_S = 0.1   # tope de la latencia de entrada de ACTIVAR que se descuenta
ACTIVAR_CUADROS_MIN = 2     # ACTIVAR tiene que verse de verdad al menos 2 cuadros (sin crédito)

TIEMPOS_FABRICA = {
    "pellizco": [66, 66], "puno": 200, "puno_espera": 500, "puno_tras_pellizco": 300,
    "activar_min": 120, "activar_max": 1500, "activar_en_pausa": 250, "soltar_min": 100,
    "doble_ventana": 700, "ignorar_tras_activar": 800, "agarre_3d": 150,
    "mano_perdida": 150, "pausa_sin_mano_s": 10,
}


@dataclass
class Resultado:
    acciones: list = field(default_factory=list)
    estado: str = K.PAUSA          # estado visible
    base: str = K.PAUSA            # PAUSA / ACTIVO / BLOQUEADO
    sub: str = ESPERA
    etiqueta: str = ""             # clave de texto de la seña o evento en curso
    progreso: float = 0.0          # 0..1 para el anillo de progreso
    avisos: list = field(default_factory=list)
    cerca_borde: bool = False
    modo: str = "2D"


def _ang_wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class MaquinaEstados:
    def __init__(self, config: dict, perfil: Perfil = GENERICO, mapeo: Mapeo | None = None,
                 pos_cursor=None):
        self.cfg = config
        self.modo = "3D" if config.get("modo") == "3D" else "2D"
        self.mapeo = mapeo or Mapeo()
        self.puntero = Puntero(self.mapeo, config.get("puntero"))
        zoom = config.get("zoom") or {}
        self.traductor = Traductor(perfil, invertir_zoom=bool(zoom.get("invertir", False)),
                                   max_muescas_cfg=float(zoom.get("max_muescas_s", 8)))
        self.pos_cursor = pos_cursor
        self._leer_config()
        self._reiniciar_todo()
        self.base = K.PAUSA
        self.sub = ESPERA
        self.motivo_bloqueo = ""
        self._t = 0.0

    # ------------------------------------------------------------------ config
    def _leer_config(self):
        cfg = self.cfg
        tm = dict(TIEMPOS_FABRICA)
        tm.update(((cfg.get("senas") or {}).get("tiempos_ms") or {}))
        self.tm = tm
        p_in, p_out = tm["pellizco"] if isinstance(tm["pellizco"], (list, tuple)) else (66, 66)
        self.s_pellizco_in = p_in / 1000.0
        self.s_pellizco_out = p_out / 1000.0
        zoom = cfg.get("zoom") or {}
        self.zoom_paso = float(zoom.get("paso_log", 0.08))
        self.zoom_muerta = float(zoom.get("zona_muerta_log", 0.05))
        self.zoom_una_mano = bool(zoom.get("una_mano", False))
        orb = cfg.get("orbita") or {}
        self.k_vol = float(orb.get("k_vol", 1.0))
        self.k_mov = float(orb.get("k_mov", 0.8))
        self.ganancia = float(orb.get("ganancia", 1.0))
        self.max_px = float(orb.get("max_px_cuadro", 60))
        senas = cfg.get("senas") or {}
        self.desplazar_dos_manos = bool(senas.get("desplazar_dos_manos", True))
        cam = cfg.get("camara") or {}
        self.aspecto = float(cam.get("ancho", 640)) / float(cam.get("alto", 480) or 480)

    def _reiniciar_todo(self):
        # activación
        self.ep_inicio = None
        self.ep_fin = None
        self.ep_consumido = False
        self.ep_activador = False
        self.ep_ignorado = False
        self.ep_aviso_larga = False
        self.ignorar_hasta = -1.0
        self.un_toque_fin = None
        self.t_pre_act = None        # primer cuadro "de paso" (V / NINGUNA) antes de ACTIVAR
        self.ep_n_act = 0            # cuadros REALES de ACTIVAR del episodio
        # botones / teclas que nosotros presionamos
        self.botones = []
        self.teclas = []
        # pellizco (clic izquierdo)
        self.pel_desde = None
        self.pel_salida = None
        self.t_ult_pellizco = -10.0
        self.izq = False
        # puño
        self.puno_inicio = None
        self.puno_ult = -10.0
        self.puno_valido = False
        self.puno_disparado = False
        self.puno_bloqueo = -1.0
        self.puno_c0 = None
        # después de un gesto de dos manos, de perder la mano o de cambiar de mano principal:
        # requiere_soltar pide que la mano principal muestre una seña neutra 100 ms antes de
        # otro clic; rearme_dos pide que AL MENOS una mano se abra antes de volver a agarrar
        # con las dos (pinza u órbita).
        self.requiere_soltar = False
        self.libre_desde = None
        self.rearme_dos = False
        self.libre2_desde = None
        # dos manos
        self.par_cand = None
        self.par_desde = None
        self.gesto = None            # None | 'pinza' | 'orbita' | 'zoom1'
        self.g = {}
        # sin mano
        self.sin_mano = False
        self.t_sin_mano = None
        self.id_principal = None
        # medio
        self.t_medio_arriba = -10.0
        self.pos_medio_arriba = None
        self.cursor = None
        self.etiqueta = ""
        self.etiqueta_t = -10.0

    # ------------------------------------------------------------ utilidades
    @property
    def perfil(self) -> Perfil:
        return self.traductor.perfil

    def _emitir(self, acc: list, nuevas):
        for a in nuevas:
            if a is None:
                continue
            acc.append(a)
            if isinstance(a, Bajar) and a.boton not in self.botones:
                self.botones.append(a.boton)
            elif isinstance(a, Subir):
                if a.boton in self.botones:
                    self.botones.remove(a.boton)
                if a.boton == K.MEDIO:
                    self.t_medio_arriba = self._t
                    self.pos_medio_arriba = self.cursor
            elif isinstance(a, Tecla):
                if a.abajo and a.tecla not in self.teclas:
                    self.teclas.append(a.tecla)
                elif not a.abajo and a.tecla in self.teclas:
                    self.teclas.remove(a.tecla)
            elif isinstance(a, Mover):
                self.cursor = (a.x, a.y)
            elif isinstance(a, MoverDelta) and self.cursor is not None:
                self.cursor = (self.cursor[0] + a.dx, self.cursor[1] + a.dy)
            elif isinstance(a, SoltarTodo):
                if K.MEDIO in self.botones:
                    self.t_medio_arriba = self._t
                    self.pos_medio_arriba = self.cursor
                self.botones.clear()
                self.teclas.clear()

    def _cursor_real(self):
        if self.pos_cursor is not None:
            try:
                p = self.pos_cursor()
                if p is not None:
                    return (int(p[0]), int(p[1]))
            except Exception:  # noqa: BLE001 - nunca romper la lógica por esto
                pass
        return self.cursor

    def algo_sostenido(self) -> bool:
        return bool(self.botones or self.teclas)

    def _marcar(self, etiqueta: str):
        self.etiqueta = etiqueta
        self.etiqueta_t = self._t

    def _pedir_rearme(self, dos_manos: bool = True):
        """La próxima seña de clic o de agarre exige antes una seña neutra (sección 4.3).

        dos_manos=False cuando el gesto de dos manos terminó porque las manos se ABRIERON (eso
        ya es el rearme del agarre); True cuando se perdió una mano o cambió la principal."""
        self.requiere_soltar = True
        self.libre_desde = None
        if dos_manos:
            self.rearme_dos = True
            self.libre2_desde = None
        self.pel_desde = None
        self.puno_inicio = None
        self.par_cand = None

    def _soltar_todo(self, acc, motivo):
        """Suelta todo y deja la lógica en un estado limpio (sin gestos ni anclas)."""
        self._emitir(acc, [SoltarTodo(motivo)])
        self.izq = False
        self.pel_desde = None
        self.pel_salida = None
        self.gesto = None
        self.g = {}
        self.par_cand = None
        self.puntero.soltar_ancla(self._t, 0.0)
        self.traductor.vaciar()

    # --------------------------------------------------------- órdenes externas
    def pausar(self, t: float, motivo: str = "pausa") -> list:
        self._t = t
        acc: list = []
        if self.base == K.BLOQUEADO:
            self._soltar_todo(acc, motivo)
            return acc
        estaba = self.base
        self._soltar_todo(acc, motivo)        # SIEMPRE antes de actualizar la interfaz
        self.base = K.PAUSA
        self.sub = ESPERA
        self.un_toque_fin = None
        self.requiere_soltar = False
        self.rearme_dos = False
        if self.ep_inicio is not None:
            self.ep_consumido = True
        if estaba != K.PAUSA:
            acc.append(Sonido("pausar"))
            self._marcar("pausado")
        return acc

    def activar(self, t: float) -> list:
        self._t = t
        if self.base == K.BLOQUEADO:
            return []
        acc: list = []
        if self.base != K.ACTIVO:
            self.base = K.ACTIVO
            self.sub = ESPERA
            self.un_toque_fin = None
            self.puntero.reset()
            self.sin_mano = False
            self.t_sin_mano = t
            acc.append(Sonido("activar"))
            self._marcar("activado")
        return acc

    def alternar_pausa(self, t: float) -> list:
        """Atajo Ctrl+Alt+M."""
        if self.base == K.ACTIVO:
            return self.pausar(t, "atajo de teclado")
        return self.activar(t)

    def cambiar_modo(self, t: float, modo: str) -> list:
        """Cambio 2D/3D: suelta todo y pausa."""
        self._t = t
        acc = self.pausar(t, "cambio de modo")
        if not any(isinstance(a, SoltarTodo) for a in acc):
            self._soltar_todo(acc, "cambio de modo")
        self.modo = "3D" if modo == "3D" else "2D"
        return acc

    def cambiar_perfil(self, t: float, perfil: Perfil) -> list:
        self._t = t
        acc: list = []
        if perfil.clave == self.perfil.clave:
            return acc
        if self.algo_sostenido() or self.gesto or self.izq:
            self._soltar_todo(acc, "cambio de programa")
            if self.gesto is None:
                self._pedir_rearme()
        self.traductor.cambiar_perfil(perfil)
        acc.append(Aviso("perfil", perfil.nombre))
        return acc

    def bloquear(self, t: float, motivo: str) -> list:
        self._t = t
        acc: list = []
        self._soltar_todo(acc, "bloqueado: " + motivo)
        if self.base != K.BLOQUEADO:
            self.base_antes = self.base
        self.base = K.BLOQUEADO
        self.motivo_bloqueo = motivo
        acc.append(Aviso("bloqueado_" + motivo))
        return acc

    def desbloquear(self, t: float, volver_a_pausa: bool = True) -> list:
        self._t = t
        if self.base != K.BLOQUEADO:
            return []
        self.base = K.PAUSA if volver_a_pausa else getattr(self, "base_antes", K.PAUSA)
        self.motivo_bloqueo = ""
        self.puntero.reset()
        return [Aviso("desbloqueado")]

    def poner_dibujo_fino(self, si: bool):
        self.puntero.poner_dibujo_fino(si)

    # ------------------------------------------------------------- paso principal
    def paso(self, t: float, seguidor) -> Resultado:
        # duración de un cuadro (la seña de este cuadro "dura" hasta el siguiente)
        t_prev = getattr(self, "_t_paso", None)
        self._dt_cuadro = min(max(t - t_prev, 0.0), 0.07) if t_prev is not None else 0.0
        self._t_paso = t
        self._t = t
        acc: list = []
        avisos: list = []
        progreso = 0.0
        principal = seguidor.principal
        pistas = list(seguidor.pistas)

        if self.base == K.BLOQUEADO:
            return self._resultado(acc, avisos, 0.0)

        # --- activar / pausar (con la mano principal) ---
        # Una pista retenida (MediaPipe ya no ve la mano) conserva su última seña 150 ms: eso
        # sirve para CONTINUAR un gesto, nunca para contar una seña de activar o pausar.
        act = principal is not None and principal.detectada and principal.sena == Sena.ACTIVAR
        s_p = principal.sena if principal is not None else None
        if s_p in (Sena.V, Sena.NINGUNA):
            if self.t_pre_act is None:
                self.t_pre_act = t
        elif s_p != Sena.ACTIVAR:
            self.t_pre_act = None
        progreso = self._activacion(t, act, acc, avisos)

        if self.base == K.PAUSA:
            if principal is not None:
                self.puntero.observar(t, *principal.img[8, :2])
            return self._resultado(acc, avisos, progreso)

        # --- ACTIVO ---
        if principal is None:
            if not self.sin_mano:
                self.sin_mano = True
                self.t_sin_mano = t
                habia = self.algo_sostenido() or self.izq or self.gesto is not None
                self._soltar_todo(acc, "mano perdida")
                self.puntero.reset()
                if habia:
                    acc.append(Sonido("perdida"))
                # Al volver, la mano no puede presionar nada sola: primero una seña neutra. Si se
                # perdió en pleno gesto, tampoco puede volver a agarrar con las dos manos.
                self._pedir_rearme(dos_manos=habia)
            if t - (self.t_sin_mano or t) > float(self.tm["pausa_sin_mano_s"]):
                acc.extend(self.pausar(t, "sin manos"))
                avisos.append(Aviso("pausa_sin_mano"))
            return self._resultado(acc, avisos, progreso)

        if self.sin_mano:
            self.sin_mano = False
            self.puntero.reset()
        # Cambió la mano principal: si había algo presionado se suelta; y SIEMPRE la nueva mano
        # tiene que mostrar una seña neutra antes de hacer clic (si no, una mano izquierda que
        # descansa cerrada o en pellizco dispararía un clic al retirarse la derecha).
        if self.id_principal is not None and principal.id != self.id_principal and self.gesto is None:
            habia = self.izq or self.algo_sostenido()
            if habia:
                self._soltar_todo(acc, "cambió la mano")
            self._pedir_rearme(dos_manos=habia)
            self.puntero.reset()
        self.id_principal = principal.id
        self._rearme_dos_manos(t, pistas)

        otras = [p for p in pistas if p.id != principal.id]
        otra = otras[0] if otras else None

        # --- gestos de dos manos ---
        if self.gesto in ("pinza", "orbita"):
            self._gesto_dos_manos(t, pistas, acc)
            if self.gesto is not None:
                return self._resultado(acc, avisos, progreso)
        elif len(pistas) == 2 and self.gesto is None:
            if self._candidato_dos_manos(t, pistas, acc):
                return self._resultado(acc, avisos, progreso)
        else:
            self.par_cand = None

        # --- una mano ---
        progreso = max(progreso, self._una_mano(t, principal, otra, act, acc, avisos))
        return self._resultado(acc, avisos, progreso)

    # ------------------------------------------------------------- activación
    def _activacion(self, t, act, acc, avisos) -> float:
        tm = self.tm
        progreso = 0.0
        if act:
            if self.ep_inicio is None:
                # El clasificador tarda ~2 cuadros en dar ACTIVAR al juntar los dedos (pasa por
                # V o NINGUNA) y en cambio la suelta en el primero: se resta esa latencia de
                # entrada para que la duración y el hueco de la doble seña sean los reales.
                self.ep_inicio = t
                if self.t_pre_act is not None:
                    self.ep_inicio = max(self.t_pre_act, t - LATENCIA_ACTIVAR_S)
                # el cuadro "de paso" ya se usó: la próxima seña toma los suyos (si no, unos
                # parpadeos de ACTIVAR entre cuadros de V heredarían un crédito viejo)
                self.t_pre_act = None
                self.ep_n_act = 0
                self.ep_consumido = False
                self.ep_activador = False
                self.ep_aviso_larga = False
                self.ep_ignorado = t < self.ignorar_hasta
            self.ep_fin = None
            self.ep_n_act += 1               # cuadros REALES de ACTIVAR
        elif self.ep_inicio is not None:
            if self.ep_fin is None:
                self.ep_fin = t
            if t - self.ep_fin >= tm["soltar_min"] / 1000.0 - 1e-9:
                self._fin_episodio(self.ep_fin - self.ep_inicio)
                self.ep_inicio = None
                self.ep_fin = None
                self.t_pre_act = None

        en_curso = self.ep_inicio is not None and self.ep_fin is None
        if self.base == K.PAUSA:
            if en_curso and not self.ep_consumido and not self.ep_ignorado:
                dur = t - self.ep_inicio
                progreso = min(dur / (tm["activar_en_pausa"] / 1000.0), 1.0)
                if dur >= tm["activar_en_pausa"] / 1000.0 - 1e-9:
                    self.ep_consumido = True
                    self.ep_activador = True
                    acc.extend(self.activar(t))
        elif self.base == K.ACTIVO:
            if self.sub == UN_TOQUE and self.un_toque_fin is not None:
                if en_curso and not self.ep_consumido and not self.ep_ignorado \
                        and self.ep_inicio - self.un_toque_fin <= tm["doble_ventana"] / 1000.0:
                    # La duración "acreditada" (con la latencia de entrada) sirve para el anillo;
                    # para decidir se exige además que ACTIVAR se haya visto de verdad varios
                    # cuadros seguidos: un parpadeo del clasificador no es una seña.
                    dur = t - self.ep_inicio + getattr(self, "_dt_cuadro", 0.0)
                    progreso = min(dur / (tm["activar_min"] / 1000.0), 1.0)
                    if dur >= tm["activar_min"] / 1000.0 - 1e-9 and self._activar_real_ok():
                        self.ep_consumido = True
                        acc.extend(self.pausar(t, "seña doble"))
                        return 1.0
                elif not en_curso and t - self.un_toque_fin > tm["doble_ventana"] / 1000.0:
                    self.sub = ESPERA
                    self.un_toque_fin = None
            if en_curso and not self.ep_consumido and not self.ep_ignorado:
                dur = t - self.ep_inicio
                if dur > tm["activar_max"] / 1000.0 and not self.ep_aviso_larga:
                    self.ep_aviso_larga = True
                    avisos.append(Aviso("sena_larga"))
                    acc.append(Aviso("sena_larga"))
        return progreso

    def _activar_real_ok(self) -> bool:
        """ACTIVAR visto de verdad (sin crédito de latencia) al menos 2 cuadros. Un cuadro suelto
        entre cuadros de V o NINGUNA es ruido del clasificador (índice y corazón casi juntos),
        no una seña. No se piden 3: el clasificador tarda ~2 cuadros en dar ACTIVAR, así que una
        seña real de 150 ms solo deja 2 cuadros de ACTIVAR."""
        return getattr(self, "ep_n_act", 0) >= ACTIVAR_CUADROS_MIN

    def _fin_episodio(self, dur: float):
        tm = self.tm
        if self.ep_activador:
            self.ignorar_hasta = self.ep_fin + tm["ignorar_tras_activar"] / 1000.0
            return
        if self.ep_consumido or self.ep_ignorado or self.base != K.ACTIVO:
            return
        if not self._activar_real_ok():
            return
        if tm["activar_min"] / 1000.0 - 1e-9 <= dur <= tm["activar_max"] / 1000.0 + 1e-9:
            self.sub = UN_TOQUE
            self.un_toque_fin = self.ep_fin

    # ------------------------------------------------------------- una mano
    def _una_mano(self, t, p, otra, act, acc, avisos) -> float:
        s = p.sena
        progreso = 0.0
        u, v = float(p.img[8, 0]), float(p.img[8, 1])
        ref = (p.img[5, :2] + p.img[9, :2]) / 2.0
        self.puntero.observar(t, u, v, embrague=(s == Sena.NINGUNA), ref=(float(ref[0]), float(ref[1])))
        # La otra mano cuenta como "a la vista" mientras su pista siga viva, aunque MediaPipe la
        # haya perdido en este cuadro: si no, un hueco de un cuadro justo al empezar la pinza de
        # dos manos bajaba la espera y salía un clic izquierdo en mitad del zoom.
        otra_visible = otra is not None

        # rearme tras un gesto de dos manos o un cambio de programa
        if self.requiere_soltar:
            if s in (Sena.PELLIZCO, Sena.PUNO, Sena.PELLIZCO_CORAZON):
                self.libre_desde = None
            else:
                if self.libre_desde is None:
                    self.libre_desde = t
                if t - self.libre_desde >= 0.1:
                    self.requiere_soltar = False

        # ---- variante: acercar/alejar con una mano (pellizco pulgar + corazón) ----
        if self.gesto == "zoom1":
            self._zoom_una_mano(t, p, s, acc)
            return 0.0
        if self.zoom_una_mano and s == Sena.PELLIZCO_CORAZON and not self.izq and not self.requiere_soltar:
            g = self.g.setdefault("zoom1_cand", t)
            progreso = min((t - g) / 0.1, 1.0)
            if t - g >= 0.1:
                self.gesto = "zoom1"
                y = float((p.img[4, 1] + p.img[12, 1]) / 2.0)
                self.g = {"y_ref": y, "salida": None}
                self._marcar("zoom")
            return progreso
        self.g.pop("zoom1_cand", None)

        # ---- pellizco: clic izquierdo y arrastre ----
        # Una mano que ya no se ve (pista retenida) solo puede SOSTENER un arrastre en curso;
        # nunca empezar ni completar un clic nuevo.
        crudo = s == Sena.PELLIZCO and (p.detectada or self.izq)
        t_pel_previo = self.t_ult_pellizco
        if crudo:
            self.t_ult_pellizco = t
        if not self.izq:
            if crudo:
                if self.pel_desde is None:
                    self.pel_desde = t
            else:
                self.pel_desde = None
            espera = self.s_pellizco_in
            if otra_visible:
                # con otra mano a la vista se espera un poco más: puede ser el zoom con dos manos
                espera = max(espera, 0.150)
                if otra.sena == Sena.PELLIZCO:
                    espera = float("inf")
            # simétrico a "puno_tras_pellizco": un pellizco que aparece justo después de un puño
            # es la mano abriéndose, no un clic izquierdo.
            permitido = (not act and not self.requiere_soltar and self.par_cand is None
                         and self.puno_inicio is None
                         and t - self.puno_ult > self.tm["puno_tras_pellizco"] / 1000.0)
            if crudo and self.pel_desde is not None:
                progreso = min((t - self.pel_desde) / max(espera, 1e-3), 1.0) if math.isfinite(espera) else 0.0
            if crudo and permitido and self.pel_desde is not None and t - self.pel_desde >= espera - 1e-9:
                self._emitir(acc, [self.puntero.anclar(self.pel_desde), Bajar(K.IZQ)])
                self.izq = True
                self.pel_salida = None
                acc.append(Sonido("clic"))
                self._marcar("clic_izquierdo")
        else:
            if crudo:
                self.pel_salida = None
            else:
                if self.pel_salida is None:
                    self.pel_salida = t
                if t - self.pel_salida >= self.s_pellizco_out - 1e-9:
                    self._emitir(acc, [Subir(K.IZQ)])
                    self.izq = False
                    self.pel_desde = None
                    self.puntero.soltar_ancla(t)
                    self._marcar("arrastre_fin" if self.puntero.arrastrando else "clic_izquierdo")

        # ---- puño: clic derecho ----
        # (con la mano retenida el puño en curso solo se sostiene: no empieza ni dispara)
        es_puno = s == Sena.PUNO and (p.detectada or (self.puno_inicio is not None
                                                      and t - self.puno_ult <= 0.066))
        if es_puno:
            if self.puno_inicio is None or t - self.puno_ult > 0.066:
                self.puno_inicio = t
                self.puno_c0 = p.centro.copy()
                self.puno_disparado = False
                self.puno_valido = (
                    t - t_pel_previo > self.tm["puno_tras_pellizco"] / 1000.0
                    and not self.izq and t >= self.puno_bloqueo and not self.requiere_soltar)
            self.puno_ult = t
            exigente = self.modo == "3D" or otra_visible
            espera = (max(self.tm["puno"], 250) if exigente else self.tm["puno"]) / 1000.0
            if otra is not None and otra.sena == Sena.PUNO:
                self.puno_valido = False      # dos puños nunca hacen clic derecho
            if exigente and self.puno_c0 is not None:
                d = (p.centro - self.puno_c0) * np.array([1.0, 1.0 / self.aspecto])
                if float(np.hypot(*d)) > 0.02:
                    self.puno_valido = False
            if self.izq:
                self.puno_valido = False
            if self.puno_valido and not self.puno_disparado:
                progreso = max(progreso, min((t - self.puno_inicio) / espera, 1.0))
                if t - self.puno_inicio >= espera - 1e-9 and not act and p.detectada:
                    pos = self.puntero.posicion_en(self.puno_inicio - self.puntero.rebobinado_s)
                    if pos is not None:
                        self._emitir(acc, [self.puntero.ir_a(*pos)])
                    self._emitir(acc, [Clic(K.DER)])
                    acc.append(Sonido("clic"))
                    self.puno_disparado = True
                    self.puno_bloqueo = t + self.tm["puno_espera"] / 1000.0
                    self._marcar("clic_derecho")
        elif self.puno_inicio is not None and t - self.puno_ult > 0.066:
            self.puno_inicio = None

        # ---- mover el puntero ----
        congelar = act or s == Sena.PUNO or self.puno_inicio is not None and s != Sena.PUNO and t - self.puno_ult <= 0.066
        if self.izq:
            # en cuanto el pellizco empieza a abrirse (pel_salida) el punto de soltar queda quieto
            if s != Sena.PUNO and self.pel_salida is None:
                self._emitir(acc, [self.puntero.mover_anclado(t)])
        elif not congelar:
            self._emitir(acc, [self.puntero.mover(t)])
        if act:
            self._marcar("activar_puesta")
        return progreso

    # --------------------------------------------------- zoom con una mano
    def _zoom_una_mano(self, t, p, s, acc):
        g = self.g
        if s != Sena.PELLIZCO_CORAZON:
            if g.get("salida") is None:
                g["salida"] = t
            if t - g["salida"] >= self.s_pellizco_out - 1e-9:
                self.gesto = None
                self.g = {}
                self.requiere_soltar = True
                self.puntero.reset()
            return
        g["salida"] = None
        y = float((p.img[4, 1] + p.img[12, 1]) / 2.0)
        dy = g["y_ref"] - y              # subir la mano = acercar
        paso = 0.04
        while abs(dy) >= paso:
            d = 1 if dy > 0 else -1
            if not self.traductor.puede_muesca(t):
                g["y_ref"] = y + d * min(abs(dy), 2 * paso)
                break
            self.traductor.gastar_muesca()
            self._emitir(acc, [self.traductor.muesca(d)])
            g["y_ref"] -= d * paso
            dy = g["y_ref"] - y
            self._marcar("acercar" if d > 0 else "alejar")

    # ------------------------------------------------------- dos manos: inicio
    def _sep(self, a, b) -> float:
        d = (np.asarray(a) - np.asarray(b)) * np.array([1.0, 1.0 / self.aspecto])
        return float(np.hypot(d[0], d[1]))

    def _rearme_dos_manos(self, t, pistas):
        if not self.rearme_dos:
            return
        libre = any(p.detectada and p.sena not in (Sena.PELLIZCO, Sena.PUNO, Sena.PELLIZCO_CORAZON)
                    for p in pistas)
        if not libre:
            self.libre2_desde = None
            return
        if self.libre2_desde is None:
            self.libre2_desde = t
        if t - self.libre2_desde >= 0.1 - 1e-9:
            self.rearme_dos = False
            self.libre2_desde = None

    def _candidato_dos_manos(self, t, pistas, acc) -> bool:
        a, b = pistas
        cand = None
        if self.rearme_dos:
            self.par_cand = None
            return False
        if a.detectada and b.detectada:
            if a.sena == Sena.PELLIZCO and b.sena == Sena.PELLIZCO:
                cand = "pinza"
            elif (self.modo == "3D" and a.sena == Sena.PUNO and b.sena == Sena.PUNO
                  and self._sep(a.centro, b.centro) > 0.15):
                cand = "orbita"
        elif self.par_cand is not None:
            # MediaPipe perdió una de las dos manos este cuadro pero su pista sigue viva con la
            # misma seña: no se reinicia el candidato (eso abría la puerta a un clic izquierdo
            # en mitad del zoom); solo no se avanza en este cuadro.
            sena_cand = Sena.PELLIZCO if self.par_cand == "pinza" else Sena.PUNO
            if a.sena == sena_cand and b.sena == sena_cand:
                return False
        if cand != self.par_cand:
            self.par_cand = cand
            self.par_desde = t
        if cand is None:
            return False
        espera = (self.tm["agarre_3d"] if cand == "orbita" else 100) / 1000.0
        if t - self.par_desde < espera - 1e-9:
            return False
        # Empieza el gesto: primero se suelta el botón izquierdo si estaba abajo
        if self.izq:
            self._emitir(acc, [Subir(K.IZQ)])
            self.izq = False
            self.puntero.soltar_ancla(t, 0.0)
        self.pel_desde = None
        self.puno_inicio = None
        self.par_cand = None
        izq_p, der_p = sorted(pistas, key=lambda p: float(p.img[0, 0]))
        self.gesto = cand
        if cand == "pinza":
            self._iniciar_pinza(t, izq_p, der_p)
        else:
            self._iniciar_orbita(t, izq_p, der_p, acc)
        return True

    def _medio_permitido(self, t, pos) -> bool:
        """Evita el doble clic del medio: 600 ms y 10 px desde el último MIDDLEUP."""
        if t - self.t_medio_arriba >= 0.6 - 1e-9:
            return True
        if pos is None or self.pos_medio_arriba is None:
            return False
        return math.hypot(pos[0] - self.pos_medio_arriba[0], pos[1] - self.pos_medio_arriba[1]) > 10

    # ------------------------------------------------ pinza (zoom / desplazar)
    @staticmethod
    def _mitad_pellizco(p):
        """Punto de referencia de cada mano en pinza. Se usa el promedio de los nudillos del
        índice y del corazón (5 y 9): al abrir o cerrar el pellizco las puntas se mueven
        1-2 cm y harían saltar una muesca de más; los nudillos casi no se mueven."""
        return (p.img[5, :2] + p.img[9, :2]) / 2.0

    def _iniciar_pinza(self, t, a, b):
        ma, mb = self._mitad_pellizco(a), self._mitad_pellizco(b)
        d0 = max(self._sep(ma, mb), 1e-4)
        M0 = (ma + mb) / 2.0
        self.g = {"ids": (a.id, b.id), "d0": d0, "d_ref": d0, "M0": M0, "modo": None,
                  "salida": {a.id: None, b.id: None}, "muescas_env": 0.0,
                  "fM": (OneEuro(1.0, 0.02), OneEuro(1.0, 0.02)), "enviado": (0, 0),
                  "M_prev": M0, "M_base": M0, "comb": None, "acum": (0.0, 0.0)}
        self._marcar("dos_manos")

    def _gesto_dos_manos(self, t, pistas, acc):
        g = self.g
        por_id = {p.id: p for p in pistas}
        ids = g["ids"]
        if any(i not in por_id for i in ids):
            self._terminar_gesto(t, acc, "mano perdida")
            return
        a, b = (por_id[i] for i in ids)
        if self.gesto == "pinza":
            self._paso_pinza(t, a, b, acc)
        else:
            self._paso_orbita(t, a, b, acc)

    def _salida_mano(self, t, p, sigue: bool) -> bool:
        sal = self.g["salida"]
        if sigue:
            sal[p.id] = None
            return False
        if sal.get(p.id) is None:
            sal[p.id] = t
        return t - sal[p.id] >= self.s_pellizco_out - 1e-9

    def _paso_pinza(self, t, a, b, acc):
        g = self.g
        fin_a = self._salida_mano(t, a, a.sena == Sena.PELLIZCO)
        fin_b = self._salida_mano(t, b, b.sena == Sena.PELLIZCO)
        if fin_a or fin_b:
            self._terminar_gesto(t, acc, "fin de pinza")
            return
        if not (a.detectada and b.detectada) or a.sena != Sena.PELLIZCO or b.sena != Sena.PELLIZCO:
            return          # una mano se está abriendo: no se mide (evita una muesca al soltar)
        ma, mb = self._mitad_pellizco(a), self._mitad_pellizco(b)
        d = max(self._sep(ma, mb), 1e-4)
        M = (ma + mb) / 2.0
        if g["modo"] is None:
            if abs(math.log(d / g["d0"])) > self.zoom_muerta:
                g["modo"] = "zoom"
            elif self.desplazar_dos_manos and self._sep(M, g["M0"]) > 0.03:
                g["modo"] = "desplazar"
                g["comb"] = self.perfil.combinacion_desplazar(self.modo)
                g["pendiente"] = True
            else:
                return
        if g["modo"] == "zoom":
            self._paso_zoom(t, d, acc)
        else:
            self._paso_desplazar(t, M, acc)

    def _paso_zoom(self, t, d, acc):
        g = self.g
        tr = self.traductor
        L = math.log(d / g["d0"])
        if tr.perfil.rueda_fraccion:
            muescas = L / self.zoom_paso
            delta = muescas - g["muescas_env"]
            nuevas = tr.fraccion(delta)
            g["muescas_env"] = muescas
            if nuevas:
                self._emitir(acc, nuevas)
                self._marcar("acercar" if nuevas[0].delta * tr._signo() > 0 else "alejar")
            return
        L = math.log(d / g["d_ref"])
        paso = self.zoom_paso
        while abs(L) >= paso - 1e-12:
            direc = 1 if L > 0 else -1
            if not tr.puede_muesca(t):
                # como máximo dos muescas pendientes
                if abs(L) > 2 * paso:
                    g["d_ref"] = d * math.exp(-direc * 2 * paso)
                break
            tr.gastar_muesca()
            self._emitir(acc, [tr.muesca(direc)])
            g["d_ref"] *= math.exp(direc * paso)
            L = math.log(d / g["d_ref"])
            self._marcar("acercar" if direc > 0 else "alejar")

    def _paso_desplazar(self, t, M, acc):
        g = self.g
        if g.get("pendiente"):
            pos = self._cursor_real()
            if not self._medio_permitido(t, pos):
                return
            g["pendiente"] = False
            self._emitir(acc, self.traductor.empezar(g["comb"]))
            for f in g["fM"]:
                f.reset()
            g["fM"][0].filtrar(float(g["M0"][0]), t)
            g["fM"][1].filtrar(float(g["M0"][1]), t)
            g["M_base"] = g["M0"]
            g["M_prev"] = M
            self._marcar("desplazar")
        if self._sep(M, g["M_prev"]) > 0.15:          # salto imposible: se descarta y se rebasa
            g["M_prev"] = M
            for f, val in zip(g["fM"], M):
                f.reset()
                f.filtrar(float(val), t)
            g["M_base"] = M
            g["enviado"] = (0, 0)
            g["acum"] = (0.0, 0.0)
            return
        g["M_prev"] = M
        mx = g["fM"][0].filtrar(float(M[0]), t)
        my = g["fM"][1].filtrar(float(M[1]), t)
        objetivo_x = (mx - g["M_base"][0]) * self.mapeo.px_por_unidad_x
        objetivo_y = (my - g["M_base"][1]) * self.mapeo.px_por_unidad_y
        ex, ey = g["enviado"]
        dx, dy = int(round(objetivo_x - ex)), int(round(objetivo_y - ey))
        if dx or dy:
            self._emitir(acc, [MoverDelta(dx, dy)])
            g["enviado"] = (ex + dx, ey + dy)

    # ------------------------------------------------------------- órbita 3D
    def _theta_M(self, a, b):
        ca, cb = a.centro, b.centro
        if ca[0] > cb[0]:
            ca, cb = cb, ca                       # izquierda y derecha EN PANTALLA
        v = cb - ca
        th = math.atan2(float(v[1]) / self.aspecto, float(v[0]))
        return th, (ca + cb) / 2.0

    def _iniciar_orbita(self, t, a, b, acc):
        th, M = self._theta_M(a, b)
        x, y = self.mapeo.a_pantalla(float(M[0]), float(M[1]))
        # Con los puños fuera de la zona activa el punto caería pegado al borde (o sobre la barra
        # de tareas): se lleva a una zona segura. Ahí también se hace el reagarre.
        x0, y0, x1, y1 = self.mapeo.monitor.zona_segura()
        x = min(max(x, x0), x1)
        y = min(max(y, y0), y1)
        self._emitir(acc, [self.puntero.ir_a(x, y)])
        if self.cursor is None:
            self.cursor = (int(round(x)), int(round(y)))
        self.g = {"ids": (a.id, b.id), "estado": "preparando", "t0": t, "agarre": (int(round(x)), int(round(y))),
                  "salida": {a.id: None, b.id: None}, "comb": self.perfil.combinacion_orbitar(self.modo)}
        self._rebasar_orbita(t, th, M)
        self._marcar("girar")

    def _rebasar_orbita(self, t, th, M):
        g = self.g
        g["th_raw"] = th
        g["th_unw"] = g.get("th_unw", th) if "th_unw" in g else th
        g["fth"] = OneEuro(0.8, 0.02)
        g["fM"] = (OneEuro(1.0, 0.02), OneEuro(1.0, 0.02))
        thf = g["fth"].filtrar(g["th_unw"], t)
        g["th_ref"] = thf
        g["M_raw"] = np.asarray(M, float)
        g["M_ref"] = np.array([g["fM"][0].filtrar(float(M[0]), t), g["fM"][1].filtrar(float(M[1]), t)])
        g["resto"] = (0.0, 0.0)

    def _abierta(self, p) -> bool:
        return p.sena == Sena.ABIERTA or p.medidas.extendidos >= 3

    def _paso_orbita(self, t, a, b, acc):
        g = self.g
        fin_a = self._salida_mano(t, a, not self._abierta(a))
        fin_b = self._salida_mano(t, b, not self._abierta(b))
        if fin_a or fin_b:
            self._terminar_gesto(t, acc, "manos abiertas")
            return
        th, M = self._theta_M(a, b)
        M = np.asarray(M, float)
        est = g["estado"]
        if est == "preparando":
            g["th_raw"], g["M_raw"] = th, M
            if t - g["t0"] < 0.02:
                return                                   # se espera un cuadro
            if not self._medio_permitido(t, self._cursor_real()):
                return
            self._emitir(acc, self.traductor.empezar(g["comb"]))
            g["estado"] = "girando"
            g.pop("th_unw", None)
            self._rebasar_orbita(t, th, M)
            return
        if est == "reagarre":
            g["th_raw"], g["M_raw"] = th, M
            if t < g["reagarre_hasta"]:
                return
            self._emitir(acc, self.traductor.empezar(g["comb"]))
            g["estado"] = "girando"
            g.pop("th_unw", None)
            self._rebasar_orbita(t, th, M)
            return
        # girando
        dth_raw = _ang_wrap(th - g["th_raw"])
        dM_raw = float(np.hypot(*((M - g["M_raw"]) * np.array([1.0, 1.0 / self.aspecto]))))
        if a.sospechosa or b.sospechosa or abs(dth_raw) > 0.6 or dM_raw > 0.15 \
                or not (a.detectada and b.detectada):
            # cuadro descartado (MediaPipe confundió las manos o se perdió un cuadro)
            g["th_raw"], g["M_raw"] = th, M
            g["th_unw"] = g["th_unw"]
            g["fth"].reset()
            g["th_ref"] = g["fth"].filtrar(g["th_unw"], t)
            g["fM"] = (OneEuro(1.0, 0.02), OneEuro(1.0, 0.02))
            g["M_ref"] = np.array([g["fM"][0].filtrar(float(M[0]), t), g["fM"][1].filtrar(float(M[1]), t)])
            return
        g["th_raw"], g["M_raw"] = th, M
        g["th_unw"] += dth_raw
        thf = g["fth"].filtrar(g["th_unw"], t)
        Mf = np.array([g["fM"][0].filtrar(float(M[0]), t), g["fM"][1].filtrar(float(M[1]), t)])
        dth = thf - g["th_ref"]
        dM = Mf - g["M_ref"]
        usar_th = abs(dth) >= 0.02
        usar_M = float(np.hypot(*dM)) >= 0.003
        if not usar_th:
            dth = 0.0
        else:
            g["th_ref"] = thf
        if not usar_M:
            dM = np.zeros(2)
        else:
            g["M_ref"] = Mf
        W, H = self.mapeo.monitor.ancho, self.mapeo.monitor.alto
        G = self.ganancia * self.perfil.ganancia_orbita
        dx = G * (self.k_vol * dth * (H / math.pi) + self.k_mov * float(dM[0]) * W)
        dy = G * self.k_mov * float(dM[1]) * H
        n = math.hypot(dx, dy)
        if n > self.max_px:
            dx, dy = dx * self.max_px / n, dy * self.max_px / n
        rx, ry = g["resto"]
        dx += rx
        dy += ry
        ix, iy = int(round(dx)), int(round(dy))
        g["resto"] = (dx - ix, dy - iy)
        if ix or iy:
            self._emitir(acc, [MoverDelta(ix, iy)])
            self._marcar("girar")
        # reagarre automático cerca del borde
        c = self._cursor_real()
        if c is not None:
            m = self.mapeo.monitor
            ag = g["agarre"]
            lejos = math.hypot(c[0] - ag[0], c[1] - ag[1]) >= 20      # nunca reagarrar en el sitio
            if lejos and (c[0] - m.x < 5 or m.x + m.ancho - 1 - c[0] < 5 or c[1] - m.y < 5
                          or m.y + m.alto - 1 - c[1] < 5):
                self._emitir(acc, self.traductor.terminar(g["comb"]))
                self._emitir(acc, [Mover(*g["agarre"])])
                self.puntero.ult_enviado = g["agarre"]
                g["estado"] = "reagarre"
                g["reagarre_hasta"] = t + 0.6

    # --------------------------------------------------------- fin de gesto
    def _terminar_gesto(self, t, acc, motivo):
        g = self.g
        if self.gesto == "pinza" and g.get("modo") == "zoom":
            self._emitir(acc, self.traductor.cerrar_fraccion())
        if self.gesto == "orbita" and g.get("estado") == "girando":
            self._emitir(acc, self.traductor.terminar(g["comb"]))
        elif self.gesto == "pinza" and g.get("modo") == "desplazar" and not g.get("pendiente"):
            self._emitir(acc, self.traductor.terminar(g["comb"]))
        # seguridad: nada puede quedar presionado al terminar un gesto de dos manos
        if self.algo_sostenido():
            self._emitir(acc, [SoltarTodo("fin de gesto")])
        self.gesto = None
        self.g = {}
        self.traductor.vaciar()
        self._pedir_rearme(dos_manos=(motivo == "mano perdida"))
        self.puntero.reset()
        self._marcar("soltar")

    # ------------------------------------------------------------- resultado
    def estado_visible(self) -> str:
        if self.base == K.BLOQUEADO:
            return K.BLOQUEADO
        if self.base == K.PAUSA:
            return K.PAUSA
        if self.sin_mano:
            return K.SIN_MANO
        if self.gesto == "orbita":
            return K.GIRANDO_3D
        if self.gesto == "pinza" and self.g.get("modo") == "desplazar":
            return K.DESPLAZANDO
        if self.izq:
            return K.ARRASTRANDO
        return K.ACTIVO

    def _resultado(self, acc, avisos, progreso) -> Resultado:
        etiqueta = self.etiqueta if self._t - self.etiqueta_t <= 0.8 else ""
        return Resultado(acciones=acc, estado=self.estado_visible(), base=self.base, sub=self.sub,
                         etiqueta=etiqueta, progreso=float(progreso), avisos=avisos,
                         cerca_borde=self.puntero.cerca_borde, modo=self.modo)
