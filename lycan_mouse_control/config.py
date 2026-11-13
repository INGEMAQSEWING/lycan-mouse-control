"""Configuración: %APPDATA%\\Lycan Mouse Control\\config.json (UTF-8).

- Escritura atómica (archivo temporal + os.replace).
- Si falta, está vacío o dañado: se renombra a config.dañado-AAAAMMDD-HHMMSS.json, se usan
  los valores de fábrica y se avisa "Se restableció la configuración.".
- Cada valor se valida (tipo y rango); uno fuera de rango vuelve al de fábrica y se anota.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import time
from pathlib import Path

from .constantes import CARPETA_DATOS

log = logging.getLogger("lycan")

VERSION_CONFIG = 1

FABRICA: dict = {
    "version": 1,
    "primera_vez": True,
    "modo": "2D",
    "mano_principal": "derecha",
    "camara": {"indice": 0, "ancho": 640, "alto": 480, "fps": 30},
    "pantalla": {"monitor": "principal"},
    "zona": {"x0": 0.20, "y0": 0.25, "x1": 0.80, "y1": 0.70, "codo_apoyado": True},
    "puntero": {"modo": "absoluto", "mincutoff": 0.5, "beta": 0.015, "dcutoff": 1.0,
                "zona_muerta_px": 1.5, "umbral_arrastre_px": 14, "rebobinado_ms": 100,
                "dibujo_fino": False, "relativo": {"gmin": 0.6, "gmax": 3.0}},
    "senas": {
        "pellizco": {"entrar": 0.28, "salir": 0.42},
        "pellizco_corazon": {"entrar": 0.28, "salir": 0.42, "activo": False},
        "juntos": {"s_entrar": 1.25, "s_salir": 1.50, "a_entrar": 10, "a_salir": 15},
        "v": {"s_entrar": 1.9, "s_salir": 1.6},
        "doblez": {"extendido": [60, 85], "doblado": [110, 90]},
        "desplazar_dos_manos": True,
        "tiempos_ms": {"pellizco": [66, 66], "puno": 200, "puno_espera": 500, "puno_tras_pellizco": 300,
                       "activar_min": 120, "activar_max": 1500, "activar_en_pausa": 250, "soltar_min": 100,
                       "doble_ventana": 700, "ignorar_tras_activar": 800, "agarre_3d": 150,
                       "mano_perdida": 150, "pausa_sin_mano_s": 10},
    },
    "zoom": {"paso_log": 0.08, "zona_muerta_log": 0.05, "max_muescas_s": 8, "invertir": False,
             "una_mano": False},
    "orbita": {"k_vol": 1.0, "k_mov": 0.8, "ganancia": 1.0, "max_px_cuadro": 60},
    "perfiles": {"automatico": True, "manual": "generico", "personalizados": {}},
    "atajos": {"pausar": "Ctrl+Alt+M", "salir": "Ctrl+Alt+X", "ventana": "Ctrl+Alt+O",
               "modo": "Ctrl+Alt+D", "dibujo_fino": "Ctrl+Alt+P"},
    "comodidad": {"sonidos": True, "aviso_cursor": True, "opacidad": 0.94,
                  "descanso_min": 20, "aviso_brazo_alto": True},
    "ventana": {"x": None, "y": None, "mini": False},
    "calibracion": {"fecha": None, "luz": None, "tam_mano": None},
}

# Rangos válidos (ruta con puntos -> (mínimo, máximo)). Fuera de rango = valor de fábrica.
RANGOS = {
    "camara.indice": (0, 9), "camara.ancho": (160, 1920), "camara.alto": (120, 1080), "camara.fps": (5, 60),
    "zona.x0": (0.0, 1.0), "zona.y0": (0.0, 1.0), "zona.x1": (0.0, 1.0), "zona.y1": (0.0, 1.0),
    "puntero.mincutoff": (0.05, 5.0), "puntero.beta": (0.0, 0.5), "puntero.dcutoff": (0.1, 10.0),
    "puntero.zona_muerta_px": (0.0, 2.0), "puntero.umbral_arrastre_px": (2, 60),
    "puntero.rebobinado_ms": (0, 300), "puntero.relativo.gmin": (0.1, 5.0), "puntero.relativo.gmax": (0.2, 10.0),
    "senas.pellizco.entrar": (0.05, 1.0), "senas.pellizco.salir": (0.05, 1.5),
    "senas.pellizco_corazon.entrar": (0.05, 1.0), "senas.pellizco_corazon.salir": (0.05, 1.5),
    "senas.juntos.s_entrar": (0.3, 3.0), "senas.juntos.s_salir": (0.3, 3.5),
    "senas.juntos.a_entrar": (1, 45), "senas.juntos.a_salir": (1, 60),
    "senas.v.s_entrar": (0.5, 5.0), "senas.v.s_salir": (0.5, 5.0),
    "senas.tiempos_ms.puno": (100, 1000), "senas.tiempos_ms.puno_espera": (100, 3000),
    "senas.tiempos_ms.puno_tras_pellizco": (0, 2000), "senas.tiempos_ms.activar_min": (40, 1000),
    "senas.tiempos_ms.activar_max": (500, 5000), "senas.tiempos_ms.activar_en_pausa": (100, 1500),
    "senas.tiempos_ms.soltar_min": (30, 500), "senas.tiempos_ms.doble_ventana": (400, 1200),
    "senas.tiempos_ms.ignorar_tras_activar": (0, 3000), "senas.tiempos_ms.agarre_3d": (50, 1000),
    "senas.tiempos_ms.mano_perdida": (50, 1000), "senas.tiempos_ms.pausa_sin_mano_s": (3, 60),
    "zoom.paso_log": (0.02, 0.5), "zoom.zona_muerta_log": (0.0, 0.3), "zoom.max_muescas_s": (1, 30),
    "orbita.k_vol": (0.0, 5.0), "orbita.k_mov": (0.0, 5.0), "orbita.ganancia": (0.1, 5.0),
    "orbita.max_px_cuadro": (5, 300),
    "comodidad.opacidad": (0.6, 1.0), "comodidad.descanso_min": (0, 60),
}
OPCIONES = {
    "modo": ("2D", "3D"),
    "mano_principal": ("derecha", "izquierda"),
    "puntero.modo": ("absoluto", "relativo"),
}


def carpeta_datos() -> Path:
    """%APPDATA%\\Lycan Mouse Control (se puede cambiar con LYCAN_MOUSE_DATOS, para pruebas)."""
    otra = os.environ.get("LYCAN_MOUSE_DATOS")
    if otra:
        return Path(otra)
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / CARPETA_DATOS


def ruta_config() -> Path:
    return carpeta_datos() / "config.json"


def por_defecto() -> dict:
    return copy.deepcopy(FABRICA)


def _es_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validar(datos, fabrica: dict | None = None, ruta: str = "", problemas: list | None = None) -> dict:
    """Devuelve una configuración completa y válida. Anota en ``problemas`` lo que se corrigió."""
    fabrica = FABRICA if fabrica is None else fabrica
    problemas = [] if problemas is None else problemas
    if not isinstance(datos, dict):
        if ruta == "":
            problemas.append("la configuración no es un objeto")
        else:
            problemas.append(f"{ruta}: tipo equivocado")
        datos = {}
    out = {}
    for clave, fab in fabrica.items():
        r = f"{ruta}.{clave}" if ruta else clave
        if clave not in datos:
            out[clave] = copy.deepcopy(fab)
            continue
        v = datos[clave]
        if clave == "personalizados" and isinstance(v, dict):
            out[clave] = copy.deepcopy(v)
            continue
        if isinstance(fab, dict):
            out[clave] = validar(v, fab, r, problemas)
        elif isinstance(fab, bool):
            if isinstance(v, bool):
                out[clave] = v
            else:
                problemas.append(f"{r}: se esperaba sí/no")
                out[clave] = fab
        elif isinstance(fab, list):
            if (isinstance(v, list) and len(v) == len(fab) and all(_es_num(x) for x in v)):
                out[clave] = list(v)
            else:
                problemas.append(f"{r}: lista inválida")
                out[clave] = list(fab)
        elif _es_num(fab):
            if not _es_num(v) or v != v:  # NaN
                problemas.append(f"{r}: se esperaba un número")
                out[clave] = fab
            else:
                lo_hi = RANGOS.get(r)
                if lo_hi and not (lo_hi[0] <= v <= lo_hi[1]):
                    problemas.append(f"{r}: {v} fuera de rango {lo_hi}")
                    out[clave] = fab
                else:
                    out[clave] = type(fab)(v) if isinstance(fab, float) else v
        elif isinstance(fab, str):
            if not isinstance(v, str):
                problemas.append(f"{r}: se esperaba texto")
                out[clave] = fab
            elif r in OPCIONES and v not in OPCIONES[r]:
                problemas.append(f"{r}: valor '{v}' no permitido")
                out[clave] = fab
            else:
                out[clave] = v
        elif fab is None:
            out[clave] = v if (v is None or _es_num(v) or isinstance(v, str)) else None
        else:
            out[clave] = v
    # coherencia de la zona
    if ruta == "":
        z = out["zona"]
        if z["x1"] - z["x0"] < 0.1 or z["y1"] - z["y0"] < 0.1:
            problemas.append("zona: demasiado pequeña")
            for k in ("x0", "y0", "x1", "y1"):
                z[k] = FABRICA["zona"][k]
        out["version"] = VERSION_CONFIG
    return out


class Configuracion:
    """Carga y guarda la configuración. ``aviso`` queda con el texto para la interfaz, si hubo."""

    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta) if ruta else ruta_config()
        self.datos: dict = por_defecto()
        self.aviso: str | None = None
        self.problemas: list[str] = []

    def cargar(self) -> dict:
        self.aviso = None
        self.problemas = []
        if not self.ruta.exists():
            self.datos = por_defecto()
            return self.datos
        try:
            texto = self.ruta.read_text(encoding="utf-8")
            if not texto.strip():
                raise ValueError("archivo vacío")
            crudo = json.loads(texto)
            if not isinstance(crudo, dict):
                raise ValueError("no es un objeto JSON")
        except (OSError, ValueError, UnicodeDecodeError, RecursionError, MemoryError) as e:
            # RecursionError: un JSON con miles de corchetes anidados tumbaba el arranque.
            log.warning("Configuración dañada (%s); se restablece.", type(e).__name__ if
                        isinstance(e, RecursionError) else e)
            self._apartar_danado()
            self.datos = por_defecto()
            self.aviso = "Se restableció la configuración."
            return self.datos
        version = crudo.get("version")
        if _es_num(version) and version > VERSION_CONFIG:
            self.problemas.append(f"versión {version} más nueva que la del programa")
        self.datos = validar(crudo, problemas=self.problemas)
        if self.problemas:
            for p in self.problemas:
                log.warning("Configuración: %s (se usa el valor de fábrica)", p)
            if any("versión" in p or "no es un objeto" in p for p in self.problemas):
                self.aviso = "Se restableció la configuración."
        return self.datos

    def _apartar_danado(self):
        try:
            sello = time.strftime("%Y%m%d-%H%M%S")
            destino = self.ruta.with_name(f"config.dañado-{sello}.json")
            n = 1
            while destino.exists():
                destino = self.ruta.with_name(f"config.dañado-{sello}-{n}.json")
                n += 1
            os.replace(self.ruta, destino)
        except OSError as e:
            log.warning("No se pudo apartar la configuración dañada: %s", e)

    def guardar(self, datos: dict | None = None):
        if datos is not None:
            self.datos = validar(datos)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        # Ruta temporal FIJA y un solo intento. tempfile.mkstemp en Windows toma un "acceso
        # denegado" como "nombre ocupado" y reintenta sin fin (el programa quedaba colgado
        # gastando un núcleo cuando la carpeta no deja escribir).
        tmp = self.ruta.with_name(self.ruta.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.datos, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.ruta)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def guardar_seguro(self, datos: dict | None = None) -> bool:
        """Como guardar(), pero nunca lanza: anota el problema y devuelve False."""
        try:
            self.guardar(datos)
            return True
        except (OSError, ValueError, TypeError) as e:
            log.warning("No se pudo guardar la configuración: %s", e)
            return False

    def restablecer_fabrica(self):
        """Restaura todo menos atajos y ventana."""
        nuevo = por_defecto()
        nuevo["atajos"] = copy.deepcopy(self.datos.get("atajos", nuevo["atajos"]))
        nuevo["ventana"] = copy.deepcopy(self.datos.get("ventana", nuevo["ventana"]))
        nuevo["primera_vez"] = False
        self.datos = nuevo
        return self.datos
