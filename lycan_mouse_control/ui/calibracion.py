"""Pantalla de calibración (unos 40 s): luz, distancia, zona cómoda y posturas.

Los cálculos están en lycan_mouse_control/calibracion.py (puros y probados).
"""
from __future__ import annotations

import copy
import math
import time
import tkinter as tk

from .. import calibracion as C
from .. import mano_baja as MB
from .comun import LETRA
from .textos import t

POSTURAS = [("abierta", "cal_abierta"), ("puno", "cal_puno"), ("pellizco", "cal_pellizco"),
            ("juntos", "cal_juntos"), ("v", "cal_v")]
PREPARAR_S = 1.5
POSTURA_S = 2.0


class Calibracion(tk.Frame):
    """Se incrusta en el asistente. ``al_terminar(ok: bool)`` al final."""

    def __init__(self, padre, app, al_terminar):
        super().__init__(padre)
        self.app = app
        self.al_terminar = al_terminar
        self.lbl_fase = tk.Label(self, text="", font=(LETRA, 13, "bold"), wraplength=360, justify="left")
        self.lbl_fase.pack(anchor="w", pady=(0, 6))
        self.lbl_info = tk.Label(self, text="", font=(LETRA, 10), wraplength=360, justify="left")
        self.lbl_info.pack(anchor="w")
        self.barra = tk.Canvas(self, width=360, height=10, bg="#DDD", highlightthickness=0)
        self.barra.pack(anchor="w", pady=8)
        self.btn = tk.Button(self, text=t("as_repetir"), command=self.empezar)
        self.btn.pack(anchor="w")
        self._fase = None
        self._t0 = 0.0
        self.empezar()

    def empezar(self):
        self.muestras = {p: [] for p, _ in POSTURAS}
        self.puntos = []
        self.resultado = {}
        self._luces = []
        self._anchos = []
        self._munecas = []       # 1.0.2 paquete C: y de la muñeca durante la zona (mano baja)
        self._altos = []         # alto de la mano (para que la zona no deje salir la muñeca)
        self._fase_i = 0
        self._fases = [("luz", 2.0), ("distancia", 2.0), ("zona", 5.0)] + \
                      [(p, PREPARAR_S + POSTURA_S) for p, _ in POSTURAS] + [("fin", 0.0)]
        self._t0 = time.monotonic()
        self._tick()

    def _tick(self):
        if not self.winfo_exists():
            return
        nombre, dur = self._fases[self._fase_i]
        ahora = time.monotonic()
        dt = ahora - self._t0
        v = getattr(self.app, "ultima_vista", None)
        self.barra.delete("all")
        if dur:
            self.barra.create_rectangle(0, 0, 360 * min(dt / dur, 1), 10, fill="#2F6FEB", outline="")
        if nombre == "luz":
            self.lbl_fase.configure(text="1. Luz")
            if v is not None and math.isfinite(v.brillo):
                self._luces.append(v.brillo)
            self.lbl_info.configure(text=self._texto_luz())
        elif nombre == "distancia":
            self.lbl_fase.configure(text="2. Distancia")
            if v is not None and v.ancho_mano is not None:
                self._anchos.append(v.ancho_mano)
            e = C.evaluar_distancia(self._anchos[-1] if self._anchos else None, mano_baja=self._mano_baja())
            self.lbl_info.configure(text={"sin_mano": t("cal_sin_mano"), "cerca": t("cal_cerca"),
                                          "lejos": t("cal_lejos"), "ok": t("cal_distancia_ok")}[e])
            if e != "ok" and dt >= dur:
                self._t0 = ahora   # se espera hasta que la distancia esté bien
                dt = 0
        elif nombre == "zona":
            self.lbl_fase.configure(text="3. Zona cómoda")
            if not getattr(self, "_incline", False):
                self.lbl_info.configure(text=t("cal_zona"))
            if v is not None and v.punta is not None:
                self.puntos.append(v.punta)
            if self._mano_baja():
                if v is not None and getattr(v, "muneca", None) is not None:
                    self._munecas.append(v.muneca[1])
                    if getattr(v, "alto_mano", None) is not None:
                        self._altos.append(v.alto_mano)
                if dt >= dur:
                    if not self.revisar_muneca():
                        self._t0 = ahora       # se repite la zona hasta que se vea la muñeca
                        dt = 0
        elif nombre == "fin":
            self._terminar()
            return
        else:
            texto = dict(POSTURAS)[nombre]
            self.lbl_fase.configure(text="4. " + t(texto))
            if dt < PREPARAR_S:
                self.lbl_info.configure(text=f"{t(texto)}… {PREPARAR_S - dt:.0f}")
            else:
                self.lbl_info.configure(text=f"{t(texto)} — sostenga")
                if v is not None and v.medidas:
                    self.muestras[nombre].append(dict(v.medidas))
        if dt >= dur:
            self._fase_i += 1
            self._t0 = ahora
        self.after(66, self._tick)

    def _mano_baja(self) -> bool:
        return bool(((getattr(self.app.cfg, "datos", None) or {}).get("zona") or {}).get("mano_baja", False))

    def revisar_muneca(self) -> bool:
        """Mano baja: la muñeca se tiene que ver en casi todos los cuadros de la zona. Si no, pide
        inclinar la pantalla (o la cámara) y empieza a medir de nuevo."""
        if MB.muneca_visible(self._munecas):
            self._incline = False
            self.lbl_info.configure(text=t("cal_mano_baja_ok"))
            return True
        self._incline = True
        self.lbl_info.configure(text=t("cal_incline"))
        self._munecas = []
        self._altos = []
        self.puntos = []
        return False

    def _texto_luz(self):
        if not self._luces:
            return t("cal_sin_mano")
        e = C.evaluar_luz(sum(self._luces) / len(self._luces))
        return {"poca": t("cal_luz_poca"), "mucha": t("cal_luz_mucha"), "ok": t("cal_luz_ok"),
                "sin_dato": t("as_sin_imagen")}[e]

    def _terminar(self):
        cfg = self.app.cfg.datos
        senas, problemas = C.calcular_umbrales(self.muestras, cfg["senas"])
        zona = C.calcular_zona(self.puntos)
        if problemas:
            nombres = {"pellizco": "pellizco", "juntos_s": "índice y corazón", "juntos_a": "índice y corazón",
                       "v_s": "la V"}
            medida = ", ".join(sorted({nombres.get(p, p) for p, _ in problemas}))
            self.lbl_fase.configure(text=t("as_repetir"))
            self.lbl_info.configure(text=t("cal_repetir", medida=medida))
            return
        nuevo = copy.deepcopy(cfg)
        nuevo["senas"] = senas
        if zona:
            nuevo["zona"].update({"x0": zona[0], "y0": zona[1], "x1": zona[2], "y1": zona[3]})
            if self._mano_baja() and self._altos:
                # la zona no baja tanto que la muñeca se salga de la imagen
                altos = sorted(self._altos)
                nuevo["zona"] = MB.recortar_zona(nuevo["zona"], altos[len(altos) // 2])
        nuevo["calibracion"] = {
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "luz": round(sum(self._luces) / len(self._luces), 1) if self._luces else None,
            "tam_mano": round(sum(self._anchos) / len(self._anchos), 3) if self._anchos else None,
        }
        self.app.cfg.datos = nuevo
        try:
            self.app.cfg.guardar(nuevo)
        except OSError:
            pass
        self.app.orden("config", copy.deepcopy(nuevo))
        self.lbl_fase.configure(text=t("cal_ok"))
        self.lbl_info.configure(text="")
        self.al_terminar(True)
