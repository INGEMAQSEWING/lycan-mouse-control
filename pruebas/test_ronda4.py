"""Ronda 4 de arreglos: temblor con la mano quieta (bloqueo de quieto), puntero fuera de la zona
(barra de tareas y menús), giro 3D que se trababa al perder una mano un cuadro, entero gigante
en config.json, número de cámara escrito a mano y «Volver a practicar señas» sin guardar."""
import json
import math

import numpy as np
import pytest

from conftest import Sim, M
from lycan_mouse_control import constantes as K
from lycan_mouse_control.acciones import Clic, MoverDelta
from lycan_mouse_control.config import FABRICA, Configuracion, validar
from lycan_mouse_control.mapeo import Mapeo, Monitor
from lycan_mouse_control.puntero import Puntero
from test_estados import DOS_PUNOS, manos_volante, soltar_al_final
from test_interfaz import bombear, root  # noqa: F401 (fixture)
from test_ronda1_interfaz import AppModo

P0 = (0.5, 0.5)
MON = Monitor(0, 0, 1366, 768)


# ======================================================== 1. temblor con la mano quieta
def _quieto_con_ruido(fps, sigma_px, semilla, cfg=None, segundos=10.0, asentar=1.0):
    """Mano quieta en el centro con ruido gaussiano de sigma_px píxeles DE PANTALLA. Devuelve
    (movimientos, rango en px) de lo enviado durante `segundos` después de `asentar` s."""
    mp = Mapeo(monitor=MON)
    rng = np.random.default_rng(semilla)
    p = Puntero(mp, cfg or {})
    t, pos, xs, movs = 0.0, None, [], 0
    for _ in range(int((asentar + segundos) * fps)):
        t += 1.0 / fps
        p.observar(t, 0.5 + rng.normal(0, sigma_px / mp.px_por_unidad_x),
                   0.5 + rng.normal(0, sigma_px / mp.px_por_unidad_y))
        m = p.mover(t)
        if m is not None:
            pos = (m.x, m.y)
            movs += t > asentar
        if t > asentar:
            xs.append(pos)
    a = np.array(xs)
    return movs, int(max(np.ptp(a, axis=0)))


@pytest.mark.parametrize("fps", [30, 15])
@pytest.mark.parametrize("semilla", range(6))
def test_mano_quieta_con_ruido_de_2px_no_mueve_mas_de_2px_en_10s(fps, semilla):
    movs, rango = _quieto_con_ruido(fps, 2.0, semilla)
    assert rango <= 2, (movs, rango)
    assert movs <= 2, (movs, rango)


@pytest.mark.parametrize("semilla", range(4))
def test_mano_quieta_con_ruido_de_3px_a_30fps_casi_no_se_mueve(semilla):
    movs, rango = _quieto_con_ruido(30, 3.0, semilla)
    assert rango <= 3, (movs, rango)
    assert movs <= 3, (movs, rango)


def _arranque(fps, vel_px_s):
    """Quieto 1.5 s, luego se mueve a vel_px_s durante 0.5 s y para. Devuelve (retraso del
    primer movimiento en s, error final en px)."""
    mp = Mapeo(monitor=MON)
    p = Puntero(mp, {})
    t, x0, pos, lat = 0.0, 683.0, None, None
    for _ in range(int(4 * fps)):
        t += 1.0 / fps
        x = x0 if t < 1.5 else x0 + vel_px_s * min(t - 1.5, 0.5)
        p.observar(t, 0.2 + x / mp.px_por_unidad_x, 0.5)
        m = p.mover(t)
        if m is not None:
            if pos is not None and t >= 1.5 and lat is None and abs(m.x - pos[0]) >= 1:
                lat = t - 1.5
            pos = (m.x, m.y)
    return lat, pos[0] - (x0 + vel_px_s * 0.5)


@pytest.mark.parametrize("fps", [30, 15])
def test_bloqueo_de_quieto_no_vuelve_lenta_la_respuesta_al_empezar_a_mover(fps):
    lat, err = _arranque(fps, 300)
    assert lat is not None and lat <= 0.12, lat          # sigue rápido al empezar
    assert abs(err) <= 2.0, err                           # y llega a donde paró la mano
    lat, err = _arranque(fps, 100)
    assert lat is not None and lat <= 0.25, lat
    assert abs(err) <= 2.0, err


def test_zona_muerta_crece_con_la_ampliacion():
    normal = Puntero(Mapeo(monitor=MON))
    chica = Puntero(Mapeo((0.40, 0.40, 0.60, 0.60), MON))     # zona chica: mucha ampliación
    # de fábrica 1 px de la cámara son 1365/0.6/640 = 3.55 px de pantalla: zona muerta 0.6 de eso
    assert normal.zona_muerta_efectiva() == pytest.approx(0.6 * 1365 / 0.6 / 640, rel=0.01)
    assert normal.zona_muerta_efectiva() >= 1.5
    assert chica.zona_muerta_efectiva() > 2 * normal.zona_muerta_efectiva()
    assert chica.umbral_bloqueo() > normal.umbral_bloqueo()


def test_reset_quita_el_bloqueo_de_quieto():
    p = Puntero(Mapeo(monitor=MON))
    t = 0.0
    for _ in range(30):
        t += 1 / 30
        p.observar(t, 0.5, 0.5)
        p.mover(t)
    assert p.bloqueado
    p.reset()
    assert not p.bloqueado


# ======================================================== 2. fuera de la zona (barra de tareas)
def test_fuera_de_la_zona_el_puntero_recorre_la_barra_de_tareas_sin_saltar_al_volver():
    s = Sim()
    s.activar(P0)
    s.durante(300, lambda f: M("apuntar", (0.5, 0.5 + 0.25 * f)))     # v hasta 0.75 (la zona acaba en 0.70)
    assert s.salida.cursor[1] >= 760
    s.durante(1500, lambda f: M("apuntar", (0.5 - 0.25 * f, 0.75)))   # por la barra, fuera de la zona
    x, y = s.salida.cursor
    assert x <= 150, s.salida.cursor                    # siguió a la mano (antes se quedaba en ~525)
    assert y >= 760                                     # recortado al borde de abajo
    n0 = len(s.salida.eventos)
    s.durante(100, M("apuntar", (0.25, 0.69)))
    movs = [ev for _, ev in s.salida.eventos[n0:] if ev[0] == "mover"]
    prev = (x, y)
    for ev in movs:
        assert math.hypot(ev[1] - prev[0], ev[2] - prev[1]) <= 40, movs
        prev = (ev[1], ev[2])
    soltar_al_final(s)


def test_fuera_de_la_zona_por_arriba_y_por_los_lados_sigue_a_la_mano():
    s = Sim()
    s.activar(P0)
    s.durante(300, lambda f: M("apuntar", (0.5, 0.5 - 0.30 * f)))     # v = 0.20 (la zona empieza en 0.25)
    s.durante(1200, lambda f: M("apuntar", (0.5 + 0.2 * f, 0.20)))    # por la fila de menús
    x, y = s.salida.cursor
    assert y <= 5 and x >= 1050, s.salida.cursor        # siguió a la mano (u = 0.7 -> x ~ 1137)
    s.durante(1200, lambda f: M("apuntar", (0.85, 0.20 + 0.3 * f)))   # por fuera del lado derecho
    x, y = s.salida.cursor
    assert x >= 1360 and y >= 300, s.salida.cursor
    soltar_al_final(s)


def test_pegado_al_borde_de_la_imagen_se_detiene_y_al_volver_llega_en_varios_cuadros():
    mp = Mapeo(monitor=MON)
    p = Puntero(mp)
    t = 0.0
    for _ in range(20):
        t += 1 / 30
        p.observar(t, 0.5, 0.5)
        p.mover(t)
    # la punta se pega al borde de la imagen (abajo): MediaPipe ya no es confiable
    for k in range(40):
        t += 1 / 30
        p.observar(t, 0.5 - 0.005 * k, 0.99)
        p.mover(t)
    assert p.fuera_mucho(t)
    quieto_x = p.ult_enviado[0]
    for _ in range(5):
        t += 1 / 30
        p.observar(t, 0.25, 0.99)
        assert p.mover(t) is None
    assert p.ult_enviado[0] == quieto_x
    # vuelve a la zona lejos de donde quedó el puntero: llega en 3-4 cuadros, no de un salto
    pasos = []
    for _ in range(8):
        t += 1 / 30
        p.observar(t, 0.25, 0.6)
        m = p.mover(t)
        if m is not None:
            pasos.append((m.x, m.y))
    assert len(pasos) >= 3, pasos
    x0, y0 = quieto_x, p.mapeo.monitor.alto - 1
    saltos = []
    for x, y in pasos:
        saltos.append(math.hypot(x - x0, y - y0))
        x0, y0 = x, y
    destino = p.pos
    assert max(saltos) < 0.5 * sum(saltos), saltos
    assert math.hypot(pasos[-1][0] - destino[0], pasos[-1][1] - destino[1]) <= 3


# ======================================================== 3. giro 3D con cuadros perdidos
def _giro_con_perdidas(cada, mover_centro=False):
    s = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    s.activar(P0)
    s.durante(300, manos_volante(0))
    t0 = s.t
    n = 30
    for k in range(n + 15):
        f = min(k, n) / n
        if mover_centro:
            m = manos_volante(0, centro=(0.5, 0.52 + 0.08 * f))
        else:
            m = manos_volante(30 * f)
        if cada and k % cada == cada - 1 and k < n:
            m = [m[1]]                     # MediaPipe pierde una mano UN cuadro
        s.cuadro(m)
    d = [a for a in s.desde(t0) if isinstance(a, MoverDelta)]
    return s, sum(a.dx for a in d), sum(a.dy for a in d), d


@pytest.mark.parametrize("cada", [0, 6, 4, 3])
def test_E17d_girar_perdiendo_una_mano_un_cuadro_de_cada_n(cada):
    s, dx, dy, d = _giro_con_perdidas(cada)
    assert s.estado == K.GIRANDO_3D
    assert dx == pytest.approx(30 / 180 * 768, rel=0.25), dx
    assert abs(dy) < 20
    assert max(math.hypot(a.dx, a.dy) for a in d) <= 30
    assert not any(isinstance(a, Clic) for _, a in s.acciones)
    soltar_al_final(s)


@pytest.mark.parametrize("cada", [0, 4, 3])
def test_E17e_subir_las_manos_perdiendo_una_mano_un_cuadro_de_cada_n(cada):
    s, dx, dy, _d = _giro_con_perdidas(cada, mover_centro=True)
    sin_perdidas = _giro_con_perdidas(0, mover_centro=True)[2]
    assert dy > 25
    assert dy == pytest.approx(sin_perdidas, rel=0.25), (dy, sin_perdidas)
    soltar_al_final(s)


def test_E17f_salto_del_centro_descartado_no_se_cuela_despues_como_movimiento():
    s = Sim(modo="3D", perfil="sketchup", cfg=DOS_PUNOS)
    s.activar(P0)
    s.durante(300, manos_volante(0))
    t0 = s.t
    s.durante(300, manos_volante(0))
    # MediaPipe "salta": el centro aparece 0.2 más abajo y se queda ahí (salto imposible)
    s.durante(700, manos_volante(0, centro=(0.5, 0.72)))
    d = [a for a in s.desde(t0) if isinstance(a, MoverDelta)]
    assert abs(sum(a.dy for a in d)) < 15, d
    assert s.estado == K.GIRANDO_3D
    soltar_al_final(s)


# ======================================================== 4. entero gigante en config.json
GIGANTE = int("1" + "0" * 400)


def test_entero_gigante_en_config_no_impide_abrir(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text('{"primera_vez": false, "zoom": {"paso_log": 1' + "0" * 400 + "}}", encoding="utf-8")
    c = Configuracion(ruta)
    datos = c.cargar()                                    # antes: OverflowError
    assert datos["zoom"]["paso_log"] == FABRICA["zoom"]["paso_log"]
    assert datos["primera_vez"] is False
    assert any("zoom.paso_log" in p for p in c.problemas)


@pytest.mark.parametrize("cambio", [
    {"zona": {"x0": GIGANTE}},
    {"puntero": {"zona_muerta_px": -GIGANTE}},
    {"camara": {"indice": GIGANTE}},
    {"calibracion": {"luz": GIGANTE}},
    {"ventana": {"x": GIGANTE}},
])
def test_validar_con_enteros_gigantes_usa_los_de_fabrica(cambio):
    problemas = []
    out = validar(cambio, problemas=problemas)
    seccion, valores = next(iter(cambio.items()))
    clave = next(iter(valores))
    assert out[seccion][clave] == FABRICA[seccion][clave]
    json.dumps(out)


def test_listas_con_enteros_gigantes_vuelven_a_fabrica():
    listas = [(k, v) for k, v in FABRICA.items() if isinstance(v, dict)
              for kk, vv in v.items() if isinstance(vv, list)]
    for seccion, sub in listas:
        for clave, fab in sub.items():
            if isinstance(fab, list) and fab:
                out = validar({seccion: {clave: [GIGANTE] * len(fab)}})
                assert out[seccion][clave] == fab


def test_cualquier_error_raro_al_validar_restablece_y_no_tumba_el_arranque(tmp_path, monkeypatch):
    from lycan_mouse_control import config as C
    ruta = tmp_path / "config.json"
    ruta.write_text('{"primera_vez": false}', encoding="utf-8")

    def revienta(*a, **k):
        raise OverflowError("int too large to convert to float")
    monkeypatch.setattr(C, "validar", revienta)
    c = Configuracion(ruta)
    datos = c.cargar()
    assert c.aviso == "Se restableció la configuración."
    assert datos["zoom"]["paso_log"] == FABRICA["zoom"]["paso_log"]
    assert list(tmp_path.glob("config.dañado-*.json"))


# ======================================================== 5. cámara escrita a mano en Opciones
@pytest.mark.parametrize("escrito, esperado", [("2", 2), (" 1 ", 1), ("7", 3), ("-4", 0)])
def test_numero_de_camara_escrito_a_mano_se_guarda(root, tmp_path, escrito, esperado):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    op._vc.set(escrito)                       # sin usar las flechitas
    op.guardar()
    assert app.cfg.datos["camara"]["indice"] == esperado
    disco = Configuracion(app.cfg.ruta)
    disco.cargar()
    assert disco.datos["camara"]["indice"] == esperado


def test_numero_de_camara_que_no_es_numero_avisa_y_no_guarda(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    from lycan_mouse_control.ui.textos import t
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    op._vc.set("dos")
    op.guardar()
    assert op.win.winfo_exists()              # no se cerró: no se guardó
    assert op.lbl_camara.cget("text") == t("op_camara_invalida")
    bombear(root, 50)
    op.win.update_idletasks()
    assert op.lbl_camara.winfo_width() + 2 >= op.lbl_camara.winfo_reqwidth()   # el aviso se lee entero
    assert app.cfg.datos["camara"]["indice"] == 0
    op._vc.set("1")
    op.guardar()
    assert app.cfg.datos["camara"]["indice"] == 1


def test_numero_de_camara_se_aplica_al_salir_de_la_casilla(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppModo(tmp_path, "2D")
    op = VentanaOpciones(root, app)
    op._vc.set("2")
    assert op._leer_camara()
    assert op.cfg["camara"]["indice"] == 2
    op.cancelar()
    assert app.cfg.datos["camara"]["indice"] == 0


# ======================================================== 6. practicar sin guardar
class AppPractica(AppModo):
    def __init__(self, tmp_path):
        super().__init__(tmp_path, "2D")
        self.asistentes = 0

    def abrir_asistente(self):
        self.asistentes += 1


def test_practicar_senas_revierte_los_cambios_sin_guardar(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppPractica(tmp_path)
    assert FABRICA["comodidad"]["opacidad"] != 0.55
    op = VentanaOpciones(root, app)
    # un cambio en vivo sin guardar (como mover un deslizador)
    op._set(["comodidad", "opacidad"], 0.55)
    bombear(root, 500)                         # el cambio en vivo llega al motor
    assert app.ordenes[-1][0] == "config" and app.ordenes[-1][1]["comodidad"]["opacidad"] == 0.55
    op.practicar()
    assert app.asistentes == 1
    assert not op.win.winfo_exists()
    assert app.ordenes[-1][0] == "config"
    assert app.ordenes[-1][1]["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]
    assert app.cfg.datos["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]
    n = len(app.ordenes)
    bombear(root, 600)                         # no queda un cambio en vivo pendiente
    assert len(app.ordenes) == n


def test_practicar_con_un_cambio_en_vivo_aun_pendiente_no_lo_deja_en_uso(root, tmp_path):  # noqa: F811
    from lycan_mouse_control.ui.opciones import VentanaOpciones
    app = AppPractica(tmp_path)
    op = VentanaOpciones(root, app)
    op._set(["comodidad", "opacidad"], 0.55)   # el envío al motor aún espera sus 400 ms
    op.practicar()
    bombear(root, 600)
    assert not [o for o in app.ordenes if o[0] == "config" and o[1]["comodidad"]["opacidad"] == 0.55]
    assert app.ordenes[-1][1]["comodidad"]["opacidad"] == FABRICA["comodidad"]["opacidad"]
    assert app.asistentes == 1
