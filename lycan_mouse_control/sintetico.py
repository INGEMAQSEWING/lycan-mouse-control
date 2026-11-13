"""Generador de manos sintéticas (sin cámara) para pruebas, para el asistente y para los
dibujos de la chuleta de señas.

Modelo cinemático simple de la mano DERECHA en metros, en un marco local:
  x lateral (el pulgar queda hacia -x), y a lo largo de los dedos (los dedos apuntan a -y,
  "hacia arriba" en la imagen), z normal a la palma (-z = lado de la palma, hacia la cámara).
La mano izquierda es el reflejo en x. Se proyecta con una cámara estenopeica de 640x480.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .mano import ManoDetectada

# ---- Medidas de la mano (metros) ----
MCP = {
    "indice": (-0.025, -0.085, 0.0),
    "corazon": (-0.004, -0.088, 0.0),
    "anular": (0.016, -0.083, 0.0),
    "menique": (0.034, -0.073, 0.0),
}
LARGOS = {
    "indice": (0.040, 0.025, 0.021),
    "corazon": (0.045, 0.028, 0.022),
    "anular": (0.042, 0.027, 0.021),
    "menique": (0.032, 0.020, 0.018),
}
CMC_PULGAR = (-0.022, -0.028, -0.008)
LARGOS_PULGAR = (0.040, 0.034, 0.029)
INDICES = {"indice": (5, 6, 7, 8), "corazon": (9, 10, 11, 12), "anular": (13, 14, 15, 16),
           "menique": (17, 18, 19, 20)}

ANCHO_IMG, ALTO_IMG = 640, 480
FOCAL_PX = 600.0


def _unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


@dataclass
class Postura:
    """dedos: nombre -> (separación lateral °, flexión MCP °, PIP °, DIP °).
    pulgar: ('angulos', dirección, (f1, f2, f3)) o ('objetivo', nombre_objetivo)."""
    dedos: dict
    pulgar: tuple
    nombre: str = ""


_DOBLADO = (90.0, 100.0, 65.0)


def _d(sep, ang):
    return (sep,) + tuple(ang)


POSTURAS: dict[str, Postura] = {
    "abierta": Postura(
        {"indice": (-8, 5, 5, 3), "corazon": (0, 5, 5, 3), "anular": (8, 5, 5, 3), "menique": (16, 5, 5, 3)},
        ("angulos", (-0.8, -0.55, -0.2), (5, 5, 5)), "abierta"),
    "puno": Postura(
        {"indice": _d(-3, _DOBLADO), "corazon": _d(0, _DOBLADO), "anular": _d(3, _DOBLADO),
         "menique": _d(6, _DOBLADO)},
        ("objetivo", "sobre_falanges"), "puno"),
    "apuntar": Postura(
        {"indice": (-3, 5, 5, 3), "corazon": _d(0, _DOBLADO), "anular": _d(3, _DOBLADO),
         "menique": _d(6, _DOBLADO)},
        ("objetivo", "sobre_corazon"), "apuntar"),
    "pellizco": Postura(
        {"indice": (-5, 40, 45, 25), "corazon": (0, 30, 40, 20), "anular": (4, 35, 45, 25),
         "menique": (8, 40, 50, 25)},
        ("objetivo", "punta_indice"), "pellizco"),
    "pellizco_corazon": Postura(
        {"indice": (-6, 5, 5, 3), "corazon": (0, 40, 45, 25), "anular": (4, 30, 35, 20),
         "menique": (8, 30, 35, 20)},
        ("objetivo", "punta_corazon"), "pellizco_corazon"),
    "juntos": Postura(
        {"indice": (2, 5, 5, 3), "corazon": (-2, 5, 5, 3), "anular": _d(3, _DOBLADO),
         "menique": _d(6, _DOBLADO)},
        ("objetivo", "sobre_anular"), "juntos"),
    "v": Postura(
        {"indice": (-15, 5, 5, 3), "corazon": (15, 5, 5, 3), "anular": _d(3, _DOBLADO),
         "menique": _d(6, _DOBLADO)},
        ("objetivo", "sobre_anular"), "v"),
    "relajada": Postura(
        {"indice": (-4, 20, 30, 15), "corazon": (0, 20, 30, 15), "anular": (4, 20, 30, 15),
         "menique": (8, 20, 30, 15)},
        ("angulos", (-0.6, -0.7, -0.3), (10, 10, 10)), "relajada"),
}

# Seña que debe dar el clasificador para cada postura (relajada: cualquiera sin acción)
SENA_ESPERADA = {
    "abierta": "ABIERTA", "puno": "PUNO", "apuntar": "APUNTAR", "pellizco": "PELLIZCO",
    "pellizco_corazon": "PELLIZCO_CORAZON", "juntos": "ACTIVAR", "v": "V",
}


def _dedo(nombre, sep, mcp, pip, dip):
    base = np.array(MCP[nombre], float)
    s = math.radians(sep)
    u = np.array([math.sin(s), -math.cos(s), 0.0])
    zpal = np.array([0.0, 0.0, -1.0])
    pts = [base]
    acum = 0.0
    p = base.copy()
    for largo, fl in zip(LARGOS[nombre], (mcp, pip, dip)):
        acum += math.radians(fl)
        d = math.cos(acum) * u + math.sin(acum) * zpal
        p = p + largo * d
        pts.append(p)
    return pts


def _pulgar_angulos(direccion, flex):
    b = _unit(direccion)
    # se dobla hacia la palma (hacia el meñique y hacia la cámara)
    e = np.array([0.6, 0.0, -0.8])
    e = _unit(e - np.dot(e, b) * b)
    p = np.array(CMC_PULGAR, float)
    pts = [p]
    acum = 0.0
    for largo, f in zip(LARGOS_PULGAR, flex):
        acum += math.radians(f)
        p = p + largo * (math.cos(acum) * b + math.sin(acum) * e)
        pts.append(p)
    return pts


def _pulgar_objetivo(objetivo):
    p0 = np.array(CMC_PULGAR, float)
    t = np.asarray(objetivo, float)
    d = t - p0
    largo = np.linalg.norm(d)
    # se curva hacia afuera (-x) y hacia la cámara, como un pulgar real
    bulto = np.array([-0.7, 0.2, -0.5])
    bulto = _unit(bulto - np.dot(bulto, _unit(d)) * _unit(d))
    pts = [p0]
    for f in (0.38, 0.72):
        pts.append(p0 + f * d + 0.18 * largo * math.sin(math.pi * f) * bulto)
    pts.append(t)
    return pts


def _objetivo(nombre, P):
    zc = np.array([0.0, 0.0, -1.0])
    if nombre == "punta_indice":
        return P[8] + np.array([-0.006, 0.0, 0.0])
    if nombre == "punta_corazon":
        return P[12] + np.array([-0.006, 0.0, 0.0])
    if nombre == "sobre_falanges":
        return (P[6] + P[10]) / 2.0 + np.array([0.004, 0.008, 0.002])
    if nombre == "sobre_corazon":
        return P[10] + np.array([0.0, 0.004, 0.0]) + 0.012 * zc
    if nombre == "sobre_anular":
        return (P[10] + P[14]) / 2.0 + np.array([0.0, 0.006, 0.0]) + 0.012 * zc
    raise ValueError(nombre)


def _construir_dedos(dedos: dict) -> np.ndarray:
    P = np.zeros((21, 3))
    for nombre, (sep, a, b, c) in dedos.items():
        for i, p in zip(INDICES[nombre], _dedo(nombre, sep, a, b, c)):
            P[i] = p
    return P


def construir(postura: str | Postura) -> np.ndarray:
    """21x3 en metros, marco local, mano derecha, muñeca en el origen."""
    pos = POSTURAS[postura] if isinstance(postura, str) else postura
    P = _construir_dedos(pos.dedos)
    if pos.pulgar[0] == "angulos":
        pul = _pulgar_angulos(pos.pulgar[1], pos.pulgar[2])
    else:
        pul = _pulgar_objetivo(_objetivo(pos.pulgar[1], P))
    for i, p in zip((1, 2, 3, 4), pul):
        P[i] = p
    return P


def intermedia(a: str, b: str, t: float) -> np.ndarray:
    """Transición entre dos posturas: ángulos de los dedos interpolados; pulgar mezclado."""
    pa, pb = POSTURAS[a], POSTURAS[b]
    t = min(max(float(t), 0.0), 1.0)
    dedos = {k: tuple((1 - t) * x + t * y for x, y in zip(pa.dedos[k], pb.dedos[k])) for k in pa.dedos}
    P = _construir_dedos(dedos)
    A, B = construir(pa), construir(pb)
    P[1:5] = (1 - t) * A[1:5] + t * B[1:5]
    return P


def rotacion(rx: float, ry: float, rz: float) -> np.ndarray:
    """Matriz de rotación (grados) Rz·Ry·Rx."""
    ax, ay, az = (math.radians(v) for v in (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def proyectar(P_cam: np.ndarray, ancho=ANCHO_IMG, alto=ALTO_IMG, focal=FOCAL_PX) -> np.ndarray:
    """Puntos en metros en el marco de la cámara -> 0..1 de la imagen."""
    Z = np.maximum(P_cam[:, 2], 0.05)
    u = (focal * P_cam[:, 0] / Z + ancho / 2.0) / ancho
    v = (focal * P_cam[:, 1] / Z + alto / 2.0) / alto
    z = (P_cam[:, 2] - P_cam[0, 2]) / 0.5
    return np.stack([u, v, z], axis=1)


@dataclass
class Variacion:
    escala: float = 1.0
    rot: tuple = (0.0, 0.0, 0.0)
    ruido_mm: float = 0.0
    lado: str = "Right"
    faltante: bool = False


def variacion_aleatoria(rng: np.random.Generator, ruido_mm: float = 2.0, rot_max: float = 40.0,
                        permitir_izquierda: bool = True) -> Variacion:
    return Variacion(
        escala=float(rng.uniform(0.7, 1.3)),
        rot=tuple(float(x) for x in rng.uniform(-rot_max, rot_max, 3)),
        ruido_mm=ruido_mm,
        lado=("Left" if (permitir_izquierda and rng.random() < 0.5) else "Right"),
    )


def mano(postura: str | Postura | np.ndarray = "abierta", *, lado: str = "Right", escala: float = 1.0,
         rot=(0.0, 0.0, 0.0), ruido_mm: float = 0.0, rng: np.random.Generator | None = None,
         distancia_m: float = 0.5, posicion=(0.5, 0.5), ancla: int | str = 8, faltante: bool = False,
         variacion: Variacion | None = None, confianza: float = 0.95) -> ManoDetectada:
    """Crea una ManoDetectada sintética.

    posicion: dónde cae el punto ``ancla`` en la imagen (0..1, imagen en espejo).
    ancla: índice del punto (8 = punta del índice) o "centro" (centro de la palma).
    """
    if variacion is not None:
        lado, escala, rot, ruido_mm, faltante = (variacion.lado, variacion.escala, variacion.rot,
                                                 variacion.ruido_mm, variacion.faltante)
    P = postura.copy() if isinstance(postura, np.ndarray) else construir(postura)
    P = P * float(escala)
    if lado == "Left":
        P[:, 0] = -P[:, 0]
    R = rotacion(*rot)
    centro = P[[0, 5, 9, 13, 17]].mean(axis=0)
    P = (P - centro) @ R.T
    if ruido_mm > 0:
        rng = rng if rng is not None else np.random.default_rng(1234)
        P = P + rng.normal(0.0, ruido_mm / 1000.0, P.shape)
    if faltante:
        rng = rng if rng is not None else np.random.default_rng(1234)
        dedo = INDICES[["indice", "corazon", "anular", "menique"][int(rng.integers(0, 4))]]
        P[dedo[3]] = P[dedo[3]] + rng.normal(0.0, 0.03, 3)
    mundo = P.copy()
    cam = P + np.array([0.0, 0.0, float(distancia_m)])
    img = proyectar(cam)
    if ancla == "centro":
        ref = img[[0, 5, 9, 13, 17], :2].mean(axis=0)
    else:
        ref = img[int(ancla), :2]
    img[:, 0] += posicion[0] - ref[0]
    img[:, 1] += posicion[1] - ref[1]
    return ManoDetectada(img=img, mundo=mundo, etiqueta=lado, confianza=confianza)


def mover_mano(m: ManoDetectada, dx: float, dy: float) -> ManoDetectada:
    img = m.img.copy()
    img[:, 0] += dx
    img[:, 1] += dy
    return ManoDetectada(img=img, mundo=m.mundo.copy(), etiqueta=m.etiqueta, confianza=m.confianza)


def dibujo_postura(postura: str, tam: int = 48, lado: str = "Right"):
    """Lista de segmentos ((x1,y1),(x2,y2)) en píxeles de un cuadro tam x tam (para la chuleta)."""
    from .constantes import CONEXIONES
    P = construir(postura)
    if lado == "Left":
        P[:, 0] = -P[:, 0]
    # vista frontal ligeramente girada para que el pulgar se vea
    P = P @ rotacion(0, 20, 0).T
    xy = P[:, :2]
    mn, mx = xy.min(axis=0), xy.max(axis=0)
    esc = (tam - 8) / max(float((mx - mn).max()), 1e-6)
    xy = (xy - (mn + mx) / 2.0) * esc + tam / 2.0
    return [((float(xy[a, 0]), float(xy[a, 1])), (float(xy[b, 0]), float(xy[b, 1]))) for a, b in CONEXIONES]
