"""Intérprete de teclas para las acciones que mandan una tecla o una combinación (1.0.2).

Puro: no toca Windows. ``interpretar_envio("Ctrl+Shift+G")`` -> ("ctrl", "shift", "g") y
``nombre_envio(("ctrl", "shift", "g"))`` -> "Ctrl+Shift+G" (ida y vuelta).
Acepta nombres en español ("Supr", "Izquierda", "RePág") y en inglés ("Del", "Left").
"""
from __future__ import annotations

MODIFICADORES = ("ctrl", "alt", "shift")      # orden en que se bajan y se muestran

# nombre interno -> (texto para mostrar, código de tecla virtual de Windows)
TECLAS: dict[str, tuple[str, int]] = {
    "ctrl": ("Ctrl", 0xA2), "alt": ("Alt", 0xA4), "shift": ("Shift", 0xA0),
    "enter": ("Enter", 0x0D), "esc": ("Esc", 0x1B), "supr": ("Supr", 0x2E), "tab": ("Tab", 0x09),
    "espacio": ("Espacio", 0x20), "retroceso": ("Retroceso", 0x08), "insert": ("Insert", 0x2D),
    "inicio": ("Inicio", 0x24), "fin": ("Fin", 0x23), "repag": ("RePág", 0x21), "avpag": ("AvPág", 0x22),
    "izquierda": ("Izquierda", 0x25), "arriba": ("Arriba", 0x26), "derecha": ("Derecha", 0x27),
    "abajo": ("Abajo", 0x28),
    **{chr(c).lower(): (chr(c), c) for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): (str(d), 0x30 + d) for d in range(10)},
    **{f"f{i}": (f"F{i}", 0x6F + i) for i in range(1, 25)},
}
# Teclas que Windows marca como "extendidas" (si no, por ejemplo Supr sale como el punto del
# teclado numérico y las flechas como 4, 6, 8 y 2 con Bloq Num).
EXTENDIDAS = frozenset({"supr", "insert", "inicio", "fin", "repag", "avpag", "izquierda", "arriba",
                        "derecha", "abajo"})

ALIAS = {
    "control": "ctrl", "mayus": "shift", "mayús": "shift", "may": "shift",
    "intro": "enter", "return": "enter", "entrar": "enter",
    "escape": "esc", "del": "supr", "delete": "supr", "suprimir": "supr",
    "space": "espacio", "backspace": "retroceso", "borrar": "retroceso", "ins": "insert",
    "home": "inicio", "end": "fin",
    "repág": "repag", "pgup": "repag", "pageup": "repag", "re pág": "repag",
    "avpág": "avpag", "pgdn": "avpag", "pagedown": "avpag", "av pág": "avpag",
    "left": "izquierda", "izq": "izquierda", "up": "arriba", "right": "derecha", "der": "derecha",
    "down": "abajo",
}


def _normal(parte: str) -> str | None:
    p = parte.strip().lower()
    p = ALIAS.get(p, p)
    return p if p in TECLAS else None


def interpretar_envio(texto) -> tuple | None:
    """Texto del usuario -> tupla de nombres internos (modificadores primero). None si no sirve.

    Debe llevar UNA tecla principal (Enter, Z, F5, Izquierda...) y, si quiere, Ctrl, Alt o Shift."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    mods: list[str] = []
    principal = None
    for parte in texto.split("+"):
        if not parte.strip():
            return None
        n = _normal(parte)
        if n is None:
            return None
        if n in MODIFICADORES:
            if n not in mods:
                mods.append(n)
        elif principal is None:
            principal = n
        else:
            return None                     # dos teclas principales: no se entiende
    if principal is None:
        return None
    return tuple(m for m in MODIFICADORES if m in mods) + (principal,)


def nombre_envio(teclas) -> str:
    """Tupla de nombres internos -> texto para mostrar ("Ctrl+Z")."""
    try:
        return "+".join(TECLAS[k][0] if k in TECLAS else str(k) for k in teclas)
    except TypeError:
        return ""


def vk_de(nombre: str) -> int | None:
    t = TECLAS.get(nombre)
    return t[1] if t else None


def es_extendida(nombre: str) -> bool:
    return nombre in EXTENDIDAS
