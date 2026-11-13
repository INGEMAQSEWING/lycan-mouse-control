# Gancho de arranque de PyInstaller (se ejecuta antes que el programa).
# mediapipe.solutions.drawing_utils hace "import matplotlib.pyplot as plt" al
# cargarse, pero solo lo usa en plot_landmarks(), que este programa no llama.
# Un modulo vacio evita empaquetar matplotlib (unos 40 MB).
# Probado 2026-11-12 con mediapipe 0.10.14 + PyInstaller 6.22.3.
import sys
import types

if "matplotlib" not in sys.modules:
    _mpl = types.ModuleType("matplotlib")
    _plt = types.ModuleType("matplotlib.pyplot")
    _mpl.pyplot = _plt
    sys.modules["matplotlib"] = _mpl
    sys.modules["matplotlib.pyplot"] = _plt
