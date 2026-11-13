"""Perfiles por programa y traductor de acciones abstractas (orbitar, desplazar, rueda)
a acciones concretas con el orden y las esperas correctas.

Regla: las teclas (Shift) bajan ANTES que el botón y suben DESPUÉS; los botones suben en
orden inverso al que bajaron (FreeCAD: izquierdo arriba antes que el medio).
"""
from __future__ import annotations

import fnmatch
import math
import ntpath
from dataclasses import dataclass, field

from .acciones import Bajar, Esperar, Rueda, Subir, Tecla
from .constantes import WHEEL_DELTA


@dataclass(frozen=True)
class Combinacion:
    botones: tuple = ("medio",)
    teclas: tuple = ()

    def describir(self) -> str:
        nombres = {"medio": "botón del medio", "izq": "botón izquierdo", "der": "botón derecho",
                   "shift": "Shift", "ctrl": "Ctrl", "alt": "Alt"}
        partes = [nombres.get(t, t) for t in self.teclas] + [nombres.get(b, b) for b in self.botones]
        return " + ".join(partes)


MEDIO = Combinacion(("medio",), ())
SHIFT_MEDIO = Combinacion(("medio",), ("shift",))
MEDIO_IZQ = Combinacion(("medio", "izq"), ())


@dataclass(frozen=True)
class Perfil:
    clave: str
    nombre: str
    exes: tuple
    modo_sugerido: str
    orbitar: Combinacion | None
    desplazar: Combinacion
    rueda_fraccion: bool = False
    max_muescas_s: float = 10.0
    ver_todo: tuple | str = ()
    ganancia_orbita: float = 1.0
    invertir_rueda: bool = False
    desplazar_2d: Combinacion | None = None   # combinación en modo 2D (si difiere)
    nota: str = ""
    # Con rueda fraccionaria: alejar solo en muescas enteras (±120). EDWIN CNC 3D le pone a
    # cada evento de alejar un piso de 5 cm sin importar su tamaño, así que 8 eventos de 15
    # alejaban 8 veces más que una muesca de 120 y separar y juntar las manos no volvía igual.
    alejar_entero: bool = False

    def combinacion_desplazar(self, modo: str) -> Combinacion:
        if modo == "2D" and self.desplazar_2d is not None:
            return self.desplazar_2d
        return self.desplazar

    def combinacion_orbitar(self, modo: str) -> Combinacion:
        return self.orbitar if self.orbitar is not None else MEDIO


PERFILES: dict[str, Perfil] = {
    "edwin3d": Perfil("edwin3d", "EDWIN CNC 3D", ("ingetrazo.exe",), "3D", MEDIO, SHIFT_MEDIO,
                      rueda_fraccion=True, max_muescas_s=30, ver_todo=("shift", "z"), alejar_entero=True,
                      nota="Gira alrededor del punto que queda bajo el puntero."),
    "sketchup": Perfil("sketchup", "SketchUp", ("sketchup.exe",), "3D", MEDIO, SHIFT_MEDIO,
                       max_muescas_s=10, ver_todo=("shift", "z")),
    "freecad": Perfil("freecad", "FreeCAD", ("freecad.exe",), "3D", MEDIO_IZQ, MEDIO,
                      max_muescas_s=10, ver_todo=("v", "f"),
                      nota="Estilo CAD: el botón izquierdo puede seleccionar algo. "
                           "Se recomienda el estilo Blender."),
    "freecad_blender": Perfil("freecad_blender", "FreeCAD (estilo Blender)", (), "3D", MEDIO, SHIFT_MEDIO,
                              max_muescas_s=10, ver_todo=("v", "f")),
    "blender": Perfil("blender", "Blender", ("blender.exe",), "3D", MEDIO, SHIFT_MEDIO,
                      max_muescas_s=10, ver_todo=("home",)),
    "edwin2d": Perfil("edwin2d", "EDWIN CNC CAD-CAM", ("edwin-cnc.exe", "edwin-cnc*.exe", "librecad.exe"), "2D",
                      None, MEDIO, max_muescas_s=8, ver_todo="doble_medio",
                      nota="Solo pasos de rueda completos y máximo 8 por segundo."),
    "generico": Perfil("generico", "Genérico", (), "2D", MEDIO, SHIFT_MEDIO, max_muescas_s=10,
                       desplazar_2d=MEDIO),
}
GENERICO = PERFILES["generico"]


def nombre_exe(ruta: str | None) -> str:
    if not ruta:
        return ""
    return ntpath.basename(str(ruta).replace("/", "\\")).strip().lower()


def perfil_para_exe(ruta: str | None, personalizados: dict | None = None) -> Perfil:
    """Resuelve el perfil por el nombre del .exe (sin distinguir mayúsculas, con comodines)."""
    exe = nombre_exe(ruta)
    if not exe:
        return GENERICO
    for p in list(cargar_personalizados(personalizados).values()) + list(PERFILES.values()):
        for patron in p.exes:
            if fnmatch.fnmatchcase(exe, patron.lower()):
                return p
    return GENERICO


def _comb(d) -> Combinacion | None:
    if d is None:
        return None
    if isinstance(d, Combinacion):
        return d
    bot = tuple(b for b in (d.get("botones") or ()) if b in ("izq", "der", "medio"))
    tec = tuple(k for k in (d.get("teclas") or ()) if k in ("shift", "ctrl", "alt"))
    return Combinacion(bot or ("medio",), tec)


def cargar_personalizados(datos: dict | None) -> dict[str, Perfil]:
    """Perfiles personalizados de config.perfiles.personalizados (mismo formato). Los dañados se ignoran."""
    out = {}
    for clave, d in (datos or {}).items():
        try:
            exes = tuple(str(e).lower() for e in d.get("exes", ()))
            out[clave] = Perfil(
                clave=str(clave), nombre=str(d.get("nombre", clave)), exes=exes,
                modo_sugerido="3D" if d.get("modo_sugerido") == "3D" else "2D",
                orbitar=_comb(d.get("orbitar", {"botones": ["medio"]})),
                desplazar=_comb(d.get("desplazar", {"botones": ["medio"], "teclas": ["shift"]})),
                rueda_fraccion=bool(d.get("rueda_fraccion", False)),
                max_muescas_s=float(d.get("max_muescas_s", 10)),
                ver_todo=tuple(d.get("ver_todo", ())),
                ganancia_orbita=float(d.get("ganancia_orbita", 1.0)),
                invertir_rueda=bool(d.get("invertir_rueda", False)),
                alejar_entero=bool(d.get("alejar_entero", False)),
            )
        except (AttributeError, TypeError, ValueError):
            continue
    return out


def obtener(clave: str, personalizados: dict | None = None) -> Perfil:
    p = cargar_personalizados(personalizados).get(clave)
    return p or PERFILES.get(clave, GENERICO)


# ---------------------------------------------------------------------------
class Traductor:
    """Convierte acciones abstractas en concretas según el perfil."""

    ESPERA_TECLA_MS = 20
    ESPERA_SOLTAR_MS = 15
    ESPERA_BOTONES_MS = 20

    def __init__(self, perfil: Perfil = GENERICO, invertir_zoom: bool = False, max_muescas_cfg: float = 8.0):
        self.perfil = perfil
        self.invertir_zoom = invertir_zoom
        self.max_muescas_cfg = max_muescas_cfg
        self._tokens = 0.0
        self._t_tokens = None
        self._acum_fraccion = 0.0

    def cambiar_perfil(self, perfil: Perfil):
        self.perfil = perfil
        self._acum_fraccion = 0.0

    def empezar(self, comb: Combinacion) -> list:
        acc = []
        for k in comb.teclas:
            acc.append(Tecla(k, True))
        if comb.teclas:
            acc.append(Esperar(self.ESPERA_TECLA_MS))
        for i, b in enumerate(comb.botones):
            if i:
                acc.append(Esperar(self.ESPERA_BOTONES_MS))
            acc.append(Bajar(b))
        return acc

    def terminar(self, comb: Combinacion) -> list:
        acc = [Subir(b) for b in reversed(comb.botones)]
        if comb.teclas:
            acc.append(Esperar(self.ESPERA_SOLTAR_MS))
            for k in reversed(comb.teclas):
                acc.append(Tecla(k, False))
        return acc

    # ---- rueda ----
    @property
    def max_muescas_s(self) -> float:
        lim = self.perfil.max_muescas_s
        if not self.perfil.rueda_fraccion:
            lim = min(lim, self.max_muescas_cfg) if self.max_muescas_cfg > 0 else lim
        return max(lim, 0.5)

    def _signo(self) -> int:
        return -1 if (self.invertir_zoom != self.perfil.invertir_rueda) else 1

    def puede_muesca(self, t: float) -> bool:
        """Cubeta de fichas: como máximo max_muescas_s por segundo."""
        lim = self.max_muescas_s
        if self._t_tokens is None:
            self._t_tokens = t
            self._tokens = 1.0
        else:
            self._tokens = min(1.0, self._tokens + (t - self._t_tokens) * lim)
            self._t_tokens = t
        return self._tokens >= 1.0 - 1e-9

    def gastar_muesca(self):
        self._tokens -= 1.0

    def muesca(self, direccion: int) -> Rueda:
        """Una muesca completa (±120). direccion > 0 = acercar."""
        return Rueda(WHEEL_DELTA * (1 if direccion > 0 else -1) * self._signo())

    def fraccion(self, muescas: float) -> list:
        """Perfiles con rueda fraccionaria (EDWIN CNC 3D): acumula y envía de a 15 o más."""
        self._acum_fraccion += muescas * WHEEL_DELTA * self._signo()
        if self.perfil.alejar_entero and self._acum_fraccion < 0:
            # alejar (delta negativo): solo muescas enteras
            n = int(-self._acum_fraccion // WHEEL_DELTA)
            if n >= 1:
                d = -n * WHEEL_DELTA
                self._acum_fraccion -= d
                return [Rueda(d)]
            return []
        if abs(self._acum_fraccion) >= 15:
            d = int(math.copysign(math.floor(abs(self._acum_fraccion)), self._acum_fraccion))
            self._acum_fraccion -= d
            return [Rueda(d)]
        return []

    def vaciar(self):
        self._acum_fraccion = 0.0
