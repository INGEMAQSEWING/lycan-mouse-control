"""Arranque y cierre seguro de Lycan Mouse Control.

Orden obligatorio: DPI en la primera línea (antes de tkinter) -> registro -> argumentos ->
configuración -> salida + atexit + señales -> hilos (cámara, motor, atajos) -> interfaz.
Todo dentro de try/finally: el finally suelta todo, detiene los hilos y libera la cámara.
"""
from __future__ import annotations

import sys

from .sistema import dpi as _dpi

_NIVEL_DPI = _dpi.activar()   # PRIMERO: antes de importar tkinter o leer medidas de pantalla

import argparse  # noqa: E402
import atexit  # noqa: E402
import copy  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import queue  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402

from . import constantes as K  # noqa: E402
from . import registro  # noqa: E402
from .config import Configuracion  # noqa: E402
from .version import VERSION  # noqa: E402

log = logging.getLogger("lycan")


def argumentos(argv=None):
    p = argparse.ArgumentParser(prog="lycan_mouse_control",
                                description="Lycan Mouse Control: maneje el ratón con las manos.")
    p.add_argument("--check", action="store_true",
                   help="Prueba que el programa y MediaPipe cargan (sin cámara ni ratón) y sale.")
    p.add_argument("--minimizado", action="store_true", help="Arranca con la ventana pequeña.")
    p.add_argument("--simular", action="store_true",
                   help="Modo ensayo: no mueve el ratón real; muestra en pantalla lo que haría.")
    p.add_argument("--prueba-segundos", type=float, default=0.0,
                   help="Cierra solo después de N segundos y escribe un informe (pruebas).")
    p.add_argument("--informe", default="", help="Archivo JSON para el informe de --prueba-segundos.")
    p.add_argument("--camara", type=int, default=None, help="Número de cámara (0, 1, ...).")
    p.add_argument("--modo", choices=("2D", "3D"), default=None, help="Arrancar en 2D o 3D.")
    p.add_argument("--sin-atajos", action="store_true", help="No registra los atajos globales.")
    p.add_argument("--sin-gancho", action="store_true",
                   help="No pone el gancho de teclado (sin clic con tecla o pedal).")
    p.add_argument("--version", action="version", version=f"Lycan Mouse Control {VERSION}")
    return p.parse_args(argv)


def check() -> int:
    """Carga MediaPipe y procesa una imagen negra. No abre la cámara ni mueve el ratón."""
    try:
        import numpy as np
        from .detector import Detector
        from .nucleo import Nucleo
        from .config import por_defecto
        d = Detector(max_manos=2, complejidad=0)
        manos = d.procesar(np.zeros((480, 640, 3), np.uint8))
        d.cerrar()
        Nucleo(por_defecto()).procesar(0.0, manos)
        log.info("--check correcto (MediaPipe %.0f ms)", d.ms_ultimo)
        return 0
    except Exception:  # noqa: BLE001
        log.exception("--check falló")
        return 1


class App:
    def __init__(self, args):
        self.args = args
        self.cerrando = False
        self.ultima_vista = None
        self.root = None
        self.ventana = None
        self.indicador = None
        self.atajos = None
        self.cola_atajos: queue.Queue = queue.Queue()
        # 1.0.2 paquete A: clic con tecla o pedal
        self.gancho = None
        self.cola_gancho: queue.Queue = queue.Queue()
        self._al_grabar = None
        self._teclas_ensayo: set = set()
        self._asistente = None
        self._opciones = None
        self.cfg = Configuracion()
        self.cfg.cargar()
        # --camara y --modo valen SOLO para esta sesión: van en una copia para el motor y nunca
        # se escriben en config.json (si no, la siguiente apertura normal usaría esa cámara).
        motor_cfg = copy.deepcopy(self.cfg.datos)
        self._camara_guardada = self.cfg.datos["camara"]["indice"]
        if args.camara is not None:
            motor_cfg["camara"]["indice"] = args.camara
        if args.modo:
            motor_cfg["modo"] = args.modo
        self._modo_arranque = motor_cfg["modo"]
        from .salida import crear
        self.salida = crear(args.simular)
        if args.simular:
            self.salida.al_enviar = self._anotar_ensayo
        atexit.register(self._soltar_todo_seguro, "atexit")
        for nombre in ("SIGINT", "SIGBREAK", "SIGTERM"):
            sig = getattr(signal, nombre, None)
            if sig is not None:
                try:
                    signal.signal(sig, self._senal)
                except (ValueError, OSError):
                    pass
        from .motor import Motor
        from .sistema.sonidos import Sonidos
        self.motor = Motor(motor_cfg, self.salida)
        self.sonidos = Sonidos(bool(self.cfg.datos["comodidad"].get("sonidos", True)))
        registro.instalar_ganchos(self._al_fallar)

    # ------------------------------------------------------------ utilidades
    def salida_actual(self):
        return self.motor.salida

    def _soltar_todo_seguro(self, motivo):
        for s in {id(self.salida): self.salida, id(self.motor.salida): self.motor.salida}.values():
            try:
                s.soltar_todo(motivo)
            except Exception:  # noqa: BLE001
                pass

    def _senal(self, signum, _frame):
        self._soltar_todo_seguro(f"señal {signum}")
        if self.root is not None:
            try:
                self.root.after(0, self.salir_seguro)
                return
            except Exception:  # noqa: BLE001
                pass
        raise SystemExit(1)

    def _salir_desde_atajo(self):
        """Ctrl+Alt+X (en el hilo de atajos): suelta todo y detiene el motor YA; la ventana se
        cierra en el siguiente refresco."""
        self._soltar_todo_seguro("atajo de salir")
        self.motor.detener()

    def _al_fallar(self, exc):
        self._soltar_todo_seguro("error no atrapado")
        self.orden("error_externo", exc)

    def _anotar_ensayo(self, eventos):
        nombres = {"izq": "izquierdo", "der": "derecho", "medio": "del medio"}
        for ev in eventos:
            if ev[0] == "mover":
                continue
            if ev[0] == "boton":
                txt = f"{'Presionar' if ev[2] else 'Soltar'} botón {nombres.get(ev[1], ev[1])}"
            elif ev[0] == "pulsar":
                from .teclas import nombre_envio
                txt = f"Tecla {nombre_envio(ev[1])}"
            elif ev[0] == "rueda":
                txt = f"Rueda {'acercar' if ev[1] > 0 else 'alejar'} ({ev[1]:+d})"
            elif ev[0] == "tecla":
                # soltar_todo suelta Shift/Ctrl/Alt por seguridad aunque no estén abajo: no se anota
                if ev[2]:
                    self._teclas_ensayo.add(ev[1])
                elif ev[1] in self._teclas_ensayo:
                    self._teclas_ensayo.discard(ev[1])
                else:
                    continue
                txt = f"{'Presionar' if ev[2] else 'Soltar'} {ev[1].capitalize()}"
            else:
                continue
            log.info("[ensayo] %s", txt)

    # ------------------------------------------------ 1.0.2: gancho de teclado
    def _evento_gancho(self, ev):
        """Llega desde el hilo del gancho: solo se reparte a colas (nada de tkinter aquí)."""
        if ev and ev[0] in ("tecla_clic", "tecla_repite", "frenar"):
            self.motor.ordenes.put(tuple(ev))
        else:
            self.cola_gancho.put(tuple(ev))

    def grabar_tecla(self, al_terminar) -> bool:
        """Opciones / asistente: la próxima tecla se graba. al_terminar(evento) se llama en el hilo
        de la interfaz con ("grabada", vk, scan, extendida) o ("rechazada", vk). False si no hay
        gancho (por ejemplo, con --sin-gancho)."""
        if self.gancho is None:
            return False
        self._al_grabar = al_terminar
        self.gancho.grabar(True)
        return True

    def cancelar_grabar(self):
        self._al_grabar = None
        if self.gancho is not None:
            self.gancho.grabar(False)

    def _revisar_gancho(self):
        if self.cerrando:
            return
        from .ui.textos import t
        while True:
            try:
                ev = self.cola_gancho.get_nowait()
            except queue.Empty:
                break
            if ev[0] in ("grabada", "rechazada"):
                cb = self._al_grabar
                if ev[0] == "grabada":
                    self._al_grabar = None
                if cb is not None:
                    try:
                        cb(ev)
                    except Exception:  # noqa: BLE001
                        log.exception("Error al grabar la tecla")
            elif ev[0] == "gancho_perdido":
                self.mostrar_aviso(t("aviso_gancho_perdido"), 6)
        try:
            self.root.after(100, self._revisar_gancho)
        except Exception:  # noqa: BLE001
            pass

    def _iniciar_gancho(self):
        if getattr(self.args, "sin_gancho", False) or sys.platform != "win32":
            return
        try:
            from .sistema.teclado import GanchoTeclado
            self.gancho = GanchoTeclado(self.motor.estado_gancho, self._evento_gancho)
            self.gancho.start()
        except Exception:  # noqa: BLE001
            log.exception("No se pudo poner el gancho de teclado")
            self.gancho = None

    def orden(self, nombre, *args):
        if nombre == "config" and args and getattr(self.args, "camara", None) is not None:
            cfg = args[0]
            try:
                if cfg["camara"]["indice"] == self._camara_guardada:
                    cfg["camara"]["indice"] = self.args.camara      # sigue la cámara de esta sesión
            except (KeyError, TypeError):
                pass
        self.motor.ordenes.put((nombre,) + args)

    def modo_vigente(self) -> str:
        """El modo en que está el motor AHORA (lo cambia el botón 2D/3D o Ctrl+Alt+D)."""
        nucleo = getattr(self.motor, "nucleo", None)
        modo = getattr(nucleo, "modo", None)
        return modo if modo in ("2D", "3D") else self.cfg.datos.get("modo", "2D")

    def al_cambiar_modo(self, modo: str):
        """El motor avisó un cambio de modo: la configuración en memoria lo sigue."""
        if modo in ("2D", "3D"):
            self.cfg.datos["modo"] = modo

    def guardar_config(self, datos: dict | None = None) -> bool:
        """Guarda sin colgarse; si la carpeta no deja escribir, lo dice en la ventana."""
        if self.cfg.guardar_seguro(datos):
            return True
        from .ui.textos import t
        if getattr(self.cfg, "solo_lectura", False):
            self.mostrar_aviso(t("aviso_config_solo_lectura"), 10)
        else:
            self.mostrar_aviso(t("aviso_no_guardo"), 10)
        return False

    # ------------------------------------------------------------ ventanas
    def abrir_opciones(self):
        """Una sola ventana de Opciones a la vez (con dos, «Cancelar» en una borraba lo que se
        había guardado en la otra). Si ya está abierta, se trae al frente."""
        o = getattr(self, "_opciones", None)
        if o is not None:
            try:
                if o.win.winfo_exists():
                    o.win.deiconify()
                    o.win.lift()
                    o.win.focus_force()
                    return o
            except Exception:  # noqa: BLE001
                pass
        from .ui.opciones import VentanaOpciones
        self._opciones = VentanaOpciones(self.root, self)
        return self._opciones

    def abrir_asistente(self):
        """Un solo asistente a la vez: dos asistentes se pisaban el modo ensayo (al cerrar uno, el
        otro seguía diciendo que el ratón no haría nada, pero ya manejaba el ratón real)."""
        a = self._asistente
        if a is not None:
            try:
                if a.win.winfo_exists():
                    a.win.deiconify()
                    a.win.lift()
                    a.win.focus_force()
                    return a
            except Exception:  # noqa: BLE001
                pass
        from .ui.asistente import Asistente
        self._asistente = Asistente(self.root, self)
        return self._asistente

    def asistente_cerrado(self, asistente):
        if self._asistente is asistente:
            self._asistente = None

    def abrir_ayuda(self):
        from .ui.ayuda import VentanaAyuda
        modo = self.ultima_vista.modo if self.ultima_vista else self.modo_vigente()
        VentanaAyuda(self.root, modo, bool(self.cfg.datos["zoom"].get("una_mano")),
                     atajos=self.cfg.datos.get("atajos"))

    def abrir_registros(self):
        registro.abrir_carpeta()

    def reiniciar_admin(self):
        from tkinter import messagebox
        if messagebox.askyesno(K.NOMBRE_APP, "¿Volver a abrir Lycan Mouse Control como administrador?",
                               parent=self.root):
            from .sistema import ventanas_win as vw
            self._soltar_todo_seguro("reiniciar como administrador")
            if vw.reiniciar_como_admin(sys.argv[1:]):
                self.salir_seguro()

    def alternar_ventana(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.attributes("-topmost", True)
        else:
            self.root.withdraw()

    def mostrar_aviso(self, texto, segundos: float = 5.0):
        if self.ventana:
            self.ventana.mostrar_aviso(texto, segundos)

    def al_pintar(self, vista):
        if self.indicador is not None:
            try:
                self.indicador.actualizar(vista)
            except Exception:  # noqa: BLE001
                pass

    def indicador_aviso(self, aviso):
        pass

    def aplicar_comodidad(self):
        com = self.cfg.datos["comodidad"]
        self.sonidos.activos = bool(com.get("sonidos", True))
        if self.indicador is not None:
            self.indicador.activo = bool(com.get("aviso_cursor", True))
        try:
            self.root.attributes("-alpha", float(com.get("opacidad", 0.94)))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ ciclo de vida
    def correr(self) -> int:
        import tkinter as tk
        from .sistema.atajos import HiloAtajos
        from .ui.indicador_cursor import Indicador
        from .ui.ventana_principal import VentanaPrincipal
        codigo = 0
        try:
            self.motor.start()
            if not self.args.sin_atajos:
                self.atajos = HiloAtajos(self.cfg.datos["atajos"], self.cola_atajos,
                                         directos={"salir": self._salir_desde_atajo})
                self.atajos.start()
            self._iniciar_gancho()
            self.root = tk.Tk()
            self.ventana = VentanaPrincipal(self.root, self)
            self.root.update_idletasks()
            self.ventana.aplicar_no_activar()
            self.indicador = Indicador(self.root, self.salida.posicion_cursor, simulado=self.args.simular)
            self.aplicar_comodidad()
            if self.args.minimizado and not self.ventana.mini:
                self.ventana.alternar_mini()
            if self.cfg.aviso:
                self.ventana.mostrar_aviso(self.cfg.aviso)
            if registro.ERROR:
                from .ui.textos import t
                self.root.after(300, lambda: self.ventana.mostrar_aviso(t("aviso_sin_registro"), 8))
            if self.args.simular:
                self.root.after(500, lambda: self.ventana.mostrar_aviso(
                    "MODO ENSAYO: el ratón no hará nada (solo se muestra lo que haría).", 6))
            if self.atajos is not None:
                self.root.after(800, self._avisar_atajos)
            self.root.after(1500, self._revisar_camara)
            self.root.after(200, self._revisar_gancho)
            if self.cfg.datos.get("primera_vez") and not self.args.prueba_segundos:
                self.root.after(600, self.abrir_asistente)
            if self.args.prueba_segundos:
                self.root.after(int(self.args.prueba_segundos * 1000), self.salir_seguro)
            self.root.mainloop()
        except KeyboardInterrupt:
            codigo = 1
        except Exception:  # noqa: BLE001
            log.exception("Error en la interfaz")
            codigo = 1
        finally:
            self._finalizar()
        return codigo

    def _avisar_atajos(self):
        if self.atajos and self.atajos.fallidos:
            self.ventana.mostrar_aviso("\n".join(txt for _, txt in self.atajos.fallidos), 8)

    def _revisar_camara(self):
        if self.cerrando:
            return
        cam = getattr(self.motor, "camara", None)
        estado = getattr(cam, "estado", "")
        from .ui.textos import t
        if self.motor.error_inicio:
            # el detalle técnico queda en el registro; al usuario, un texto claro
            self.ventana.mostrar_aviso(t("aviso_no_arranca"), 10)
        elif estado == "NO_ABRE":
            self.ventana.mostrar_aviso(t("aviso_no_camara"), 8)
            self.root.after(8000, self._revisar_camara)
            return
        elif estado == "OCUPADA":
            self.ventana.mostrar_aviso(t("aviso_camara_ocupada"), 8)
            self.root.after(8000, self._revisar_camara)
            return
        elif estado == "PERDIDA":
            # se repite mientras siga perdida (antes el aviso salía una vez y a los 5 s quedaba
            # la imagen congelada como si todo funcionara)
            self.ventana.mostrar_aviso(t("aviso_camara_perdida"), 8)
            self.root.after(8000, self._revisar_camara)
            return
        self.root.after(5000, self._revisar_camara)

    def salir_seguro(self):
        """Soltar todo -> detener motor -> soltar cámara -> anular atajos -> guardar -> cerrar."""
        if self.cerrando:
            return
        self.cerrando = True
        self._soltar_todo_seguro("salir")
        log.info("Saliendo")
        try:
            if self.ventana:
                x, y = self.ventana.posicion()
                self.cfg.datos["ventana"]["x"], self.cfg.datos["ventana"]["y"] = int(x), int(y)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.indicador:
                self.indicador.destruir()
            if self.root:
                self.root.destroy()
        except Exception:  # noqa: BLE001
            pass

    def _finalizar(self):
        self.cerrando = True
        self._soltar_todo_seguro("fin")
        try:
            self.motor.detener()
            self.motor.join(timeout=2.0)
        except Exception:  # noqa: BLE001
            pass
        self._soltar_todo_seguro("fin del motor")
        if self.atajos is not None:
            self.atajos.detener()
        if self.gancho is not None:
            try:
                self.gancho.detener()
            except Exception:  # noqa: BLE001
                pass
        try:
            # el modo se guarda solo si el usuario lo cambió en esta sesión (no el de --modo)
            if self.motor.nucleo is not None and self.motor.nucleo.modo != self._modo_arranque:
                self.cfg.datos["modo"] = self.motor.nucleo.modo
            if not self.args.simular or not self.cfg.ruta.exists():
                self.cfg.guardar_seguro()
        except Exception:  # noqa: BLE001
            log.exception("No se pudo guardar la configuración")
        self.sonidos.cerrar()
        if self.args.prueba_segundos:
            self._informe()

    def _informe(self):
        r = self.motor.stats.resumen()
        cam = getattr(self.motor, "camara", None)
        r.update({
            "camara": getattr(cam, "estado", ""),
            "camara_backend": getattr(cam, "backend", ""),
            "camara_fps": round(getattr(cam, "fps_reales", 0.0), 1),
            "mediapipe_ms": round(getattr(self.motor.detector, "ms_ultimo", 0.0), 1),
            "error_inicio": self.motor.error_inicio,
            "errores_nucleo": len(self.motor.nucleo.errores) if self.motor.nucleo else None,
            "estado_final": self.motor.nucleo.estado if self.motor.nucleo else None,
            "todo_suelto": self.salida.todo_suelto(),
            "simulada": bool(self.args.simular),
            "eventos_simulados": getattr(self.salida, "n_eventos", len(getattr(self.salida, "eventos", ()))),
            "dpi": _NIVEL_DPI,
        })
        log.info("Informe: %s", r)
        texto = json.dumps(r, ensure_ascii=False)
        if self.args.informe:
            try:
                with open(self.args.informe, "w", encoding="utf-8") as f:
                    f.write(texto)
            except OSError:
                pass
        try:
            print(texto)
        except Exception:  # noqa: BLE001
            pass


def ya_abierto_en_prueba(args):
    """Prueba automática con otra copia abierta: nunca un cuadro modal que deje el proceso
    colgado. Anota, escribe el informe y sale con código 2."""
    log.warning("Ya hay otra copia abierta: la prueba no se ejecuta")
    texto = json.dumps({"error": "ya abierto"}, ensure_ascii=False)
    if args.informe:
        try:
            with open(args.informe, "w", encoding="utf-8") as f:
                f.write(texto)
        except OSError:
            pass
    try:
        print(texto)
    except Exception:  # noqa: BLE001
        pass
    sys.exit(2)


def main(argv=None):
    registro.proteger_salida_estandar()
    args = argumentos(argv)
    ruta_log = registro.configurar()
    if args.check:
        registro.anotar_inicio({"modo": "--check", "DPI": _NIVEL_DPI})
        sys.exit(check())
    from .sistema import pantallas, ventanas_win
    mutex = K.MUTEX + ("Ensayo" if args.simular else "")
    if not ventanas_win.instancia_unica(mutex):
        if args.prueba_segundos:
            ya_abierto_en_prueba(args)
        ventanas_win.traer_al_frente(K.NOMBRE_APP)
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showinfo(K.NOMBRE_APP, "Lycan Mouse Control ya está abierto.", parent=r)
            r.destroy()
        except Exception:  # noqa: BLE001
            pass
        sys.exit(0)
    registro.anotar_inicio({"DPI": _NIVEL_DPI, "Monitores": pantallas.monitores(),
                            "Simular": args.simular, "Registro": ruta_log})
    try:
        app = App(args)
    except Exception:  # noqa: BLE001
        # sin esto, en el .exe sin consola el programa simplemente no abría y no quedaba rastro
        log.exception("No se pudo abrir Lycan Mouse Control")
        if not args.prueba_segundos:
            try:
                import tkinter as tk
                from tkinter import messagebox
                from .ui.textos import t
                r = tk.Tk()
                r.withdraw()
                messagebox.showerror(K.NOMBRE_APP, t("aviso_no_abre"), parent=r)
                r.destroy()
            except Exception:  # noqa: BLE001
                pass
        sys.exit(1)
    codigo = app.correr()
    sys.exit(codigo)


if __name__ == "__main__":
    main()
