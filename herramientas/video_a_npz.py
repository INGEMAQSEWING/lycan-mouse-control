"""Pasa un video grabado (.mp4) por el detector y guarda los puntos de la mano en .npz,
con el mismo formato que ``grabar.py`` (no guarda imágenes).

El video se voltea en espejo (como hace ``captura.py`` con la cámara en vivo): la app de Cámara
de Windows guarda el video SIN espejo.

Uso:
    py -3.10 herramientas\\video_a_npz.py VIDEO.mp4 --sena subir --salida pruebas\\datos_reales
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


def convertir(video: str, sena: str, salida: str, espejo: bool = True, ancho: int = 640) -> str:
    import cv2
    from lycan_mouse_control.detector import Detector
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    det = Detector(max_manos=2)
    img, mundo, n, etq, ts = [], [], [], [], []
    k = 0
    while True:
        ok, im = cap.read()
        if not ok:
            break
        h, w = im.shape[:2]
        im = cv2.resize(im, (ancho, int(round(h * ancho / w))))
        if espejo:
            im = cv2.flip(im, 1)
        manos = det.procesar(im)
        a = np.full((2, 21, 3), np.nan)
        b = np.full((2, 21, 3), np.nan)
        e = ["", ""]
        for i, m in enumerate(manos[:2]):
            a[i], b[i], e[i] = m.img, m.mundo, m.etiqueta
        img.append(a)
        mundo.append(b)
        n.append(len(manos))
        etq.append(e)
        ts.append(k / fps)
        k += 1
    cap.release()
    det.cerrar()
    os.makedirs(salida, exist_ok=True)
    nombre = os.path.join(salida, f"{sena}.npz")
    np.savez_compressed(nombre, img=np.array(img), mundo=np.array(mundo), n_manos=np.array(n),
                        etiquetas=np.array(etq), t=np.array(ts), sena_pedida=np.array(sena))
    return nombre


def main():
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--sena", required=True)
    p.add_argument("--salida", default=os.path.join(RAIZ, "pruebas", "datos_reales"))
    p.add_argument("--sin-espejo", action="store_true")
    a = p.parse_args()
    print("Guardado:", convertir(a.video, a.sena, a.salida, espejo=not a.sin_espejo))


if __name__ == "__main__":
    main()
