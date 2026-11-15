"""Hilo MOTOR: último cuadro -> MediaPipe -> núcleo (señas + estados) -> salida.

Es el único que envía al ratón (salvo ``soltar_todo``, que es seguro desde cualquier hilo).
Deja para la interfaz un estado para pintar en una cola de 1 (se descarta el viejo).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from . import constantes as K
from . import perfiles as P
from .acciones import Aviso, Sonido, SoltarTodo, describir, es_de_entrada
from .mano_baja import VigiaManoBaja
from .mapeo import Mapeo
from .nucleo import Nucleo
from .salida.base import ErrorEnvio
from .sistema.teclado import EstadoGancho

log = logging.getLogger("lycan")

SIN_CUADROS_S = 1.0      # sin cuadros nuevos por más de esto, los cuadros/s se muestran en 0


@dataclass
class Vista:
    """Lo que la interfaz necesita para pintar un cuadro."""
    estado: str = K.PAUSA
    modo: str = "2D"
    perfil: str = "Genérico"
    etiqueta: str = ""
    progreso: float = 0.0
    sub: str = ""
    imagen: np.ndarray | None = None          # RGB 320x240
    fps: float = 0.0
    latencia_ms: float = 0.0
    medidas: dict = field(default_factory=dict)
    sena: str = ""
    manos: int = 0
    camara: str = ""
    cerca_borde: bool = False
    ultima_accion: str = ""
    simulada: bool = False
    brillo: float = float("nan")              # 0..255 (para el aviso de luz)
    punta: tuple | None = None                # (u, v) de la punta del índice principal
    ancho_mano: float | None = None           # |0-17| en la imagen (distancia a la cámara)
    cursor: tuple | None = None               # posición del puntero (simulada o real)
    eventos_ensayo: int = 0                   # cuántos eventos lleva la salida simulada
    cuentas: dict = field(default_factory=dict)   # 1.0.2: clics con tecla, anular y meñique
    gesto: str | None = None                  # revisión 1.0.2: gesto en curso (orbita1, inercia...)
    # 1.0.2 paquete C (mano baja): muñeca (u, v) y alto de la mano (de la muñeca a la punta más alta)
    muneca: tuple | None = None
    alto_mano: float | None = None


def _color_bgr(hexa: str):
    hexa = hexa.lstrip("#")
    r, g, b = int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16)
    return (b, g, r)


class Estadisticas:
    def __init__(self):
        self.t_cuadros: deque = deque(maxlen=120)
        self.latencias: deque = deque(maxlen=600)
        self.fps_hist: deque = deque(maxlen=3600)
        self.total = 0

    def cuadro(self, t: float):
        self.t_cuadros.append(t)
        self.total += 1

    @property
    def fps(self) -> float:
        if len(self.t_cuadros) < 2:
            return 0.0
        dt = self.t_cuadros[-1] - self.t_cuadros[0]
        return (len(self.t_cuadros) - 1) / dt if dt > 0 else 0.0

    def fps_reciente(self, ventana: float = 2.0) -> float:
        """Cuadros/s de los últimos ``ventana`` segundos (para no avisar con datos viejos justo
        después de que la cámara se recupera)."""
        ts = self.t_cuadros
        if len(ts) < 2:
            return 0.0
        t1 = ts[-1]
        n = sum(1 for t in ts if t >= t1 - ventana)
        lapso = min(ventana, t1 - ts[0])
        return (n - 1) / lapso if lapso > 0 else 0.0

    def latencia(self, ms: float):
        self.latencias.append(ms)

    def resumen(self) -> dict:
        lat = sorted(self.latencias)
        p95 = lat[int(0.95 * (len(lat) - 1))] if lat else 0.0
        return {"fps": round(self.fps, 1), "latencia_media_ms": round(sum(lat) / len(lat), 1) if lat else 0.0,
                "latencia_p95_ms": round(p95, 1), "cuadros": self.total}


class Motor(threading.Thread):
    def __init__(self, config: dict, salida, camara=None, detector=None, sistema: bool = True):
        super().__init__(daemon=True, name="motor")
        self.cfg = config
        self.salida = salida
        self.camara = camara
        self.detector = detector
        self.sistema = sistema                 # False en pruebas: no consulta Windows
        self.ordenes: queue.Queue = queue.Queue()
        self.vistas: queue.Queue = queue.Queue(maxsize=1)
        self.avisos: queue.Queue = queue.Queue()
        self._parar = threading.Event()
        self.stats = Estadisticas()
        self.monitor = None
        self.mapeo = None
        self.nucleo = None
        self.perfil_actual = P.GENERICO
        self.ultima_accion = ""
        self._dibujo_fino = bool((config.get("puntero") or {}).get("dibujo_fino", False))
        self.listo = threading.Event()
        self.error_inicio: str | None = None
        self._t_rev_admin = 0.0
        self._t_rev_perfil = 0.0
        self._t_rev_pantalla = 0.0
        self._t_rev_escritorio = 0.0
        self._escritorio = None                # escritorio virtual (x, y, ancho, alto) en uso
        self._t_reintento = 0.0
        self._t_lento = None
        self._aviso_lento = False
        self._t_brazo = None
        self._aviso_brazo = False
        self._vigia_baja = VigiaManoBaja()     # 1.0.2 paquete C
        self._t_activo_acum = 0.0
        self._t_ult_descanso = 0.0
        self._ult_t = None
        self._t_perf = time.perf_counter()
        self._sugerido = None
        self._salida_real = None
        # 1.0.2 paquete A: lo que el gancho de teclado lee (tecla elegida y si está ACTIVO)
        self.estado_gancho = EstadoGancho.desde_config(config.get("tecla_clic"))
        self.tecla_limite_s = None             # seguridad de la tecla (valores de Windows)

    # ------------------------------------------------------------- arranque
    def _preparar(self):
        from .sistema import pantallas
        pant = (self.cfg.get("pantalla") or {}).get("monitor", "principal")
        self.monitor = pantallas.elegir(pant) if self.sistema else None
        if self.sistema:
            self._escritorio = tuple(pantallas.escritorio_virtual())
        z = self.cfg["zona"]
        cam = self.cfg["camara"]
        kw = {"aspecto_cam": cam["ancho"] / cam["alto"]}
        if self.monitor is not None:
            kw["monitor"] = self.monitor
        self.mapeo = Mapeo((z["x0"], z["y0"], z["x1"], z["y1"]), **kw)
        perf = self.cfg["perfiles"]
        if not perf.get("automatico", True):
            self.perfil_actual = P.obtener(perf.get("manual", "generico"), perf.get("personalizados"))
        self.nucleo = Nucleo(self.cfg, self.perfil_actual, self.mapeo, pos_cursor=self.salida.posicion_cursor)
        self.nucleo.maquina.poner_dibujo_fino(self._dibujo_fino)
        if self.sistema:
            from .sistema.teclado import limite_repeticion_s
            try:
                self.tecla_limite_s = limite_repeticion_s()
            except Exception:  # noqa: BLE001
                self.tecla_limite_s = None
        self._poner_limite_tecla()
        if self.sistema and hasattr(self.salida, "actualizar_pantalla"):
            self.salida.actualizar_pantalla()
        if self.camara is None:
            from .captura import Camara
            self.camara = Camara(cam["indice"], cam["ancho"], cam["alto"], cam["fps"])
            self.camara.al_perder = lambda: self.ordenes.put(("camara_perdida",))
        if not self.camara.is_alive() and hasattr(self.camara, "start"):
            self.camara.start()
        if self.detector is None:
            from .detector import Detector
            self.detector = Detector(max_manos=2)

    def run(self):
        try:
            self._preparar()
        except Exception as e:  # noqa: BLE001
            log.exception("No se pudo arrancar el motor")
            self.error_inicio = repr(e)
            self.salida.soltar_todo("error al arrancar")
            self.listo.set()
            return
        self.listo.set()
        numero = 0
        self._ult_t = time.perf_counter()
        try:
            while not self._parar.is_set():
                try:
                    numero = self._vuelta(numero)
                except Exception as e:  # noqa: BLE001
                    # Cualquier error fuera del núcleo (revisiones, envío, dibujo, avisos...) NO
                    # puede matar el hilo: el control quedaba muerto en silencio. Se suelta todo,
                    # se pausa con aviso (3 errores en 1 minuto = fatal) y se sigue.
                    self._error_en_vuelta(e)
        finally:
            self.salida.soltar_todo("fin del motor")
            try:
                if hasattr(self.camara, "detener"):
                    self.camara.detener()
            except Exception:  # noqa: BLE001
                pass
            try:
                if hasattr(self.detector, "cerrar"):
                    self.detector.cerrar()
            except Exception:  # noqa: BLE001
                pass

    def _vuelta(self, numero: int) -> int:
        """Una vuelta del bucle: órdenes, último cuadro, MediaPipe y un paso. Devuelve el número
        del último cuadro procesado."""
        self._atender_ordenes()
        cuadro = self.camara.ultimo(numero, espera=0.1)
        ahora = time.perf_counter()
        if cuadro is None:
            # sin cuadro nuevo: igual corren los relojes (pausa sin mano, etc.)
            if ahora - (self._ult_t or ahora) > 0.25:
                self._paso(ahora, [], None)
            return numero
        numero = cuadro.numero
        try:
            manos = self.detector.procesar(cuadro.imagen)
        except Exception as e:  # noqa: BLE001
            log.exception("Error en MediaPipe")
            self._aplicar(self.nucleo.por_error(cuadro.t_captura, e))
            return numero
        self._paso(cuadro.t_captura, manos, cuadro)
        return numero

    # ------------------------------------------------ 1.0.2: gancho de teclado
    def _poner_limite_tecla(self):
        if self.nucleo is not None and self.tecla_limite_s:
            self.nucleo.maquina.tecla_limite_s = float(self.tecla_limite_s)

    def sincronizar_gancho(self):
        """El gancho decide con esto si traga la tecla (solo con el control ACTIVO)."""
        if self.nucleo is None:
            return
        m = self.nucleo.maquina
        self.estado_gancho.motor_activo = m.base == K.ACTIVO
        self.estado_gancho.inercia_activa = bool(getattr(m, "inercia_activa", False))

    def _error_en_vuelta(self, e: Exception):
        log.exception("Error en el motor: se suelta todo y se pausa")
        try:
            self.salida.soltar_todo("error en el motor")
        except Exception:  # noqa: BLE001
            pass
        try:
            self._aplicar_orden(self.nucleo.por_error(time.perf_counter(), e).acciones)
        except Exception:  # noqa: BLE001
            log.exception("Tampoco se pudo pausar tras el error")
            self.avisos.put(Aviso("error"))
        if self.nucleo is not None and getattr(self.nucleo, "fatal", False):
            self.avisos.put(Aviso("fatal"))
            self._parar.set()
        time.sleep(0.05)          # si el error se repite en cada vuelta, no se come un núcleo

    def detener(self):
        self._parar.set()

    # ------------------------------------------------------------- un paso
    def _paso(self, t, manos, cuadro):
        self._ult_t = time.perf_counter()
        self._revisiones(t)
        res = self.nucleo.procesar(t, manos)
        self._aplicar(res)
        self.sincronizar_gancho()
        if cuadro is not None:
            self.stats.cuadro(cuadro.t_captura)
            self.stats.latencia((time.perf_counter() - cuadro.t_captura) * 1000.0)
            self._comodidad(t, res)
        self._publicar(res, cuadro)
        if self.nucleo.fatal:
            self.avisos.put(Aviso("fatal"))
            self._parar.set()

    def _aplicar(self, res):
        acciones = res.acciones if hasattr(res, "acciones") else res
        try:
            for a in self.salida.aplicar(acciones):
                self.avisos.put(a)
        except ErrorEnvio as e:
            log.warning("Windows no aceptó los eventos (%s): se pausa", e)
            self.salida.soltar_todo("SendInput bloqueado")
            self._aplicar_orden(self.nucleo.bloquear(time.perf_counter(), "envio"))
            self._t_reintento = time.perf_counter()
        for a in acciones:
            if isinstance(a, (Aviso, Sonido)):
                self.avisos.put(a)
            elif es_de_entrada(a):
                self.ultima_accion = describir(a)
                if isinstance(a, SoltarTodo):
                    log.info("Soltar todo: %s", a.motivo)

    def _aplicar_orden(self, acciones):
        try:
            self.salida.aplicar(acciones)
        except ErrorEnvio:
            self.salida.soltar_todo("orden")
        for a in acciones:
            if isinstance(a, (Aviso, Sonido)):
                self.avisos.put(a)

    # ------------------------------------------------------------- órdenes
    def _atender_ordenes(self):
        while True:
            try:
                o = self.ordenes.get_nowait()
            except queue.Empty:
                return
            t = time.perf_counter()
            nombre = o[0]
            try:
                if nombre == "pausar":
                    self._aplicar_orden(self.nucleo.alternar_pausa(t))
                    log.info("Atajo: estado %s", self.nucleo.estado)
                elif nombre == "solo_pausar":
                    self._aplicar_orden(self.nucleo.pausar(t, o[1] if len(o) > 1 else "pausa"))
                elif nombre == "modo":
                    modo = o[1] if len(o) > 1 and o[1] else ("2D" if self.nucleo.modo == "3D" else "3D")
                    self.cfg["modo"] = modo
                    self._aplicar_orden(self.nucleo.cambiar_modo(t, modo))
                    girar = (self.cfg.get("orbita") or {}).get("girar", "un_puno")
                    self.avisos.put(Aviso("modo", modo + ("_dos" if modo == "3D" and girar == "dos_punos" else "")))
                    log.info("Modo %s", modo)
                elif nombre == "dibujo_fino":
                    self._dibujo_fino = not self._dibujo_fino if len(o) < 2 else bool(o[1])
                    self.nucleo.maquina.poner_dibujo_fino(self._dibujo_fino)
                    self.avisos.put(Aviso("dibujo_fino", "si" if self._dibujo_fino else "no"))
                elif nombre == "perfil":
                    clave = o[1]
                    perf = self.cfg["perfiles"]
                    if clave is None:
                        perf["automatico"] = True
                    else:
                        perf["automatico"] = False
                        perf["manual"] = clave
                        self._cambiar_perfil(P.obtener(clave, perf.get("personalizados")))
                elif nombre == "config":
                    self._nueva_config(o[1])
                elif nombre == "ensayo":
                    self._poner_ensayo(bool(o[1]), o[2] if len(o) > 2 else None)
                elif nombre == "camara_perdida":
                    self.salida.soltar_todo("cámara perdida")
                    self._aplicar_orden(self.nucleo.pausar(t, "cámara perdida"))
                    self.avisos.put(Aviso("camara_perdida"))
                elif nombre == "error_externo":
                    self.salida.soltar_todo("error")
                    self._aplicar(self.nucleo.por_error(t, o[1] if len(o) > 1 else RuntimeError("error")))
                elif nombre == "tecla_clic":
                    # ("tecla_clic", abajo, t) del gancho de teclado
                    t_tecla = o[2] if len(o) > 2 else t
                    self._aplicar(self.nucleo.maquina.tecla_clic(t_tecla, bool(o[1])))
                elif nombre == "tecla_repite":
                    self.nucleo.maquina.tecla_repite(o[1] if len(o) > 1 else t)
                elif nombre == "frenar":
                    self._aplicar(self.nucleo.maquina.frenar(t))
                elif nombre == "otra_tecla":
                    self.nucleo.maquina.otra_tecla(o[1] if len(o) > 1 else t)
            except Exception as e:  # noqa: BLE001
                log.exception("Error atendiendo la orden %s", nombre)
                self._aplicar(self.nucleo.por_error(t, e))
            self.sincronizar_gancho()

    def _poner_ensayo(self, si: bool, salida_ensayo=None):
        """Asistente: mientras practica se usa una salida simulada (nada llega a Windows)."""
        t = time.perf_counter()
        self.salida.soltar_todo("cambio a modo ensayo" if si else "fin del modo ensayo")
        if si:
            if self._salida_real is None:
                self._salida_real = self.salida
            from .salida.simulada import SalidaSimulada
            self.salida = salida_ensayo or SalidaSimulada()
        elif self._salida_real is not None:
            self.salida = self._salida_real
            self._salida_real = None
        self.nucleo.maquina.pos_cursor = self.salida.posicion_cursor
        self._aplicar_orden(self.nucleo.pausar(t, "modo ensayo"))

    def _nueva_config(self, cfg):
        """Opciones guardadas: se rearma el núcleo (todo suelto y en pausa)."""
        t = time.perf_counter()
        self.salida.soltar_todo("cambio de opciones")
        estaba_activo = self.nucleo.maquina.base == K.ACTIVO
        cam_antes, cam_nueva = self.cfg.get("camara"), cfg.get("camara")
        self.cfg = cfg
        if cam_antes != cam_nueva and hasattr(self.camara, "detener") and self.sistema:
            # otra cámara o resolución: se vuelve a abrir
            from .captura import Camara
            try:
                self.camara.detener()
            except Exception:  # noqa: BLE001
                pass
            self.camara = Camara(cam_nueva["indice"], cam_nueva["ancho"], cam_nueva["alto"], cam_nueva["fps"])
            self.camara.al_perder = lambda: self.ordenes.put(("camara_perdida",))
            self.camara.start()
        z = cfg["zona"]
        from .sistema import pantallas
        if self.sistema:
            self.monitor = pantallas.elegir((cfg.get("pantalla") or {}).get("monitor", "principal"))
            self.mapeo.cambiar_monitor(self.monitor)
        self.mapeo.cambiar_zona((z["x0"], z["y0"], z["x1"], z["y1"]))
        self.nucleo = Nucleo(cfg, self.perfil_actual, self.mapeo, pos_cursor=self.salida.posicion_cursor)
        self.estado_gancho.poner_config(cfg.get("tecla_clic"))
        self._poner_limite_tecla()
        self._dibujo_fino = bool(cfg["puntero"].get("dibujo_fino", False))
        self.nucleo.maquina.poner_dibujo_fino(self._dibujo_fino)
        if estaba_activo:
            self.nucleo.maquina.activar(t)

    def _cambiar_perfil(self, perfil):
        if perfil.clave == self.perfil_actual.clave:
            return
        self.perfil_actual = perfil
        self._aplicar_orden(self.nucleo.cambiar_perfil(time.perf_counter(), perfil))
        log.info("Perfil: %s", perfil.nombre)
        if perfil.modo_sugerido == "3D" and self.nucleo.modo == "2D" and self._sugerido != perfil.clave:
            self._sugerido = perfil.clave
            self.avisos.put(Aviso("sugerir_3d", perfil.nombre))

    # ------------------------------------------------------------- revisiones
    def _revisiones(self, t):
        if not self.sistema:
            return
        ahora = time.perf_counter()
        from .sistema import ventanas_win as vw
        if ahora - self._t_rev_admin >= 0.5:
            self._t_rev_admin = ahora
            try:
                self.salida.foco_propio = vw.es_propia()
                bloqueado = vw.primer_plano_bloqueado() and not self.salida.simulada
            except OSError:
                bloqueado = False
            m = self.nucleo.maquina
            if bloqueado and m.base != K.BLOQUEADO:
                log.warning("La ventana activa es de administrador: se pausa el envío")
                self._aplicar_orden(self.nucleo.bloquear(t, "admin"))
            elif not bloqueado and m.base == K.BLOQUEADO and m.motivo_bloqueo == "admin":
                self._aplicar_orden(self.nucleo.desbloquear(t))
            if m.base == K.BLOQUEADO and m.motivo_bloqueo == "envio" and ahora - self._t_reintento >= 1.0:
                self._t_reintento = ahora
                if self.salida.probar():
                    self._aplicar_orden(self.nucleo.desbloquear(t))
        if ahora - self._t_rev_perfil >= 1.0:
            self._t_rev_perfil = ahora
            perf = self.cfg["perfiles"]
            if perf.get("automatico", True):
                try:
                    if not vw.es_propia():
                        exe = vw.exe_ventana_activa()
                        if exe:
                            estilo = P.estilo_freecad() if P.nombre_exe(exe) == "freecad.exe" else None
                            self._cambiar_perfil(P.perfil_para_exe(exe, perf.get("personalizados"),
                                                                   estilo_freecad=estilo))
                except OSError:
                    pass
        if ahora - self._t_rev_escritorio >= 0.5:
            # GetSystemMetrics es muy barato: así se nota enseguida si se conectó o desconectó
            # un monitor aunque la pantalla principal siga igual
            self._t_rev_escritorio = ahora
            from .sistema import pantallas
            try:
                if pantallas.escritorio_virtual() != self._escritorio:
                    self._revisar_pantalla()
            except OSError:
                pass
        if ahora - self._t_rev_pantalla >= 5.0:
            self._t_rev_pantalla = ahora
            try:
                self._revisar_pantalla()
            except OSError:
                pass
        if ahora - self._t_perf >= 60.0:
            self._t_perf = ahora
            r = self.stats.resumen()
            log.info("Rendimiento: %.1f cuadros/s, latencia media %.0f ms (p95 %.0f ms)",
                     r["fps"], r["latencia_media_ms"], r["latencia_p95_ms"])

    def _revisar_pantalla(self) -> bool:
        """Vuelve a leer el escritorio virtual y el monitor elegido. Si cambió cualquiera de los
        dos (también al conectar o desconectar un monitor que NO es el principal: el escritorio
        virtual crece o se encoge y SendInput tiene que usar el tamaño nuevo), se rearma el
        mapeo, el puntero y la salida. Devuelve True si hubo cambio."""
        from .sistema import pantallas
        escr = tuple(pantallas.escritorio_virtual())
        mon = pantallas.elegir((self.cfg.get("pantalla") or {}).get("monitor", "principal"))
        if mon == self.monitor and escr == self._escritorio:
            return False
        log.info("Cambió la pantalla: monitor %s, escritorio %s", mon, escr)
        self._escritorio = escr
        self.monitor = mon
        self.mapeo.cambiar_monitor(mon)
        self.nucleo.maquina.puntero.reset()
        for sal in (self.salida, self._salida_real):
            if sal is not None and hasattr(sal, "actualizar_pantalla"):
                sal.actualizar_pantalla()
        return True

    def _comodidad(self, t, res):
        fps = self.stats.fps
        # No se exigen 60 cuadros (a 1 cuadro/s eso es más de un minuto): bastan 5 y 5 segundos.
        if len(self.stats.t_cuadros) >= 5 and fps and fps < 20 and self.stats.fps_reciente() < 20:
            if self._t_lento is None:
                self._t_lento = t
            elif t - self._t_lento > 5 and not self._aviso_lento:
                self._aviso_lento = True
                self.avisos.put(Aviso(self._causa_lentitud()))
        else:
            self._t_lento = None
        com = self.cfg.get("comodidad") or {}
        p = self.nucleo.seguidor.principal
        activo = self.nucleo.maquina.base == K.ACTIVO
        zona = self.cfg.get("zona") or {}
        mano_baja = bool(zona.get("mano_baja", False))
        if mano_baja and p is not None and activo:
            # 1.0.2 paquete C: con la mano baja no hay aviso de brazo alto; si la mano sube por
            # encima de la zona más de 2 s, se pide bajarla
            if self._vigia_baja.paso(t, float(p.img[8, 1]), float(zona.get("y0", 0.25))):
                self.avisos.put(Aviso("baje_mano"))
        if (com.get("aviso_brazo_alto", True) and not mano_baja and p is not None and activo
                and not self._aviso_brazo):
            if float(p.img[0, 1]) < 0.30:
                if self._t_brazo is None:
                    self._t_brazo = t
                elif t - self._t_brazo > 60:
                    self._aviso_brazo = True
                    self.avisos.put(Aviso("brazo_alto"))
            else:
                self._t_brazo = None
        dmin = com.get("descanso_min", 20) or 0
        if dmin and activo and p is not None:
            self._t_activo_acum += min(0.2, max(0.0, self.stats.t_cuadros[-1] - self.stats.t_cuadros[-2])
                                       if len(self.stats.t_cuadros) > 1 else 0.0)
            if self._t_activo_acum - self._t_ult_descanso >= dmin * 60:
                self._t_ult_descanso = self._t_activo_acum
                self.avisos.put(Aviso("descanso", str(dmin)))

    def _causa_lentitud(self) -> str:
        """'camara_lenta' si MediaPipe va rápido (la cámara es la que entrega poco: compartida
        con otro programa o poca luz); 'lento' si es el equipo el que no alcanza."""
        ms = float(getattr(self.detector, "ms_ultimo", 0.0) or 0.0)
        if 0.0 < ms < 40.0:
            return "camara_lenta"
        return "lento"

    # ------------------------------------------------------------- dibujo
    def fps_vigente(self, ahora: float | None = None) -> float:
        """Cuadros/s para mostrar: 0 si hace más de 1 s que no llega un cuadro (cámara perdida).
        Sin esto el letrero seguía en «22 cuadros/s» con la imagen congelada."""
        ts = self.stats.t_cuadros
        if not ts:
            return 0.0
        ahora = time.perf_counter() if ahora is None else ahora
        if ahora - ts[-1] > SIN_CUADROS_S:
            return 0.0
        return self.stats.fps

    def _publicar(self, res, cuadro):
        seg = self.nucleo.seguidor
        p = seg.principal
        v = Vista(estado=res.estado, modo=self.nucleo.modo, perfil=self.perfil_actual.nombre,
                  etiqueta=res.etiqueta, progreso=res.progreso, sub=res.sub,
                  fps=self.fps_vigente(), latencia_ms=(self.stats.latencias[-1] if self.stats.latencias else 0.0),
                  medidas=p.medidas.como_dict() if p is not None else {},
                  sena=p.sena.value if p is not None else "", manos=len(seg.pistas),
                  camara=getattr(self.camara, "estado", ""), cerca_borde=res.cerca_borde,
                  ultima_accion=self.ultima_accion, simulada=getattr(self.salida, "simulada", False))
        if p is not None:
            v.punta = (float(p.img[8, 0]), float(p.img[8, 1]))
            v.ancho_mano = float(np.hypot(*(p.img[0, :2] - p.img[17, :2])))
            v.muneca = (float(p.img[0, 0]), float(p.img[0, 1]))
            v.alto_mano = float(p.img[0, 1] - p.img[:, 1].min())
        try:
            v.cursor = self.salida.posicion_cursor()
        except Exception:  # noqa: BLE001
            v.cursor = None
        v.cuentas = dict(getattr(self.nucleo.maquina, "cuenta", {}) or {})
        v.gesto = getattr(self.nucleo.maquina, "gesto", None)
        v.eventos_ensayo = getattr(self.salida, "n_eventos", None)
        if v.eventos_ensayo is None:
            v.eventos_ensayo = len(getattr(self.salida, "eventos", ()))
        if cuadro is not None:
            try:
                peq = cuadro.imagen[::8, ::8]
                v.brillo = float(peq.mean()) if peq.size else float("nan")
            except Exception:  # noqa: BLE001
                pass
            try:
                v.imagen = self._dibujar(cuadro.imagen, res)
            except Exception:  # noqa: BLE001
                log.exception("Error al dibujar la vista previa")
        try:
            self.vistas.get_nowait()
        except queue.Empty:
            pass
        try:
            self.vistas.put_nowait(v)
        except queue.Full:
            pass

    def _dibujar(self, img, res):
        import cv2
        peq = cv2.resize(img, (320, 240), interpolation=cv2.INTER_AREA)
        W, H = 320, 240
        x0, y0, x1, y1 = self.mapeo.zona
        color_zona = (28, 159, 255) if res.cerca_borde else (255, 255, 255)
        cv2.rectangle(peq, (int(x0 * W), int(y0 * H)), (int(x1 * W), int(y1 * H)), color_zona, 1)
        seg = self.nucleo.seguidor
        col_estado = _color_bgr(K.COLORES_ESTADO.get(res.estado, "#8A8F98"))
        for pista in seg.pistas:
            pts = [(int(x * W), int(y * H)) for x, y in pista.img[:, :2]]
            col = col_estado if pista.id == seg.id_principal else (180, 180, 180)
            for a, b in K.CONEXIONES:
                cv2.line(peq, pts[a], pts[b], col, 1, cv2.LINE_AA)
            if pista.id == seg.id_principal:
                pellizco = pista.sena.value == "PELLIZCO"
                cv2.line(peq, pts[4], pts[8], (74, 163, 31) if pellizco else (200, 200, 200), 2, cv2.LINE_AA)
                cv2.circle(peq, pts[8], 4, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(peq, pts[8], 4, col_estado, 1, cv2.LINE_AA)
                if 0.0 < res.progreso < 1.0:
                    cv2.ellipse(peq, pts[8], (14, 14), -90, 0, int(360 * res.progreso), (255, 255, 255), 2,
                                cv2.LINE_AA)
        # (los cuadros por segundo los muestra solo la interfaz, con su unidad)
        return cv2.cvtColor(peq, cv2.COLOR_BGR2RGB)
