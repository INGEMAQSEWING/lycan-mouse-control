"""Hilo de la cámara: lee sin parar y guarda SOLO el último cuadro (nunca hace cola).

- Abre con DirectShow; si en 2 s no entrega cuadros, prueba Media Foundation.
- Pide 640x480 a 30 cuadros/s y BUFFERSIZE=1. Prueba MJPG; si va más lento, vuelve al formato normal.
- Voltea la imagen (espejo) UNA sola vez, aquí. Nunca se vuelve a invertir x en otro lugar.
- 15 lecturas fallidas seguidas = cámara perdida: avisa y reintenta abrir cada 2 s.
- Si al abrir entrega menos de 8 cuadros/s, casi siempre es porque otro programa (Zoom, Teams,
  Cámara) la está usando: se suelta (estado OCUPADA) y se reintenta cada 2,5 s. Tras 3 intentos
  se usa igual (puede ser poca luz). Si ya abierta se queda por debajo de 8 cuadros/s más de 5 s,
  se suelta y se vuelve a abrir (con espera creciente entre reaperturas).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("lycan")

ABRIENDO, FUNCIONANDO, NO_ABRE, PERDIDA, DETENIDA = "ABRIENDO", "FUNCIONANDO", "NO_ABRE", "PERDIDA", "DETENIDA"
OCUPADA = "OCUPADA"


@dataclass
class Cuadro:
    imagen: np.ndarray     # BGR, ya en espejo
    t_captura: float       # time.perf_counter()
    numero: int


class Camara(threading.Thread):
    FPS_MIN = 8.0             # por debajo: cámara compartida u ocupada
    INTENTOS_LENTA = 3        # aperturas lentas seguidas antes de usarla igual
    ESPERA_OCUPADA_S = 2.5
    MEDIR_S = 1.5             # tope de tiempo de cada medición de cuadros/s
    LENTA_S = 5.0             # tiempo por debajo de FPS_MIN antes de reabrir
    REABRIR_MIN_S = 20.0      # espera mínima entre reaperturas por lentitud (se duplica)

    def __init__(self, indice: int = 0, ancho: int = 640, alto: int = 480, fps: int = 30):
        super().__init__(daemon=True, name="camara")
        self.indice, self.ancho, self.alto, self.fps_pedidos = indice, ancho, alto, fps
        self._lock = threading.Lock()
        self._nuevo = threading.Condition(self._lock)
        self._cuadro: Cuadro | None = None
        self._parar = threading.Event()
        self.estado = ABRIENDO
        self.cap = None
        self.backend = ""
        self.fps_reales = 0.0
        self._n = 0
        self.al_perder = None   # callback() cuando se pierde la cámara
        self.fps_al_abrir = 0.0
        self._intentos_lentos = 0
        self._espera_reabrir = self.REABRIR_MIN_S
        self._t_reabierta = -1e9

    # ---- apertura ----
    def _abrir(self) -> bool:
        import cv2
        for nombre, api in (("DirectShow", cv2.CAP_DSHOW), ("Media Foundation", cv2.CAP_MSMF)):
            if self._parar.is_set():
                return False
            try:
                cap = cv2.VideoCapture(self.indice, api)
            except Exception:  # noqa: BLE001
                continue
            if not cap or not cap.isOpened():
                try:
                    cap.release()
                except Exception:  # noqa: BLE001
                    pass
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.ancho)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.alto)
            cap.set(cv2.CAP_PROP_FPS, self.fps_pedidos)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self._entrega(cap, 2.0):
                fps = self._probar_mjpg(cap)
                self.fps_al_abrir = fps
                if 0.0 <= fps < self.FPS_MIN and self._intentos_lentos < self.INTENTOS_LENTA - 1:
                    self._intentos_lentos += 1
                    log.warning("Cámara %d: solo %.1f cuadros/s al abrir; parece compartida u ocupada "
                                "por otro programa. Se suelta y se reintenta.", self.indice, fps)
                    try:
                        cap.release()
                    except Exception:  # noqa: BLE001
                        pass
                    self.estado = OCUPADA
                    return False
                if fps < self.FPS_MIN:
                    log.warning("Cámara %d: sigue lenta (%.1f cuadros/s); se usa igual.", self.indice, fps)
                self._intentos_lentos = 0
                self.cap = cap
                self.backend = nombre
                log.info("Cámara %d abierta con %s (%dx%d)", self.indice, nombre,
                         int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                return True
            cap.release()
        return False

    def _entrega(self, cap, segundos: float) -> bool:
        fin = time.perf_counter() + segundos
        while time.perf_counter() < fin and not self._parar.is_set():
            ok, img = cap.read()
            if ok and img is not None and img.size:
                return True
            time.sleep(0.05)
        return False

    def _medir(self, cap, n=12) -> float:
        """Cuadros/s en hasta ``n`` lecturas o MEDIR_S segundos (lo que pase primero): con una
        cámara compartida a 1 cuadro/s, 12 lecturas tardaban 12 s."""
        t0 = time.perf_counter()
        k = 0
        for _ in range(n):
            ok, _img = cap.read()
            if ok:
                k += 1
            if time.perf_counter() - t0 > self.MEDIR_S or self._parar.is_set():
                break
        dt = time.perf_counter() - t0
        return k / dt if dt > 0 else 0.0

    def _probar_mjpg(self, cap) -> float:
        """Prueba MJPG y deja el formato más rápido. Devuelve los cuadros/s que quedaron."""
        import cv2
        try:
            antes = self._medir(cap)
            fourcc_prev = cap.get(cv2.CAP_PROP_FOURCC)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            despues = self._medir(cap)
            if despues + 2 < antes:
                cap.set(cv2.CAP_PROP_FOURCC, fourcc_prev)
            log.info("Cámara: %.1f cuadros/s normal, %.1f con MJPG", antes, despues)
            return max(antes, despues)
        except Exception:  # noqa: BLE001
            return -1.0      # no se pudo medir: no se descarta la cámara

    # ---- bucle ----
    def run(self):
        import cv2
        while not self._parar.is_set():
            self.estado = ABRIENDO
            if not self._abrir():
                if self.estado == OCUPADA:
                    if self._parar.wait(self.ESPERA_OCUPADA_S):
                        break
                    continue
                self.estado = NO_ABRE if self._n == 0 else PERDIDA
                if self._parar.wait(2.0):
                    break
                continue
            self.estado = FUNCIONANDO
            fallos = 0
            t_fps, n_fps = time.perf_counter(), 0
            t_lenta = None
            while not self._parar.is_set():
                ok, img = self.cap.read()
                if not ok or img is None:
                    fallos += 1
                    if fallos >= 15:
                        self.estado = PERDIDA
                        log.warning("La cámara se desconectó. Reintentando…")
                        if self.al_perder:
                            try:
                                self.al_perder()
                            except Exception:  # noqa: BLE001
                                pass
                        break
                    time.sleep(0.02)
                    continue
                fallos = 0
                img = cv2.flip(img, 1)   # espejo: UNA sola vez, aquí
                t = time.perf_counter()
                with self._nuevo:
                    self._n += 1
                    self._cuadro = Cuadro(img, t, self._n)
                    self._nuevo.notify_all()
                n_fps += 1
                if t - t_fps >= 1.0:
                    self.fps_reales = n_fps / (t - t_fps)
                    t_fps, n_fps = t, 0
                    if self._lenta_hay_que_reabrir(t, t_lenta):
                        break
                    t_lenta = (t_lenta or t) if self.fps_reales < self.FPS_MIN else None
            try:
                self.cap.release()
            except Exception:  # noqa: BLE001
                pass
            self.cap = None
            if not self._parar.is_set():
                self._parar.wait(2.0)
        self.estado = DETENIDA

    def _lenta_hay_que_reabrir(self, t: float, t_lenta) -> bool:
        """Lenta más de LENTA_S: se suelta y se vuelve a abrir (el otro programa pudo soltarla).
        Entre reaperturas se espera cada vez el doble (para no cortar la imagen sin fin si es
        poca luz)."""
        if t_lenta is None or self.fps_reales >= self.FPS_MIN or t - t_lenta < self.LENTA_S:
            return False
        if t - self._t_reabierta < self._espera_reabrir:
            return False
        log.warning("Cámara a %.1f cuadros/s por más de %.0f s: se vuelve a abrir.", self.fps_reales,
                    self.LENTA_S)
        if self._t_reabierta > 0:
            self._espera_reabrir = min(self._espera_reabrir * 2, 300.0)
        self._t_reabierta = t
        self._intentos_lentos = 0
        return True

    def ultimo(self, despues_de: int = 0, espera: float = 0.1) -> Cuadro | None:
        """El cuadro más reciente con número > despues_de (espera hasta ``espera`` s)."""
        with self._nuevo:
            if self._cuadro is None or self._cuadro.numero <= despues_de:
                self._nuevo.wait(espera)
            c = self._cuadro
        if c is None or c.numero <= despues_de:
            return None
        return c

    def detener(self):
        self._parar.set()
        with self._nuevo:
            self._nuevo.notify_all()


def probar_indices(maximo: int = 4) -> list[int]:
    """Índices de cámara que abren (para Opciones). Tarda unos segundos."""
    import cv2
    out = []
    for i in range(maximo):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    out.append(i)
        finally:
            cap.release()
    return out
