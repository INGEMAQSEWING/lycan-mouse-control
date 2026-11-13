"""Graba sesiones reales para pruebas de regresión y para ajustar los umbrales de fábrica
con datos de la cámara del portátil (especificación 11.6, punto 15). No guarda imágenes.

Uso:
    py -3.10 herramientas\\grabar.py --sena pellizco --segundos 6
    py -3.10 herramientas\\grabar.py --guion          (pide las señas una por una)

Cada archivo .npz queda en grabaciones\\ con:
    img (N x máx 2 x 21 x 3), mundo (N x máx 2 x 21 x 3), n_manos (N), etiquetas (N x 2),
    t (N), sena_pedida (texto).
Luego se puede reproducir con ``reproducir(ruta)`` en una prueba.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

SENAS_GUION = [("abierta", "Abra la mano"), ("puno", "Cierre el puño"), ("pellizco", "Junte pulgar e índice"),
               ("juntos", "Junte índice y corazón"), ("v", "Haga la V"), ("apuntar", "Apunte con el índice"),
               ("dos_punos", "Dos manos en puño"), ("dos_pellizcos", "Dos manos en pellizco")]


def grabar(sena: str, segundos: float, camara: int = 0, carpeta: str | None = None) -> str:
    from lycan_mouse_control.captura import Camara
    from lycan_mouse_control.detector import Detector
    carpeta = carpeta or os.path.join(RAIZ, "grabaciones")
    os.makedirs(carpeta, exist_ok=True)
    cam = Camara(camara)
    cam.start()
    det = Detector(max_manos=2)
    while cam.estado != "FUNCIONANDO":
        time.sleep(0.05)
    img, mundo, n, etq, ts = [], [], [], [], []
    num = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < segundos:
        c = cam.ultimo(num, 0.2)
        if c is None:
            continue
        num = c.numero
        manos = det.procesar(c.imagen)
        a = np.full((2, 21, 3), np.nan)
        b = np.full((2, 21, 3), np.nan)
        e = ["", ""]
        for i, m in enumerate(manos[:2]):
            a[i], b[i], e[i] = m.img, m.mundo, m.etiqueta
        img.append(a)
        mundo.append(b)
        n.append(len(manos))
        etq.append(e)
        ts.append(c.t_captura - t0)
    cam.detener()
    det.cerrar()
    nombre = os.path.join(carpeta, f"{sena}-{time.strftime('%Y%m%d-%H%M%S')}.npz")
    np.savez_compressed(nombre, img=np.array(img), mundo=np.array(mundo), n_manos=np.array(n),
                        etiquetas=np.array(etq), t=np.array(ts), sena_pedida=np.array(sena))
    return nombre


def reproducir(ruta: str):
    """Devuelve una lista de (t, [ManoDetectada]) para pasar por el Nucleo en una prueba."""
    from lycan_mouse_control.mano import ManoDetectada
    d = np.load(ruta)
    out = []
    for k in range(len(d["t"])):
        manos = [ManoDetectada(d["img"][k, i], d["mundo"][k, i], str(d["etiquetas"][k, i]))
                 for i in range(int(d["n_manos"][k]))]
        out.append((float(d["t"][k]), manos))
    return out, str(d["sena_pedida"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sena", default="abierta")
    p.add_argument("--segundos", type=float, default=6.0)
    p.add_argument("--camara", type=int, default=0)
    p.add_argument("--guion", action="store_true")
    a = p.parse_args()
    if a.guion:
        for sena, texto in SENAS_GUION:
            input(f"\n{texto}. Presione Enter y sostenga la seña {a.segundos:.0f} segundos...")
            print("Guardado:", grabar(sena, a.segundos, a.camara))
    else:
        print("Guardado:", grabar(a.sena, a.segundos, a.camara))


if __name__ == "__main__":
    main()
