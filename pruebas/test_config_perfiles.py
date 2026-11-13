"""11.5: configuración (archivos dañados, tipos, rangos, versión, escritura atómica) y perfiles."""
import json

import pytest

from lycan_mouse_control import config as C
from lycan_mouse_control import perfiles as P
from lycan_mouse_control.acciones import Bajar, Esperar, Rueda, Subir, Tecla


def test_archivo_ausente_usa_fabrica(tmp_path):
    c = C.Configuracion(tmp_path / "no" / "config.json")
    d = c.cargar()
    assert d == C.por_defecto()
    assert c.aviso is None


@pytest.mark.parametrize("contenido", ["", "   ", "{malo", "[1, 2]", "null", "\x00\x01"])
def test_archivo_vacio_o_danado_se_aparta_y_avisa(tmp_path, contenido):
    ruta = tmp_path / "config.json"
    ruta.write_text(contenido, encoding="utf-8")
    c = C.Configuracion(ruta)
    d = c.cargar()
    assert d == C.por_defecto()
    assert c.aviso == "Se restableció la configuración."
    apartados = list(tmp_path.glob("config.dañado-*.json"))
    assert len(apartados) == 1


def test_tipos_equivocados_y_fuera_de_rango_vuelven_a_fabrica(tmp_path):
    ruta = tmp_path / "config.json"
    datos = C.por_defecto()
    datos["modo"] = "4D"
    datos["camara"]["indice"] = "cero"
    datos["puntero"]["mincutoff"] = 99
    datos["senas"]["tiempos_ms"]["pausa_sin_mano_s"] = 1
    datos["comodidad"]["sonidos"] = "si"
    datos["senas"]["doblez"]["extendido"] = [60]
    datos["zoom"]["paso_log"] = float("nan")
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    c = C.Configuracion(ruta)
    d = c.cargar()
    f = C.FABRICA
    assert d["modo"] == f["modo"]
    assert d["camara"]["indice"] == 0
    assert d["puntero"]["mincutoff"] == f["puntero"]["mincutoff"]
    assert d["senas"]["tiempos_ms"]["pausa_sin_mano_s"] == 10
    assert d["comodidad"]["sonidos"] is True
    assert d["senas"]["doblez"]["extendido"] == [60, 85]
    assert d["zoom"]["paso_log"] == 0.08
    assert len(c.problemas) >= 7


def test_valores_validos_se_conservan(tmp_path):
    ruta = tmp_path / "config.json"
    datos = C.por_defecto()
    datos["modo"] = "3D"
    datos["senas"]["tiempos_ms"]["pausa_sin_mano_s"] = 30
    datos["perfiles"]["personalizados"] = {"mio": {"nombre": "Mío", "exes": ["mio.exe"]}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    d = C.Configuracion(ruta).cargar()
    assert d["modo"] == "3D" and d["senas"]["tiempos_ms"]["pausa_sin_mano_s"] == 30
    assert d["perfiles"]["personalizados"]["mio"]["nombre"] == "Mío"


def test_claves_faltantes_se_completan(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"modo": "3D"}), encoding="utf-8")
    d = C.Configuracion(ruta).cargar()
    assert d["modo"] == "3D" and d["zoom"] == C.FABRICA["zoom"]


def test_version_futura_avisa_y_valida(tmp_path):
    ruta = tmp_path / "config.json"
    datos = C.por_defecto()
    datos["version"] = 99
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    c = C.Configuracion(ruta)
    d = c.cargar()
    assert d["version"] == 1
    assert c.aviso == "Se restableció la configuración."


def test_zona_demasiado_pequena(tmp_path):
    datos = C.por_defecto()
    datos["zona"].update({"x0": 0.5, "x1": 0.52})
    d = C.validar(datos)
    assert d["zona"]["x0"] == 0.2


def test_escritura_atomica_y_utf8(tmp_path):
    ruta = tmp_path / "sub" / "config.json"
    c = C.Configuracion(ruta)
    c.cargar()
    c.datos["calibracion"]["luz"] = 120.5
    c.datos["perfiles"]["personalizados"] = {"x": {"nombre": "Diseño ñandú"}}
    c.guardar()
    assert json.loads(ruta.read_text(encoding="utf-8"))["perfiles"]["personalizados"]["x"]["nombre"] == "Diseño ñandú"
    assert not list(ruta.parent.glob("*.tmp"))


def test_escritura_atomica_no_deja_el_archivo_a_medias(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    c = C.Configuracion(ruta)
    c.cargar()
    c.guardar()
    antes = ruta.read_text(encoding="utf-8")
    monkeypatch.setattr(C.json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("disco lleno")))
    with pytest.raises(OSError):
        c.guardar()
    assert ruta.read_text(encoding="utf-8") == antes
    assert not list(tmp_path.glob("*.tmp"))


def test_restablecer_fabrica_conserva_atajos_y_ventana(tmp_path):
    c = C.Configuracion(tmp_path / "c.json")
    c.cargar()
    c.datos["atajos"]["pausar"] = "Ctrl+Alt+K"
    c.datos["ventana"]["x"] = 10
    c.datos["modo"] = "3D"
    d = c.restablecer_fabrica()
    assert d["atajos"]["pausar"] == "Ctrl+Alt+K" and d["ventana"]["x"] == 10 and d["modo"] == "2D"


def test_carpeta_de_datos_por_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("LYCAN_MOUSE_DATOS", str(tmp_path))
    assert C.ruta_config() == tmp_path / "config.json"
    monkeypatch.delenv("LYCAN_MOUSE_DATOS")
    monkeypatch.setenv("APPDATA", str(tmp_path / "ad"))
    assert C.ruta_config() == tmp_path / "ad" / "Lycan Mouse Control" / "config.json"


# ---------------------------------------------------------------- perfiles
@pytest.mark.parametrize("ruta,clave", [
    (r"C:\Program Files\EDWIN CNC 3D\ingetrazo.exe", "edwin3d"),
    (r"C:\PROGRAM FILES\EDWIN CNC 3D\IngeTrazo.EXE", "edwin3d"),
    (r"C:\Program Files\SketchUp\SketchUp 2024\SketchUp.exe", "sketchup"),
    (r"C:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe", "freecad"),
    ("freecad.exe", "freecad"),
    (r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe", "blender"),
    (r"C:\EDWIN\EDWIN-CNC.exe", "edwin2d"),
    (r"C:\EDWIN\edwin-cnc-v1.0.14.exe", "edwin2d"),
    ("C:/LibreCAD/librecad.exe", "edwin2d"),
    (r"C:\Windows\notepad.exe", "generico"),
    ("", "generico"),
    (None, "generico"),
    (r"\\?\C:\Una ruta muy larga" + r"\sub" * 40 + r"\SketchUp.exe", "sketchup"),
])
def test_cada_exe_resuelve_su_perfil(ruta, clave):
    assert P.perfil_para_exe(ruta).clave == clave


def test_perfiles_personalizados_y_danados():
    pers = {"mio": {"nombre": "Mi CAD", "exes": ["micad*.exe"], "modo_sugerido": "3D",
                    "orbitar": {"botones": ["der"]}, "desplazar": {"botones": ["medio"], "teclas": ["ctrl"]}},
            "malo": "no es un dict"}
    p = P.perfil_para_exe(r"C:\x\MiCAD2.exe", pers)
    assert p.nombre == "Mi CAD" and p.orbitar.botones == ("der",) and p.desplazar.teclas == ("ctrl",)
    assert P.obtener("malo", pers).clave == "generico"


def test_traductor_orden_shift_medio():
    tr = P.Traductor(P.PERFILES["sketchup"])
    assert tr.empezar(P.SHIFT_MEDIO) == [Tecla("shift", True), Esperar(20), Bajar("medio")]
    assert tr.terminar(P.SHIFT_MEDIO) == [Subir("medio"), Esperar(15), Tecla("shift", False)]


def test_traductor_freecad_medio_luego_izquierdo():
    tr = P.Traductor(P.PERFILES["freecad"])
    assert tr.empezar(P.MEDIO_IZQ) == [Bajar("medio"), Esperar(20), Bajar("izq")]
    assert tr.terminar(P.MEDIO_IZQ) == [Subir("izq"), Subir("medio")]


def test_traductor_limite_de_muescas():
    tr = P.Traductor(P.PERFILES["edwin2d"], max_muescas_cfg=8)
    t, n = 0.0, 0
    for k in range(100):
        t += 0.01
        if tr.puede_muesca(t):
            tr.gastar_muesca()
            n += 1
    assert n <= 9   # 1 s: la primera + 8 por segundo


def test_traductor_rueda_fraccionaria_minimo_15():
    tr = P.Traductor(P.PERFILES["edwin3d"])
    assert tr.fraccion(0.05) == []          # 6 < 15
    r = tr.fraccion(0.1)                    # 6 + 12 = 18
    assert r == [Rueda(18)]


def test_combinaciones_por_modo():
    g = P.GENERICO
    assert g.combinacion_desplazar("2D") == P.MEDIO
    assert g.combinacion_desplazar("3D") == P.SHIFT_MEDIO
    assert P.PERFILES["edwin2d"].combinacion_orbitar("3D") == P.MEDIO
    assert "Shift" in P.SHIFT_MEDIO.describir()
