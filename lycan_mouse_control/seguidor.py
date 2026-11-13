"""Identidad estable de cada mano entre cuadros, mano principal y orden por x.

MediaPipe cambia el orden y a veces la etiqueta de las manos: no se confía en ninguno.
Cada pista guarda su propio Clasificador (histéresis por mano).
"""
from __future__ import annotations

import itertools
from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from .mano import ManoDetectada
from .senas import Clasificador, Medidas, Sena

DIST_MAX_ASOCIAR = 0.25     # fracción del ancho de la imagen
SALTO_SOSPECHOSO = 0.15
RETENER_S = 0.150           # una pista sin detección se conserva 150 ms
PREDECIR_S = 0.100          # ... con posición predicha por velocidad hasta 100 ms
VOTOS = 15


def _escala_y(aspecto: float):
    """Las distancias en la imagen se miden en fracción del ANCHO (y se corrige por el aspecto)."""
    return np.array([1.0, 1.0 / aspecto])


@dataclass
class Pista:
    id: int
    img: np.ndarray
    mundo: np.ndarray
    t_visto: float
    clasificador: Clasificador
    votos: deque = field(default_factory=lambda: deque(maxlen=VOTOS))
    vel: np.ndarray = field(default_factory=lambda: np.zeros(2))
    sena: Sena = Sena.NINGUNA
    medidas: Medidas = field(default_factory=Medidas)
    detectada: bool = True
    sospechosa: bool = False
    t_nacio: float = 0.0
    img_base: np.ndarray | None = None   # última img detectada (para predecir)

    @property
    def etiqueta(self) -> str:
        if not self.votos:
            return "Right"
        c = Counter(self.votos)
        if c["Right"] == c["Left"]:
            return self.votos[-1]
        return "Right" if c["Right"] > c["Left"] else "Left"

    @property
    def muneca(self) -> np.ndarray:
        return self.img[0, :2]

    @property
    def centro(self) -> np.ndarray:
        return self.img[[0, 5, 9, 13, 17], :2].mean(axis=0)


class Seguidor:
    def __init__(self, umbrales: dict | None = None, mano_principal: str = "derecha", aspecto: float = 4 / 3):
        self.umbrales = umbrales
        self.mano_principal = mano_principal
        self.aspecto = aspecto
        self.pistas: list[Pista] = []
        self._ids = itertools.count(1)
        self.id_principal: int | None = None

    def reiniciar(self):
        self.pistas.clear()
        self.id_principal = None

    def actualizar_umbrales(self, umbrales: dict):
        self.umbrales = umbrales
        for p in self.pistas:
            p.clasificador.actualizar_umbrales(umbrales)

    def _dist(self, a, b) -> float:
        d = (np.asarray(a, float) - np.asarray(b, float)) * _escala_y(self.aspecto)
        return float(np.hypot(d[0], d[1]))

    def actualizar(self, t: float, manos: list[ManoDetectada]) -> list[Pista]:
        """Asocia las manos del cuadro con las pistas y devuelve las pistas vivas."""
        validas = []
        for m in manos or []:
            img = np.asarray(m.img, float)
            if img.shape != (21, 3) or not np.all(np.isfinite(img[:, :2])):
                continue
            validas.append(m)
        for p in self.pistas:
            p.sospechosa = False

        # Asociación por el punto 9 (base del corazón): se prueba cada permutación (≤ 2 manos).
        libres = list(range(len(self.pistas)))
        asign: dict[int, int] = {}
        if validas and self.pistas:
            mejor = None
            for n in range(min(len(validas), len(self.pistas)), 0, -1):
                mejor_costo = float("inf")
                for idx_p in itertools.permutations(libres, n):
                    for idx_m in itertools.combinations(range(len(validas)), n):
                        costo = 0.0
                        ok = True
                        for ip, im in zip(idx_p, idx_m):
                            d = self._dist(self.pistas[ip].img[9, :2], validas[im].img[9, :2])
                            if d > DIST_MAX_ASOCIAR:
                                ok = False
                                break
                            costo += d
                        if ok and costo < mejor_costo:
                            mejor, mejor_costo = list(zip(idx_m, idx_p)), costo
                if mejor:
                    break
            if mejor:
                asign = dict(mejor)

        usadas = set()
        for im, m in enumerate(validas):
            img = np.asarray(m.img, float)
            mundo = np.asarray(m.mundo, float)
            if im in asign:
                p = self.pistas[asign[im]]
                usadas.add(asign[im])
                dt = max(t - p.t_visto, 1e-3)
                base = p.img_base if p.img_base is not None else p.img
                salto = self._dist(base[9, :2], img[9, :2])
                if salto > SALTO_SOSPECHOSO:
                    p.sospechosa = True
                    p.vel = np.zeros(2)
                else:
                    p.vel = 0.5 * p.vel + 0.5 * (img[9, :2] - base[9, :2]) / dt
                p.img, p.mundo, p.img_base = img, mundo, img
                p.t_visto = t
                p.detectada = True
            else:
                p = Pista(id=next(self._ids), img=img, mundo=mundo, t_visto=t,
                          clasificador=Clasificador(self.umbrales), t_nacio=t, img_base=img)
                self.pistas.append(p)
                usadas.add(len(self.pistas) - 1)
            p.votos.append(m.etiqueta if m.etiqueta in ("Left", "Right") else "Right")
            p.sena = p.clasificador.clasificar(mundo, p.etiqueta)
            p.medidas = p.clasificador.medidas

        # Pistas sin detección: se conservan 150 ms (posición predicha hasta 100 ms).
        vivas = []
        for i, p in enumerate(self.pistas):
            if i in usadas:
                vivas.append(p)
                continue
            edad = t - p.t_visto
            if edad > RETENER_S:
                continue
            p.detectada = False
            if p.img_base is not None:
                tp = min(edad, PREDECIR_S)
                img = p.img_base.copy()
                img[:, 0] += p.vel[0] * tp
                img[:, 1] += p.vel[1] * tp
                p.img = img
            vivas.append(p)
        self.pistas = vivas
        self._elegir_principal()
        return self.pistas

    def _elegir_principal(self):
        if not self.pistas:
            self.id_principal = None
            return
        if len(self.pistas) == 1:
            self.id_principal = self.pistas[0].id
            return
        quiero = "Right" if self.mano_principal == "derecha" else "Left"
        coinciden = [p for p in self.pistas if p.etiqueta == quiero]
        if len(coinciden) == 1:
            self.id_principal = coinciden[0].id
            return
        actual = self.principal
        if actual is not None:
            return  # empate: se conserva la que ya era principal
        ordenadas = self.por_x()
        self.id_principal = (ordenadas[-1] if quiero == "Right" else ordenadas[0]).id

    @property
    def principal(self) -> Pista | None:
        for p in self.pistas:
            if p.id == self.id_principal:
                return p
        return None

    def otras(self) -> list[Pista]:
        return [p for p in self.pistas if p.id != self.id_principal]

    def por_x(self) -> list[Pista]:
        """Manos ordenadas por la x de la muñeca: [izquierda en pantalla, derecha en pantalla]."""
        return sorted(self.pistas, key=lambda p: float(p.img[0, 0]))
