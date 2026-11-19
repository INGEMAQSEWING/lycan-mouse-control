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
import math
import os
import time
from pathlib import Path

from .constantes import CARPETA_DATOS

log = logging.getLogger("lycan")

VERSION_CONFIG = 1
# Ctrl, Shift, Alt y Windows (iguales a sistema.teclado.MODIFICADORES; aquí sin importar ctypes)
VK_NO_SIRVEN = frozenset({0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C})
REINTENTOS_LECTURA = 3
PAUSA_REINTENTO_S = 0.2
AVISO_NO_LEIDA = ("No se pudo leer la configuración (otro programa la tenía abierta); se usan los valores "
                  "de fábrica sin cambiar su archivo. Cierre y vuelva a abrir para recuperarla.")


class ErrorSoloLectura(OSError):
    """La configuración no se pudo leer al abrir: en esta sesión no se escribe encima."""

FABRICA: dict = {
    "version": 1,
    "primera_vez": True,
    "modo": "2D",
    "mano_principal": "derecha",
    "camara": {"indice": 0, "ancho": 640, "alto": 480, "fps": 30},
    "pantalla": {"monitor": "principal"},
    "zona": {"x0": 0.20, "y0": 0.25, "x1": 0.80, "y1": 0.70, "codo_apoyado": True,
             "mano_baja": False},                          # 1.0.2 paquete C
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
                       "mano_perdida": 150, "pausa_sin_mano_s": 10,
                       "menique": 100,                       # 1.0.2 paquete A
                       "puno_3d": 300},                      # 1.0.2 paquete B
        # 1.0.2 paquete A
        "pellizco_anular": {"entrar": 0.28, "salir": 0.42},
        "pellizco_menique": {"entrar": 0.26, "salir": 0.40},
        "clic_indice": True,
        "clic_anular": True,
        "menique": "doble_clic",
    },
    "zoom": {"paso_log": 0.08, "zona_muerta_log": 0.05, "max_muescas_s": 8, "invertir": False,
             "una_mano": False},
    "orbita": {"k_vol": 1.0, "k_mov": 0.8, "ganancia": 1.0, "max_px_cuadro": 60,
               # 1.0.2 paquete B: girar con un puño (de fábrica) y lanzar con inercia (apagado)
               "girar": "un_puno", "k_un_puno": 1.2, "inercia": False, "friccion": 1.5},
    "perfiles": {"automatico": True, "manual": "generico", "personalizados": {}},
    "atajos": {"pausar": "Ctrl+Alt+M", "salir": "Ctrl+Alt+X", "ventana": "Ctrl+Alt+O",
               "modo": "Ctrl+Alt+D", "dibujo_fino": "Ctrl+Alt+P"},
    "comodidad": {"sonidos": True, "aviso_cursor": True, "opacidad": 0.94,
                  "descanso_min": 20, "aviso_brazo_alto": True},
    "ventana": {"x": None, "y": None, "mini": False},
    "calibracion": {"fecha": None, "luz": None, "tam_mano": None},
    # 1.0.2 paquete A: clic con una tecla o un pedal (de fábrica, el 5 del teclado numérico)
    "tecla_clic": {"activa": True, "vk": 0x65, "scan": 0x4C, "extendida": False, "numerico": True,
                   "nombre": "5 del teclado numérico", "preguntado": False},
    # 1.0.2 paquete B: abrir / cerrar la mano de golpe; atajos por programa (los usa también C)
    "gestos": {"golpe": True, "por_programa": {},
               "barrido": False},                          # 1.0.3: lo reemplaza el abanico                           # 1.0.2 paquete C
    # 1.0.2 paquete C: pasar página con la palma abierta (rueda)
    # 1.0.3: la palma que arrastra la página queda apagada de fábrica (la reemplaza el abanico)
    "scroll": {"palma": False, "inercia": True, "friccion": 2.0, "invertir": False, "paso": 0.025},
    # 1.0.3 señas para navegar: clic empujando el dedo y scroll abanicando la mano
    "navegar": {"abanico": True, "empujar": True, "abanico_paso": 3, "empujar_fuerza": 0.15,
                "invertir": False},
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
    # listas: el rango se aplica a CADA elemento
    "senas.tiempos_ms.pellizco": (20, 500),
    "senas.doblez.extendido": (0, 180), "senas.doblez.doblado": (0, 180),
    # 1.0.2 paquete A
    "senas.pellizco_anular.entrar": (0.05, 1.0), "senas.pellizco_anular.salir": (0.05, 1.5),
    "senas.pellizco_menique.entrar": (0.05, 1.0), "senas.pellizco_menique.salir": (0.05, 1.5),
    "senas.tiempos_ms.menique": (40, 1000),
    "tecla_clic.vk": (1, 254), "tecla_clic.scan": (0, 255),
    # 1.0.2 paquete B
    "senas.tiempos_ms.puno_3d": (150, 1000),
    "orbita.k_un_puno": (0.1, 5.0), "orbita.friccion": (0.3, 6.0),
    # 1.0.2 paquete C
    "scroll.friccion": (0.3, 6.0), "scroll.paso": (0.005, 0.10),
    # 1.0.3
    "navegar.abanico_paso": (1, 10), "navegar.empujar_fuerza": (0.05, 0.50),
}
# Campos donde 0 significa "apagado" y, si no, hay un mínimo (un descanso cada 0,001 min sacaría
# el aviso a cada rato): (mínimo cuando no es 0).
MINIMO_SI_NO_CERO = {"comodidad.descanso_min": 5}
# Campos que tienen que ser enteros (índice de cámara, tamaños, milisegundos, minutos): un decimal
# se redondea. Otros campos enteros de fábrica (por ejemplo el ángulo de los dedos juntos, que la
# calibración guarda con decimales) sí aceptan decimales.
ENTEROS = {"camara.indice", "camara.ancho", "camara.alto", "camara.fps", "comodidad.descanso_min",
           "tecla_clic.vk", "tecla_clic.scan"}    # 1.0.2 paquete A


def _entero(ruta: str) -> bool:
    return ruta in ENTEROS or ruta.startswith("senas.tiempos_ms.")
OPCIONES = {
    "modo": ("2D", "3D"),
    "mano_principal": ("derecha", "izquierda"),
    "puntero.modo": ("absoluto", "relativo"),
    # 1.0.2 paquete A
    "senas.menique": ("doble_clic", "clic_derecho", "clic_medio", "enter", "esc", "suprimir", "deshacer",
                      "nada"),
    # 1.0.2 paquete B
    "orbita.girar": ("un_puno", "dos_punos", "ambos"),
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


def _finito(v) -> bool:
    """math.isfinite sin reventar: un entero gigante (1 seguido de 400 ceros) no cabe en un
    float y math.isfinite lanza OverflowError. Se trata como fuera de rango."""
    try:
        return math.isfinite(v)
    except (OverflowError, TypeError, ValueError):
        return False


def limpiar_por_programa(v, problemas: list | None = None) -> dict:
    """1.0.2 paquete B: gestos.por_programa = {programa: {gesto: "Ctrl+Shift+G"}}. Se guardan solo
    textos; lo demás (números, listas, programas que no son diccionario) se quita. Si el texto
    es un atajo que no se entiende, se ignora al usarlo (no aquí: así no se pierde lo escrito)."""
    problemas = [] if problemas is None else problemas
    if not isinstance(v, dict):
        problemas.append("gestos.por_programa: tipo equivocado")
        return {}
    out = {}
    for prog, gestos in v.items():
        if not isinstance(prog, str) or not isinstance(gestos, dict):
            problemas.append(f"gestos.por_programa.{prog}: tipo equivocado")
            continue
        limpio = {}
        for nombre, txt in gestos.items():
            if isinstance(nombre, str) and isinstance(txt, str) and len(txt) <= 60:
                limpio[nombre] = txt
            else:
                problemas.append(f"gestos.por_programa.{prog}.{nombre}: se esperaba texto")
        out[prog] = limpio
    return out


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
        if r == "gestos.por_programa":           # 1.0.2 paquete B: diccionario libre
            out[clave] = limpiar_por_programa(v, problemas)
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
            lo_hi = RANGOS.get(r)
            if not (isinstance(v, list) and len(v) == len(fab)
                    and all(_es_num(x) and _finito(x) for x in v)):
                problemas.append(f"{r}: lista inválida")
                out[clave] = list(fab)
            elif lo_hi and not all(lo_hi[0] <= x <= lo_hi[1] for x in v):
                problemas.append(f"{r}: {v} fuera de rango {lo_hi}")
                out[clave] = list(fab)
            else:
                out[clave] = [int(round(x)) if _entero(r) else x for x in v]
        elif _es_num(fab):
            if not _es_num(v) or not _finito(v):  # NaN, infinito o un entero gigante
                problemas.append(f"{r}: se esperaba un número")
                out[clave] = fab
            else:
                lo_hi = RANGOS.get(r)
                if lo_hi and not (lo_hi[0] <= v <= lo_hi[1]):
                    problemas.append(f"{r}: {v} fuera de rango {lo_hi}")
                    out[clave] = fab
                elif r in MINIMO_SI_NO_CERO and v != 0 and v < MINIMO_SI_NO_CERO[r]:
                    problemas.append(f"{r}: {v} es muy poco (0 o desde {MINIMO_SI_NO_CERO[r]})")
                    out[clave] = MINIMO_SI_NO_CERO[r]
                elif isinstance(fab, float):
                    out[clave] = float(v)
                elif _entero(r) and isinstance(v, float) and not v.is_integer():
                    # campo entero (índice de cámara, milisegundos...): se redondea
                    problemas.append(f"{r}: {v} no es un número entero; se usó {int(round(v))}")
                    out[clave] = int(round(v))
                elif _entero(r):
                    out[clave] = int(v)
                else:
                    out[clave] = v
        elif isinstance(fab, str):
            if not isinstance(v, str):
                problemas.append(f"{r}: se esperaba texto")
                out[clave] = fab
            elif r in OPCIONES and v not in OPCIONES[r]:
                problemas.append(f"{r}: valor '{v}' no permitido")
                out[clave] = fab
            elif r == "tecla_clic.nombre" and not v.strip():
                problemas.append(f"{r}: vacío")
                out[clave] = fab
            else:
                out[clave] = v
        elif fab is None:
            out[clave] = v if (v is None or (_es_num(v) and _finito(v)) or isinstance(v, str)) else None
        else:
            out[clave] = v
    # coherencia de la zona
    if ruta == "":
        z = out["zona"]
        if z["x1"] - z["x0"] < 0.1 or z["y1"] - z["y0"] < 0.1:
            problemas.append("zona: demasiado pequeña")
            for k in ("x0", "y0", "x1", "y1"):
                z[k] = FABRICA["zona"][k]
        # 1.0.2 paquete A: el «5 del teclado numérico» es siempre vk 0x65 / scan 0x4C
        tc = out["tecla_clic"]
        # revisión 1.0.2: escrita a mano, la tecla de clic no puede ser Ctrl, Shift, Alt, Windows ni
        # un botón del ratón (la grabación ya las rechaza): Shift dejaría de escribir en todo Windows
        if not tc["numerico"] and (tc["vk"] in VK_NO_SIRVEN or tc["vk"] < 0x08):
            problemas.append(f"tecla_clic.vk: {tc['vk']} no sirve como tecla de clic")
            tc["numerico"] = True
        if tc["numerico"]:
            fab_tc = FABRICA["tecla_clic"]
            tc["vk"], tc["scan"], tc["extendida"] = fab_tc["vk"], fab_tc["scan"], fab_tc["extendida"]
            tc["nombre"] = fab_tc["nombre"]
        out["version"] = VERSION_CONFIG
    return out


class Configuracion:
    """Carga y guarda la configuración. ``aviso`` queda con el texto para la interfaz, si hubo."""

    def __init__(self, ruta: Path | None = None):
        self.ruta = Path(ruta) if ruta else ruta_config()
        self.datos: dict = por_defecto()
        self.aviso: str | None = None
        self.problemas: list[str] = []
        self.solo_lectura = False     # True: en esta sesión no se escribe el archivo

    def _leer_texto(self) -> str | None:
        """Lee el archivo con 3 intentos (200 ms entre uno y otro). Un antivirus, una copia de
        seguridad o OneDrive pueden tenerlo bloqueado un momento. None si no se pudo leer.
        Un error de CONTENIDO (UnicodeDecodeError) se deja pasar: eso sí es archivo dañado."""
        ultimo = None
        for intento in range(REINTENTOS_LECTURA):
            try:
                return self.ruta.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise
            except OSError as e:
                ultimo = e
                if intento < REINTENTOS_LECTURA - 1:
                    time.sleep(PAUSA_REINTENTO_S)
        log.warning("No se pudo leer la configuración (%s): se usan los valores de fábrica sin "
                    "tocar el archivo.", ultimo)
        return None

    def cargar(self) -> dict:
        self.aviso = None
        self.problemas = []
        self.solo_lectura = False
        if not self.ruta.exists():
            self.datos = por_defecto()
            return self.datos
        try:
            texto = self._leer_texto()
            if texto is None:
                # Archivo bloqueado o sin permiso de lectura: NO es un archivo dañado. No se
                # aparta ni se escribe encima en esta sesión (se perdería la calibración).
                self.datos = por_defecto()
                self.datos["primera_vez"] = False     # el archivo existe: no es la primera vez
                self.solo_lectura = True
                self.aviso = AVISO_NO_LEIDA
                return self.datos
            if not texto.strip():
                raise ValueError("archivo vacío")
            crudo = json.loads(texto)
            if not isinstance(crudo, dict):
                raise ValueError("no es un objeto JSON")
            version = crudo.get("version")
            problemas: list[str] = []
            if _es_num(version) and version > VERSION_CONFIG:
                problemas.append(f"versión {version} más nueva que la del programa")
            datos = validar(crudo, problemas=problemas)
            if "navegar" not in crudo:
                # 1.0.3: configuración de antes. El abanico reemplaza la palma que arrastra la
                # página y el barrido (se pueden volver a prender en Opciones).
                datos["scroll"]["palma"] = False
                datos["gestos"]["barrido"] = False
        except (ValueError, UnicodeDecodeError, RecursionError, MemoryError, OverflowError,
                TypeError) as e:
            # OverflowError: un entero gigante (1 seguido de 400 ceros) no cabe en un float;
            # TypeError: por seguridad, cualquier otro valor raro termina en «se restableció»
            # y nunca en un programa que no abre.
            # RecursionError: un JSON con miles de corchetes anidados tumbaba el arranque.
            log.warning("Configuración dañada (%s); se restablece.", type(e).__name__ if
                        isinstance(e, RecursionError) else e)
            self.datos = por_defecto()
            self.aviso = "Se restableció la configuración."
            if not self._apartar_danado():
                # si no se pudo guardar la copia del dañado, tampoco se escribe encima al salir
                self.datos["primera_vez"] = False
                self.solo_lectura = True
            return self.datos
        self.problemas = problemas
        self.datos = datos
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
            return True
        except OSError as e:
            log.warning("No se pudo apartar la configuración dañada: %s", e)
            return False

    def guardar(self, datos: dict | None = None):
        if datos is not None:
            self.datos = validar(datos)
        if self.solo_lectura:
            # al abrir no se pudo leer (o apartar) el archivo: escribir ahora borraría la
            # configuración y la calibración que el usuario sí tiene guardadas
            raise ErrorSoloLectura("la configuración no se pudo leer al abrir; no se escribe encima")
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
