"""Índices de los puntos de la mano (MediaPipe) y valores fijos del programa."""

# ---- Puntos de la mano (MediaPipe Hands) ----
MUNECA = 0
PULGAR = (1, 2, 3, 4)          # CMC, MCP, IP, punta
INDICE = (5, 6, 7, 8)          # MCP, PIP, DIP, punta
CORAZON = (9, 10, 11, 12)
ANULAR = (13, 14, 15, 16)
MENIQUE = (17, 18, 19, 20)
DEDOS_LARGOS = {"indice": INDICE, "corazon": CORAZON, "anular": ANULAR, "menique": MENIQUE}
PUNTAS = (4, 8, 12, 16, 20)
PUNTOS_PALMA = (0, 5, 9, 13, 17)

CONEXIONES = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)

# ---- Estados principales ----
PAUSA = "PAUSA"
ACTIVO = "ACTIVO"
ARRASTRANDO = "ARRASTRANDO"
GIRANDO_3D = "GIRANDO_3D"
DESPLAZANDO = "DESPLAZANDO"
SIN_MANO = "SIN_MANO"
BLOQUEADO = "BLOQUEADO"

COLORES_ESTADO = {
    PAUSA: "#8A8F98",
    ACTIVO: "#1FA34A",
    ARRASTRANDO: "#2F6FEB",
    GIRANDO_3D: "#FF9F1C",
    DESPLAZANDO: "#FF9F1C",
    SIN_MANO: "#D93636",
    BLOQUEADO: "#D93636",
}

# ---- Botones y teclas (nombres internos) ----
IZQ, DER, MEDIO = "izq", "der", "medio"
BOTONES = (IZQ, DER, MEDIO)
SHIFT, CTRL, ALT = "shift", "ctrl", "alt"
TECLAS = (SHIFT, CTRL, ALT)

WHEEL_DELTA = 120

# Firma de los eventos propios en dwExtraInfo ('LYCN')
LYCAN_EXTRA = 0x4C59434E

NOMBRE_APP = "Lycan Mouse Control"
CARPETA_DATOS = "Lycan Mouse Control"
MUTEX = "Local\\LycanMouseControl"
