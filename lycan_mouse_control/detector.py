"""MediaPipe Hands -> lista de ManoDetectada (puntos de imagen y en metros)."""
from __future__ import annotations

import time

import numpy as np

from .mano import ManoDetectada


def _sin_matplotlib():
    """mediapipe.solutions.drawing_utils importa matplotlib sin usarlo: se evita cargarlo."""
    import sys
    import types
    if "matplotlib" not in sys.modules:
        try:
            import importlib.util
            if importlib.util.find_spec("matplotlib") is not None:
                return
        except (ImportError, ValueError):
            pass
        mpl = types.ModuleType("matplotlib")
        plt = types.ModuleType("matplotlib.pyplot")
        mpl.pyplot = plt
        sys.modules["matplotlib"] = mpl
        sys.modules["matplotlib.pyplot"] = plt


class Detector:
    def __init__(self, max_manos: int = 2, complejidad: int = 0, deteccion: float = 0.6, seguimiento: float = 0.5):
        _sin_matplotlib()
        import mediapipe as mp
        self.max_manos = max_manos
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False, model_complexity=complejidad, max_num_hands=max_manos,
            min_detection_confidence=deteccion, min_tracking_confidence=seguimiento)
        self.t_fin = 0.0
        self.ms_ultimo = 0.0

    def procesar(self, imagen_bgr: np.ndarray) -> list[ManoDetectada]:
        import cv2
        t0 = time.perf_counter()
        rgb = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        res = self._hands.process(rgb)
        self.t_fin = time.perf_counter()
        self.ms_ultimo = (self.t_fin - t0) * 1000.0
        out: list[ManoDetectada] = []
        if not res.multi_hand_landmarks:
            return out
        mundos = res.multi_hand_world_landmarks or []
        lados = res.multi_handedness or []
        for i, lm in enumerate(res.multi_hand_landmarks):
            img = np.array([(p.x, p.y, p.z) for p in lm.landmark], dtype=float)
            if i < len(mundos):
                mundo = np.array([(p.x, p.y, p.z) for p in mundos[i].landmark], dtype=float)
            else:
                mundo = img.copy()
            etiqueta, conf = "Right", 0.0
            if i < len(lados) and lados[i].classification:
                c = lados[i].classification[0]
                etiqueta, conf = c.label, float(c.score)
            out.append(ManoDetectada(img=img, mundo=mundo, etiqueta=etiqueta, confianza=conf))
        return out

    def cerrar(self):
        try:
            self._hands.close()
        except Exception:  # noqa: BLE001
            pass
