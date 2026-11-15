"""Secuencias aleatorias ("uso real" desordenado): posturas, manos que entran y salen, cambios de
velocidad de la cámara, atajos y cambios de programa. Nada puede quedar presionado y nunca puede
haber un "bajar" repetido, rueda con Shift/Ctrl, ni Shift soltado antes que el botón del medio."""
import numpy as np
import pytest

from conftest import Sim
from lycan_mouse_control import constantes as K
from lycan_mouse_control import perfiles
from lycan_mouse_control.sintetico import intermedia, mano

POSTURAS = ["abierta", "puno", "apuntar", "pellizco", "juntos", "v", "relajada", "pellizco_corazon",
            # 1.0.2 paquete A
            "pellizco_anular", "pellizco_menique", "pulgar_corazon_anular", "pulgar_sobre_anular_doblado"]


def _manos(rng, estado):
    """Evoluciona un 'estado' de manos de a poco (como en la vida real) y devuelve la lista."""
    out = []
    for i, h in enumerate(estado):
        if h is None:
            continue
        if rng.random() < 0.08:
            h["postura"] = POSTURAS[int(rng.integers(len(POSTURAS)))]
        h["pos"] = np.clip(h["pos"] + rng.normal(0, 0.01, 2), 0.05, 0.95)
        if rng.random() < 0.05:
            P = intermedia("abierta", "puno", float(rng.random()))
        else:
            P = h["postura"]
        out.append(mano(P, posicion=tuple(h["pos"]), lado=h["lado"], ancla="centro",
                        ruido_mm=float(rng.choice([0, 1, 2, 4])), rng=rng,
                        rot=tuple(rng.uniform(-25, 25, 3))))
    return out


@pytest.mark.parametrize("semilla", range(24))
def test_secuencia_aleatoria_nada_queda_presionado(semilla):
    rng = np.random.default_rng(semilla)
    modo = "3D" if semilla % 2 else "2D"
    perfil = list(perfiles.PERFILES)[semilla % len(perfiles.PERFILES)]
    # 1.0.2 paquete B: las tres formas de girar, con y sin inercia, y atajos de golpe en todos los
    # programas (así las secuencias desordenadas también abren y cierran la mano «de golpe»)
    cfg = {"orbita": {"girar": ("un_puno", "dos_punos", "ambos")[semilla % 3], "inercia": semilla % 4 < 2},
           "gestos": {"por_programa": {k: {"abrir_golpe": "Ctrl+Alt+U", "cerrar_golpe": "Ctrl+Alt+J"}
                                       for k in perfiles.PERFILES}}}
    sim = Sim(modo=modo, perfil=perfil, fps=float(rng.choice([15, 20, 30])), cfg=cfg)
    sim.orden(sim.nucleo.alternar_pausa(sim.t))          # arranca activo para ejercitar más
    estado = [{"postura": "apuntar", "pos": np.array([0.65, 0.5]), "lado": "Right"},
              {"postura": "abierta", "pos": np.array([0.35, 0.5]), "lado": "Left"} if rng.random() < 0.5 else None]
    for k in range(int(10 * 30)):
        if rng.random() < 0.01:
            sim.poner_fps(float(rng.choice([12, 15, 24, 30])))
        if rng.random() < 0.02:     # una mano entra o sale
            i = int(rng.integers(2))
            estado[i] = None if estado[i] is not None else {
                "postura": POSTURAS[int(rng.integers(len(POSTURAS)))],
                "pos": rng.uniform(0.2, 0.8, 2), "lado": ("Right", "Left")[i]}
        sim.cuadro(_manos(rng, estado))
        r = rng.random()
        if r < 0.003:
            sim.orden(sim.nucleo.alternar_pausa(sim.t))
        elif r < 0.005:
            sim.orden(sim.nucleo.cambiar_perfil(sim.t, perfiles.PERFILES[list(perfiles.PERFILES)[int(rng.integers(7))]]))
        elif r < 0.006:
            sim.orden(sim.nucleo.cambiar_modo(sim.t, "3D" if sim.nucleo.modo == "2D" else "2D"))
            sim.orden(sim.nucleo.alternar_pausa(sim.t))
        elif r < 0.016:
            # 1.0.2 paquete A: la tecla de clic (bajar, soltar o repetición) y la orden de frenar
            q = rng.random()
            if q < 0.4:
                sim.orden(sim.nucleo.tecla_clic(sim.t, True))
            elif q < 0.8:
                sim.orden(sim.nucleo.tecla_clic(sim.t, False))
            elif q < 0.9:
                sim.nucleo.maquina.tecla_repite(sim.t)
            else:
                sim.orden(sim.nucleo.frenar(sim.t))
        sim.invariantes(final=False)
    sim.durante(300, [])
    assert sim.salida.todo_suelto()
    sim.orden(sim.nucleo.pausar(sim.t))
    sim.invariantes(final=True)
    assert not sim.nucleo.errores, sim.nucleo.ultimo_error


def test_reproducir_grabacion_npz(tmp_path):
    """Las sesiones grabadas con herramientas/grabar.py se pueden pasar por el núcleo."""
    import importlib.util
    import pathlib
    ruta_mod = pathlib.Path(__file__).resolve().parents[1] / "herramientas" / "grabar.py"
    spec = importlib.util.spec_from_file_location("grabar", ruta_mod)
    grabar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grabar)
    n = 60
    img = np.full((n, 2, 21, 3), np.nan)
    mun = np.full((n, 2, 21, 3), np.nan)
    for k in range(n):
        m = mano("pellizco" if 20 <= k < 30 else "apuntar")
        img[k, 0], mun[k, 0] = m.img, m.mundo
    ruta = tmp_path / "x.npz"
    np.savez_compressed(ruta, img=img, mundo=mun, n_manos=np.ones(n, int), etiquetas=np.array([["Right", ""]] * n),
                        t=np.arange(n) / 30, sena_pedida=np.array("pellizco"))
    cuadros, sena = grabar.reproducir(str(ruta))
    assert sena == "pellizco" and len(cuadros) == n
    sim = Sim()
    sim.orden(sim.nucleo.alternar_pausa(sim.t))
    for t, manos in cuadros:
        sim.cuadro(manos)
    assert ("izq", True) in sim.salida.botones()
    sim.durante(300, [])
    sim.invariantes()
