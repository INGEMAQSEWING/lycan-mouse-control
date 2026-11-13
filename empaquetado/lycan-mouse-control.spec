# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: Lycan Mouse Control (modo carpeta, "one-dir").

Compilar (desde la raiz del proyecto):
    py -3.10 -m PyInstaller empaquetado\lycan-mouse-control.spec --noconfirm
Resultado:
    dist\LycanMouseControl\LycanMouseControl.exe  (+ carpeta _internal)

Probado 2026-11-12 (mediapipe 0.10.14, opencv-python-headless 4.10.0.84,
numpy 2.2.6, PyInstaller 6.22.3, Python 3.10): carpeta ~199 MB,
comprimida con LZMA ~56 MB; mp.solutions.hands arranca bien en el .exe.

Por que NO "onefile": cada arranque descomprimiria ~200 MB en %TEMP%
(5-15 s en un portatil de 8 GB) y los antivirus marcan mas a menudo los
.exe que se auto-extraen. El instalador Inno Setup ya entrega un solo archivo.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parent          # raiz del proyecto
ENTRADA = str(ROOT / 'lanzar.py')               # lanzador: from lycan_mouse_control.app import main; main()
ICONO = ROOT / 'recursos' / 'lycan-mouse.ico'

# ── Modelos de mediapipe ─────────────────────────────────────────────────────
# Solo lo que usa mp.solutions.hands: hand_landmark_tracking_cpu.binarypb,
# hand_landmark_{lite,full}.tflite, handedness.txt, palm_detection_{lite,full}.tflite.
# (Equivale a --collect-data mediapipe pero sin los otros 8 modelos: cara,
# pose, selfie..., unos 16 MB menos.)  Sin esto el .exe falla con
# "ValueError: The path does not exist: ...hand_landmark_tracking_cpu.binarypb".
datas = collect_data_files(
    'mediapipe',
    includes=['modules/hand_landmark/*', 'modules/palm_detection/*'],
)
# Recursos propios del programa (iconos, textos de ayuda, etc.).
if (ROOT / 'recursos').is_dir():
    datas.append((str(ROOT / 'recursos'), 'recursos'))

a = Analysis(
    [ENTRADA],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=[],
    runtime_hooks=[str(Path(SPECPATH) / 'rthook_sin_matplotlib.py')],
    # mediapipe 0.10.14 pide jax, jaxlib, matplotlib y sounddevice como
    # dependencias, pero mp.solutions.hands no los usa. OJO: NO excluir
    # 'mediapipe.tasks': mediapipe/__init__.py lo importa siempre
    # ("ModuleNotFoundError: No module named 'mediapipe.tasks'").
    excludes=[
        'jax', 'jaxlib', 'matplotlib', 'sounddevice', 'scipy', 'pandas',
        'IPython', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'tensorflow',
        'torch', 'mediapipe.model_maker', 'pytest',
    ],
    noarchive=False,
)

# opencv: la DLL de ffmpeg (~30 MB) solo sirve para leer/grabar ARCHIVOS de
# video; la camara usa MSMF/DirectShow, que vienen dentro de cv2.pyd.
a.binaries = [b for b in a.binaries if 'opencv_videoio_ffmpeg' not in b[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LycanMouseControl',
    console=False,              # sin ventana negra. sys.stdout/stderr = None:
                                # el programa debe enviar su registro a un archivo.
    upx=False,                  # UPX dispara falsos positivos de antivirus.
    icon=str(ICONO) if ICONO.exists() else None,
    version=str(Path(SPECPATH) / 'version_info.txt'),
    # El programa debe ser "DPI aware" para que SendInput y las
    # coordenadas de pantalla coincidan con escalado 125-150 %.
    # PyInstaller ya incrusta un manifiesto; ademas, al arrancar:
    #   ctypes.windll.shcore.SetProcessDpiAwareness(2)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name='LycanMouseControl',
)
