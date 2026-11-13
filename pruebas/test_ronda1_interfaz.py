"""Ronda 1 de arreglos: interfaz (asistente, Opciones, ayuda, ventana principal) y empaquetado."""
import re
import tkinter as tk
from pathlib import Path

import numpy as np
import pytest

from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Aviso
from lycan_mouse_control.motor import Vista
from test_interfaz import AppFalsa, bombear


@pytest.fixture
def root():
    """Como el de test_interfaz, pero reintenta: Tcl a veces falla al crear la raíz justo
    después de destruir otra en el mismo proceso, y la prueba se saltaba sin avisar."""
    import time
    ultimo = None
    for _ in range(5):
        try:
            r = tk.Tk()
            break
        except tk.TclError as e:
            ultimo = e
            time.sleep(0.2)
    else:
        pytest.skip(f"sin pantalla ({ultimo})")
    r.withdraw()
    yield r
    try:
        r.destroy()
    except tk.TclError:
        pass

RAIZ = Path(__file__).resolve().parents[1]


class AppModo(AppFalsa):
    """AppFalsa con el modo vigente del motor separado del de la configuración."""

    def __init__(self, tmp_path, modo_motor="3D"):
        super().__init__(tmp_path)
        self.modo_motor = modo_motor
        self.avisos_mostrados = []
        self._asistente = None
        self.root = None

    def modo_vigente(self):
        return self.modo_motor

    def al_cambiar_modo(self, modo):
        self.cfg.datos["modo"] = modo

    def mostrar_aviso(self, t, segundos=5):
        self.avisos_mostrados.append(t)

    def guardar_config(self, datos=None):
        return self.cfg.guardar_seguro(datos)


# ======================================================== 16. botones del asistente visibles
def test_botones_del_asistente_no_quedan_cortados(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    app = AppModo(tmp_path, "2D")
    app.root = root
    a = Asistente(root, app)
    try:
        for _ in range(len(a.pasos)):
            bombear(root, 60)
            a.win.update_idletasks()
            alto = a.win.winfo_height()
            for b in (a.b_sig, a.b_atras):
                assert b.winfo_ismapped()
                abajo = b.winfo_rooty() - a.win.winfo_rooty() + b.winfo_height()
                assert b.winfo_height() >= 20, "botón aplastado"
                assert abajo <= alto, "botón cortado por el borde de la ventana"
            a.siguiente() if a.i < len(a.pasos) - 1 else None
    finally:
        a.cerrar()


# ======================================================== 17. un solo modo
def test_aviso_de_modo_actualiza_la_configuracion(root, tmp_path):
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    app = AppModo(tmp_path, "2D")
    v = VentanaPrincipal(root, app)
    assert app.cfg.datos["modo"] == "2D"
    app.motor.avisos.put(Aviso("modo", "3D"))
    bombear(root, 200)
    assert app.cfg.datos["modo"] == "3D"
    app.cerrando = True
    _ = v


def test_opciones_guardar_y_cancelar_respetan_el_modo_vigente(root, tmp_path):
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "3D")
    assert app.cfg.datos["modo"] == "2D"               # la configuración aún no se enteró
    op = VentanaOpciones(root, app)
    bombear(root, 100)
    op.guardar()
    assert app.ordenes[-1][0] == "config" and app.ordenes[-1][1]["modo"] == "3D"
    op = VentanaOpciones(root, app)
    app.modo_motor = "2D"                               # Ctrl+Alt+D con Opciones abierta
    op.cancelar()
    assert app.ordenes[-1][1]["modo"] == "2D"
    # si el usuario SÍ elige el modo en Opciones, se respeta
    op = VentanaOpciones(root, app)
    op._poner_modo("3D")
    op.guardar()
    assert app.ordenes[-1][1]["modo"] == "3D"


def test_asistente_usa_el_modo_vigente(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    app = AppModo(tmp_path, "3D")
    a = Asistente(root, app)
    claves = [p.clave for p in a.pasos]
    assert "girar" in claves and "desplazar" in claves and "soltar" in claves
    a.cerrar()


# ======================================================== 18. un solo asistente
def test_no_se_abren_dos_asistentes(root, tmp_path):
    from lycan_mouse_control.app import App

    class AppA(AppModo):
        abrir_asistente = App.abrir_asistente
        asistente_cerrado = App.asistente_cerrado
    app = AppA(tmp_path, "2D")
    app.root = root
    a1 = app.abrir_asistente()
    a2 = app.abrir_asistente()
    assert a1 is a2
    assert [o for o in app.ordenes if o[:2] == ("ensayo", True)].__len__() == 1
    a1.cerrar()
    assert app._asistente is None
    a3 = app.abrir_asistente()
    assert a3 is not a1
    a3.cerrar()


# ======================================================== 9. avisar si no se pudo guardar
def test_asistente_avisa_si_no_pudo_guardar(root, tmp_path):
    from lycan_mouse_control.ui.asistente import Asistente
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    app.guardar_config = lambda datos=None: False
    a = Asistente(root, app)
    a.terminar()
    assert t("as_listo") not in app.avisos_mostrados
    assert app.cfg.datos["primera_vez"] is False


def test_app_guardar_config_muestra_aviso_si_falla(tmp_path):
    from lycan_mouse_control.app import App
    from lycan_mouse_control.ui.textos import t
    avisos = []
    falsa = type("F", (), {})()
    falsa.cfg = type("C", (), {"guardar_seguro": lambda self, d=None: False})()
    falsa.mostrar_aviso = lambda txt, s=5: avisos.append(txt)
    assert App.guardar_config(falsa) is False
    assert avisos == [t("aviso_no_guardo")]


# ======================================================== 19. barra de estado
@pytest.mark.parametrize("perfil", ["EDWIN CNC CAD-CAM", "FreeCAD (estilo Blender)", "Genérico"])
@pytest.mark.parametrize("estado", [K.SIN_MANO, K.DESPLAZANDO, K.ARRASTRANDO, K.PAUSA])
@pytest.mark.parametrize("simulada", [False, True])
def test_barra_de_estado_no_corta_el_perfil_por_delante(root, tmp_path, perfil, estado, simulada):
    from lycan_mouse_control.ui.ventana_principal import ANCHO, VentanaPrincipal
    app = AppModo(tmp_path, "2D")
    v = VentanaPrincipal(root, app)
    root.deiconify()
    app.motor.vistas.put(Vista(estado=estado, perfil=perfil, simulada=simulada, modo="3D",
                               imagen=np.zeros((240, 320, 3), np.uint8)))
    bombear(root, 150)
    root.update_idletasks()
    txt = v.lbl_perfil.cget("text")
    assert txt == perfil or (txt.endswith("…") and perfil.startswith(txt[:-1].rstrip()))
    usado = v.lbl_estado.winfo_reqwidth() + v.lbl_modo.winfo_reqwidth() + v.lbl_perfil.winfo_reqwidth()
    # márgenes de empaque: (6+4) estado, (2+2) chip, (6+6) perfil; la barra mide ANCHO - 6
    assert usado + 10 + 4 + 12 <= ANCHO - 6, "la barra no alcanza: algo queda tapado"
    assert "ensayo" not in v.lbl_estado.cget("text")
    if simulada:
        assert "ensayo" in v.lbl_modo.cget("text")
    app.cerrando = True


def test_recortar_con_puntos_suspensivos():
    from lycan_mouse_control.ui.ventana_principal import recortar
    medir = lambda s: 7 * len(s)                      # noqa: E731
    assert recortar("EDWIN CNC CAD-CAM", 500, medir) == "EDWIN CNC CAD-CAM"
    corto = recortar("EDWIN CNC CAD-CAM", 70, medir)
    assert corto.endswith("…") and corto.startswith("EDWIN")
    assert medir(corto) <= 70


# ======================================================== 24. diagnóstico sin tapar los botones
def test_diagnostico_sube_la_ventana(root, tmp_path):
    from lycan_mouse_control.ui.ventana_principal import ALTO, VentanaPrincipal, area_de_trabajo
    app = AppModo(tmp_path, "2D")
    v = VentanaPrincipal(root, app)
    root.deiconify()
    _l, _t, _r, abajo = area_de_trabajo(root)
    root.geometry(f"+{root.winfo_x()}+{abajo - ALTO - 16}")
    bombear(root, 100)
    v._alternar_diag()
    bombear(root, 150)
    assert root.winfo_y() + ALTO + 70 <= abajo
    v._alternar_diag()
    app.cerrando = True


# ======================================================== 25. cuadros por segundo una sola vez
def test_video_no_lleva_numero_suelto_y_la_etiqueta_tiene_unidad(root, tmp_path):
    from lycan_mouse_control.config import por_defecto
    from lycan_mouse_control.motor import Motor
    from lycan_mouse_control.nucleo import Nucleo
    from lycan_mouse_control.mapeo import Mapeo
    from lycan_mouse_control.salida.simulada import SalidaSimulada
    from lycan_mouse_control.ui.ventana_principal import VentanaPrincipal
    m = Motor(por_defecto(), SalidaSimulada(), sistema=False)
    m.mapeo = Mapeo()
    m.nucleo = Nucleo(por_defecto())
    for k in range(30):
        m.stats.cuadro(k / 30)
    res = m.nucleo.procesar(0.0, [])
    img = m._dibujar(np.zeros((480, 640, 3), np.uint8), res)
    assert int(img[0:16, 280:320].max()) == 0, "hay un número sin unidad arriba a la derecha"
    app = AppModo(tmp_path, "2D")
    v = VentanaPrincipal(root, app)
    app.motor.vistas.put(Vista(estado=K.ACTIVO, fps=21.0, imagen=np.zeros((240, 320, 3), np.uint8)))
    bombear(root, 150)
    assert v.lbl_fps.cget("text") == "21 cuadros/s"
    app.cerrando = True


# ======================================================== 20. etiquetas de Opciones completas
def test_opciones_sin_etiquetas_cortadas(root, tmp_path):
    from tkinter import ttk
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    nb = next(w for w in op.win.winfo_children() if isinstance(w, ttk.Notebook))
    cortadas = []

    def revisar(w):
        for h in w.winfo_children():
            if isinstance(h, tk.Label) and h.cget("text") and h.winfo_ismapped():
                if h.winfo_width() + 2 < h.winfo_reqwidth():
                    cortadas.append(h.cget("text"))
            if isinstance(h, ttk.Combobox) and h.winfo_ismapped():
                import tkinter.font as tkfont
                f = tkfont.nametofont("TkTextFont")
                if f.measure(h.get()) > h.winfo_width() - 20:
                    cortadas.append(h.get())
            revisar(h)
    for i in range(len(nb.tabs())):
        nb.select(i)
        bombear(root, 80)
        op.win.update_idletasks()
        revisar(nb.nametowidget(nb.tabs()[i]))
    assert not cortadas, cortadas
    textos = []

    def combos(w):
        for h in w.winfo_children():
            if isinstance(h, ttk.Combobox):
                textos.extend(h.cget("values"))
            combos(h)
    combos(op.win)
    assert t("op_monitor_principal") in textos
    assert not any(str(x).startswith(t("op_monitor")) for x in textos)
    op.cancelar()


# ======================================================== 21 y 22. ayuda
def test_ayuda_no_deja_la_rueda_enganchada(root):
    from lycan_mouse_control.ui.ayuda import VentanaAyuda
    a = VentanaAyuda(root, "3D", False)
    assert root.bind_all("<MouseWheel>") == ""
    a.win.destroy()
    root.deiconify()
    bombear(root, 50)
    root.event_generate("<MouseWheel>", delta=-120, when="now")   # antes: TclError
    bombear(root, 50)


def test_ayuda_3d_dice_modelo_y_lista_todos_los_atajos(root):
    from lycan_mouse_control.ui.ayuda import VentanaAyuda, texto_atajos
    a = VentanaAyuda(root, "3D", False, atajos={"pausar": "Ctrl+Alt+K"})
    textos = []

    def recorrer(w):
        for h in w.winfo_children():
            if isinstance(h, tk.Label):
                textos.append(h.cget("text"))
            recorrer(h)
    recorrer(a.win)
    todo = "\n".join(textos)
    assert "Mover el modelo" in todo and "Mover el dibujo" not in todo
    assert "Ctrl+Alt+K" in todo and "Ctrl+Alt+D" in todo and "Ctrl+Alt+P" in todo
    a.win.destroy()
    linea = texto_atajos(None)
    for atajo in ("Ctrl+Alt+M", "Ctrl+Alt+X", "Ctrl+Alt+O", "Ctrl+Alt+D", "Ctrl+Alt+P"):
        assert atajo in linea


def test_textos_de_mover_en_3d():
    from lycan_mouse_control.ui.textos import t
    assert "modelo" in t("sena_desplazar_3D").lower()
    assert "modelo" in t("ayuda_DESPLAZANDO_3D").lower()
    assert "modelo" in t("as_desplazar_3D").lower()


# ======================================================== 23. abrir al encender solo al guardar
def test_abrir_al_encender_solo_se_escribe_al_guardar(root, tmp_path, monkeypatch):
    from lycan_mouse_control.sistema import inicio
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    llamadas = []
    monkeypatch.setattr(inicio, "activo", lambda: False)
    monkeypatch.setattr(inicio, "poner", lambda si: llamadas.append(si))
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    op._inicio_pedido = True                  # marcó la casilla
    assert llamadas == []
    op.cancelar()
    assert llamadas == []
    op = VentanaOpciones(root, app)
    op._inicio_pedido = True
    op.guardar()
    assert llamadas == [True]
    # en modo ensayo (--simular) nunca se toca el registro de Windows
    app.args = type("A", (), {"simular": True})()
    op = VentanaOpciones(root, app)
    op._inicio_pedido = True
    op.guardar()
    assert llamadas == [True]


# ======================================================== 27-30. empaquetado
def _leer(rel):
    return (RAIZ / rel).read_text(encoding="utf-8-sig")


def test_desinstalar_borra_siempre_el_arranque_con_windows():
    iss = _leer("empaquetado/lycan-mouse-control.iss")
    codigo = iss[iss.index("[Code]"):]
    bloque = codigo[codigo.index("usUninstall then"):]
    assert "RegDeleteValue(HKEY_CURRENT_USER" in bloque
    assert "'LycanMouseControl'" in bloque


def test_iss_compila_sin_version_y_versioninfo_es_numerica():
    iss = _leer("empaquetado/lycan-mouse-control.iss")
    m = re.search(r'#define MyAppVersion "([^"]+)"', iss)
    assert m and re.fullmatch(r"\d+(\.\d+){0,3}", m.group(1)), "la versión por defecto no es numérica"
    assert "VersionInfoVersion={#MyAppVersionNum}" in iss
    assert "#define MyAppVersionNum MyAppVersion" in iss
    assert ".github\\workflows\\windows.yml" in iss
    assert "lycan-mouse-windows.yml" not in iss


def test_workflow_instalador_antes_que_el_zip_y_leeme_aparte():
    for rel in (".github/workflows/windows.yml", "empaquetado/lycan-mouse-windows.yml"):
        wf = _leer(rel)
        assert wf.index("- name: Instalador") < wf.index("- name: ZIP portable")
        assert "dist/LycanMouseControl/LEEME.txt" not in wf
        assert "dist/portable/LycanMouseControl/LEEME.txt" in wf
        assert "/DMyAppVersionNum=" in wf
    assert _leer(".github/workflows/windows.yml") == _leer("empaquetado/lycan-mouse-windows.yml")


def test_tamano_del_paquete_actualizado():
    assert "~199 MB" not in _leer("empaquetado/lycan-mouse-control.spec")
    assert "199 MB" not in _leer("docs/especificacion.md")
    assert "211 MB" in _leer("empaquetado/lycan-mouse-control.spec")
