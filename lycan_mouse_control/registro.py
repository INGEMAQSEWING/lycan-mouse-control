"""Registro de errores: %APPDATA%\\Lycan Mouse Control\\registros\\registro.txt
(1 MB, 3 copias, UTF-8). Nunca se guardan imágenes de la cámara.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import carpeta_datos
from .version import VERSION

log = logging.getLogger("lycan")
_MANEJADOR: RotatingFileHandler | None = None


def carpeta_registros() -> Path:
    return carpeta_datos() / "registros"


class _Nulo:
    """Reemplazo de sys.stdout/stderr cuando el .exe no tiene consola (son None)."""

    def write(self, *_a, **_k):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False


def proteger_salida_estandar():
    if sys.stdout is None:
        sys.stdout = _Nulo()
    if sys.stderr is None:
        sys.stderr = _Nulo()


ERROR: str | None = None     # por qué no se pudo crear el archivo de registro (para avisar)


def configurar(carpeta: Path | None = None, nivel=logging.INFO, max_bytes: int = 1_000_000) -> Path:
    """Crea la carpeta y el archivo rotativo. Devuelve la ruta del archivo."""
    global _MANEJADOR, ERROR
    proteger_salida_estandar()
    carpeta = Path(carpeta) if carpeta else carpeta_registros()
    ruta = carpeta / "registro.txt"
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        if _MANEJADOR is not None:
            log.removeHandler(_MANEJADOR)
            _MANEJADOR.close()
        h = RotatingFileHandler(ruta, maxBytes=max_bytes, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
        log.addHandler(h)
        _MANEJADOR = h
        ERROR = None
    except OSError as e:
        ERROR = str(e)
    log.setLevel(nivel)
    log.propagate = False
    return ruta


def anotar_inicio(extra: dict | None = None):
    log.info("==== Lycan Mouse Control %s ====", VERSION)
    log.info("Windows: %s %s | Python %s", platform.system(), platform.version(), platform.python_version())
    for k, v in (extra or {}).items():
        log.info("%s: %s", k, v)


def instalar_ganchos(al_fallar):
    """Excepción no atrapada en cualquier hilo: ``al_fallar(exc)`` (suelta todo y pausa)."""
    anterior = sys.excepthook

    def gancho(tipo, valor, traza):
        log.error("Excepción no atrapada", exc_info=(tipo, valor, traza))
        try:
            al_fallar(valor)
        except Exception:  # noqa: BLE001
            pass
        if anterior and anterior is not sys.__excepthook__:
            anterior(tipo, valor, traza)

    def gancho_hilo(args):
        if args.exc_type is SystemExit:
            return
        log.error("Excepción no atrapada en el hilo %s", getattr(args.thread, "name", "?"),
                  exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        try:
            al_fallar(args.exc_value)
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = gancho
    threading.excepthook = gancho_hilo


def abrir_carpeta():
    try:
        os.startfile(str(carpeta_registros()))  # noqa: S606
    except OSError:
        pass
