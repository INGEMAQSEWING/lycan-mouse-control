"""Mide los cuadros por segundo reales con la cámara y MediaPipe (sin mover el ratón).

Uso:
    py -3.10 herramientas\\medir_fps.py --segundos 15 --manos 2
    py -3.10 herramientas\\medir_fps.py --segundos 15 --manos 1

Sirve para la "compuerta de rendimiento" (especificación 3.3): si con 2 manos en 2D no se
llega a 25 cuadros/s, el modo 2D debe pasar a 1 mano. Imprime un JSON con los resultados.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lycan_mouse_control.sistema import dpi  # noqa: E402

dpi.activar()

from lycan_mouse_control.captura import Camara  # noqa: E402
from lycan_mouse_control.config import por_defecto  # noqa: E402
from lycan_mouse_control.detector import Detector  # noqa: E402
from lycan_mouse_control.nucleo import Nucleo  # noqa: E402


def medir(segundos: float, manos: int, camara: int = 0) -> dict:
    try:
        import psutil
        proc = psutil.Process()
        proc.cpu_percent(None)
    except ImportError:
        proc = None
    cam = Camara(camara)
    cam.start()
    det = Detector(max_manos=manos)
    nucleo = Nucleo(por_defecto())
    t_ini = time.perf_counter()
    while cam.estado != "FUNCIONANDO" and time.perf_counter() - t_ini < 10:
        time.sleep(0.05)
    if cam.estado != "FUNCIONANDO":
        cam.detener()
        return {"error": f"la cámara no abrió ({cam.estado})"}
    n, num, con_manos = 0, 0, 0
    tiempos_mp, latencias = [], []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < segundos:
        c = cam.ultimo(num, espera=0.2)
        if c is None:
            continue
        num = c.numero
        ms = det.procesar(c.imagen)
        nucleo.procesar(c.t_captura, ms)
        tiempos_mp.append(det.ms_ultimo)
        latencias.append((time.perf_counter() - c.t_captura) * 1000)
        n += 1
        con_manos += 1 if ms else 0
    dur = time.perf_counter() - t0
    cpu = proc.cpu_percent(None) if proc else None
    mem = proc.memory_info().rss / 1e6 if proc else None
    cam.detener()
    det.cerrar()
    latencias.sort()
    return {
        "max_manos": manos, "segundos": round(dur, 1), "cuadros": n,
        "cuadros_por_segundo": round(n / dur, 1),
        "camara_cuadros_por_segundo": round(cam.fps_reales, 1),
        "cuadros_con_manos": con_manos,
        "mediapipe_ms_medio": round(sum(tiempos_mp) / max(len(tiempos_mp), 1), 1),
        "latencia_media_ms": round(sum(latencias) / max(len(latencias), 1), 1),
        "latencia_p95_ms": round(latencias[int(0.95 * (len(latencias) - 1))], 1) if latencias else None,
        "cpu_proceso_pct": cpu, "memoria_mb": round(mem, 0) if mem else None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--segundos", type=float, default=15)
    p.add_argument("--manos", type=int, default=2, choices=(1, 2))
    p.add_argument("--camara", type=int, default=0)
    a = p.parse_args()
    r = medir(a.segundos, a.manos, a.camara)
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
