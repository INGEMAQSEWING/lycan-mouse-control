"""Doble clic aquí para abrir Lycan Mouse Control sin ventana negra (usa pythonw).

Equivale a:  py -3.10 -m lycan_mouse_control
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lycan_mouse_control.app import main  # noqa: E402

if __name__ == "__main__":
    main()
