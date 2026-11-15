# Lycan Mouse Control

**Maneje el ratón con las manos, usando la cámara del portátil.** Pensado para diseño: dibujo en 2D
(EDWIN CNC CAD-CAM, LibreCAD) y modelado en 3D (EDWIN CNC 3D, SketchUp, FreeCAD, Blender).

Lycan Developments / EDWIN CNC — versión 1.0.2

> Es un **complemento** del ratón: sirve para girar modelos en 3D, presentar o descansar la mano.
> Para puntos exactos use el zoom y el enganche del programa de dibujo.

---

## Cómo abrirlo

| Para | Haga esto |
|---|---|
| Usarlo normal | Doble clic en `lycan_mouse_control.pyw` |
| Usarlo desde una consola | `py -3.10 -m lycan_mouse_control` (también sirve `py -3.10 -m lycan_mouse`) |
| **Probar sin riesgo** (el ratón no hace nada) | `py -3.10 -m lycan_mouse_control --simular` |
| Revisar que todo carga (sin cámara) | `py -3.10 -m lycan_mouse_control --check` |
| Arrancar en 3D | `py -3.10 -m lycan_mouse_control --modo 3D` |
| Arrancar con la ventana pequeña | `py -3.10 -m lycan_mouse_control --minimizado` |

El programa **arranca en pausa**. La primera vez se abre un asistente para practicar las señas;
mientras practica, el ratón no hace nada.

Con `--simular` la ventana muestra "(ensayo)", dibuja un anillo donde estaría el puntero y anota en el
registro cada acción ("Presionar botón izquierdo", "Rueda acercar"...). Así puede probar todas las señas
sin mover el ratón real.

### Requisitos
Windows 10/11 de 64 bits, cámara, Python 3.10 con: `mediapipe==0.10.14`, `numpy==2.2.6`,
`opencv-python-headless==4.10.0.84` (u opencv), `Pillow`. tkinter, ctypes y winsound vienen con Python.
No usa pynput ni pyautogui.

```
py -3.10 -m pip install -r requirements.txt
```

---

## Señas

### Mouse Control 2D

| Seña | Qué hace |
|---|---|
| Índice y corazón estirados y **pegados**, una vez (en pausa), un cuarto de segundo | **Activar** |
| La misma seña **dos veces seguidas** (activo) | **Pausar** y soltar todo |
| Mover el dedo índice | **Mover el puntero** (sin temblor) |
| Pellizco pulgar + índice y soltar | **Clic izquierdo** (cae donde estaba el puntero antes de cerrar los dedos) |
| Pellizco sostenido y mover | **Arrastrar** |
| Dos pellizcos rápidos | **Doble clic** |
| Puño cerrado (un momento) | **Clic derecho** |
| Dos manos en pellizco: separarlas / juntarlas | **Acercar / alejar** (rueda) |
| Dos manos en pellizco movidas juntas | **Mover el dibujo** (botón del medio) |
| *(Opcional, apagado)* Pellizco pulgar + corazón y subir/bajar la mano | Acercar / alejar con una mano |
| Sacar la mano | **Se suelta todo** (y pausa sola a los 10 s sin manos) |

### Mouse Control 3D (todo lo de 2D, más:)

| Seña | Qué hace |
|---|---|
| Un puño cerrado y moverlo (1.0.2, de fábrica) — o, con «Dos puños», las dos manos cerradas como un volante | **Girar el modelo** (botón del medio sostenido) |
| Dos manos en pellizco movidas juntas | **Mover el modelo** (Shift + botón del medio) |
| Abrir las manos | **Soltar** |
| Puño con **una** mano | Clic derecho (espera un poco más para no confundirse con girar) |

### Novedades de la 1.0.2

| Seña o tecla | Qué hace | De fábrica | Dónde se cambia |
|---|---|---|---|
| Pellizco pulgar + **anular** | Clic izquierdo y arrastre; el índice que apunta no se mueve | Prendido | ⚙ > Clic |
| Pellizco pulgar + **meñique** | Doble clic (o clic derecho, del medio, Enter, Esc, Suprimir, Deshacer, Nada) | Doble clic | ⚙ > Clic |
| **5 del teclado numérico** (o la tecla/pedal que grabe) | Sostener = botón abajo; un toque = clic; dos = doble clic. En pausa escribe normal | Prendido | ⚙ > Clic > Cambiar tecla |
| (3D) **Un puño** cerrado y movido | Girar el modelo; quieto 300 ms sigue siendo clic derecho. Se suelta abriendo la mano o apuntando | Un puño | ⚙ > Girar |
| (3D) Soltar el puño moviéndolo rápido (solo con el giro de un puño o «Los dos») | El modelo sigue girando y frena solo; un puño lo atrapa | Apagado | ⚙ > Girar > Lanzar |
| Abrir / cerrar la mano **de golpe** | Manda el atajo que usted escriba (despiezar / armar) | Sin atajo | ⚙ > Girar |
| **Palma** abierta, dedos separados, quieta medio segundo; luego subir/bajar | Pasar página (rueda). En programas de diseño es zoom | Prendido | ⚙ > Palma |
| Palma estirada pasada rápido a un lado | Siguiente / anterior (flechas; Alt+flechas en el navegador) | Prendido | ⚙ > Palma |
| Mano baja, cerca del teclado | Postura nueva en el asistente y en la calibración | Apagado | ⚙ > Comodidad |

El giro con dos puños (el de la 1.0.1) sigue disponible en ⚙ > Girar > «Dos puños» o «Los dos».

### Atajos de teclado (funcionan con cualquier programa al frente)

| Atajo | Acción |
|---|---|
| `Ctrl+Alt+M` | Pausar / activar |
| `Ctrl+Alt+X` | Salir (suelta todo antes) |
| `Ctrl+Alt+O` | Mostrar / ocultar la ventana |
| `Ctrl+Alt+D` | Cambiar 2D / 3D (queda en pausa) |
| `Ctrl+Alt+P` | Modo dibujo fino |

No se usa `Ctrl+Alt+Q` porque en el teclado latinoamericano escribe "@". Al arrancar, el programa revisa
que ningún atajo escriba un carácter en su teclado; si alguno lo hace, no lo usa y avisa.

### Perfiles por programa (automáticos)

| Programa | Girar | Mover | Rueda |
|---|---|---|---|
| EDWIN CNC 3D (`ingetrazo.exe`) | Medio | Shift + medio | Suave (fracciones) |
| SketchUp | Medio | Shift + medio | Normal |
| FreeCAD (estilo CAD) | Medio + izquierdo | Medio | Normal |
| FreeCAD (estilo Blender; en «Automático» se nota solo, leyendo las preferencias de FreeCAD) | Medio | Shift + medio | Normal |
| Blender | Medio | Shift + medio | Normal |
| EDWIN CNC CAD-CAM / LibreCAD | — | Medio | Pasos completos, máximo 8 por segundo |
| Navegador (Chrome, Edge, Firefox, Brave, Opera; 1.0.2) | Medio | Medio (2D) / Shift + medio (3D) | Normal; barrido = Alt+flechas |
| Genérico (cualquier otro) | Medio | Medio (2D) / Shift + medio (3D) | Normal; barrido = flechas |

---

## Seguridad: nada queda presionado

- Si se pierde la mano (150 ms), se pausa, se cambia de modo o de programa, se sale, o algo falla:
  se sueltan **siempre** todos los botones y después Shift/Ctrl/Alt.
- Al mover el modelo, Shift baja antes que el botón del medio y sube después.
- Nunca se envía rueda con Shift o Ctrl presionados.
- Con el puntero sobre la ventana de Lycan Mouse Control no se hace clic.
- Si la ventana activa se abrió como administrador, el control se pone en espera y avisa
  (menú **?** → "Reiniciar como administrador").
- Si se cerró a la fuerza y algo quedó presionado: presione y suelte Shift y el botón de la rueda del ratón.

Configuración: `%APPDATA%\Lycan Mouse Control\config.json` (si se daña, se aparta y se usan los valores
de fábrica). Registro de errores: `%APPDATA%\Lycan Mouse Control\registros\registro.txt` (menú **?** →
"Abrir carpeta de registros"). Nunca se guardan imágenes de la cámara.

---

## Para desarrolladores

### Estructura

```
lycan_mouse_control/        paquete (así lo espera el .spec)
  geometria.py filtros.py senas.py      medidas, One Euro/histéresis, clasificador (puro)
  seguidor.py mapeo.py puntero.py        identidad de manos, zona -> pantalla, puntero
  estados.py nucleo.py perfiles.py       máquina de estados y perfiles (puro)
  acciones.py salida/                    acciones -> SendInput (windows.py) o simulada
  captura.py detector.py motor.py        cámara, MediaPipe, bucle principal
  sistema/                               DPI, pantallas, ventanas, atajos, sonidos, inicio
  ui/                                    tkinter: ventana, indicador, opciones, ayuda, asistente
  sintetico.py                           manos sintéticas (pruebas, chuleta y asistente)
pruebas/                    pytest (sin cámara ni ratón real)
herramientas/               medir_fps.py, grabar.py (sesiones reales .npz)
empaquetado/                .spec, rthook, version_info, .iss
.github/workflows/windows.yml
docs/especificacion.md
```

Regla de oro: la lógica de señas y estados es **pura** (recibe puntos y tiempos, devuelve acciones);
solo `salida/windows.py` toca Windows. Por eso todo se prueba sin cámara.

### Pruebas

```
py -3.10 -m pip install -r requirements-dev.txt
py -3.10 -m pytest -q
```

Las pruebas usan manos sintéticas (cambio de tamaño, giros de ±40°, mano izquierda/derecha, ruido de
1, 2 y 4 mm, dedos fuera de lugar) y recorren las 36 secuencias de la especificación (E1–E36) más
casos extra, revisando al final que nada quede presionado.

### Medir el rendimiento con la cámara real

```
py -3.10 herramientas\medir_fps.py --segundos 30 --manos 2
py -3.10 herramientas\medir_fps.py --segundos 30 --manos 1
py -3.10 -m lycan_mouse_control --simular --prueba-segundos 20 --informe informe.json
```

### Grabar sesiones reales (para ajustar los umbrales con la HP TrueVision)

```
py -3.10 herramientas\grabar.py --guion
```

### Compilar (entorno limpio, versiones fijas)

```
py -3.10 -m venv .venv-build
.venv-build\Scripts\pip install mediapipe==0.10.14 numpy==2.2.6 Pillow pyinstaller==6.22.3
.venv-build\Scripts\pip uninstall -y opencv-contrib-python
.venv-build\Scripts\pip install opencv-python-headless==4.10.0.84
.venv-build\Scripts\pyinstaller empaquetado\lycan-mouse-control.spec --noconfirm
dist\LycanMouseControl\LycanMouseControl.exe --check
iscc /DMyAppVersion=1.0.2 empaquetado\lycan-mouse-control.iss
```

El instalador no pide administrador, pregunta al desinstalar si se borra la configuración (por defecto
la conserva) y usa siempre el mismo AppId. El workflow `.github/workflows/windows.yml` hace lo mismo en
la nube (pruebas, compilación, revisión del paquete, `--check`, instalador y ZIP) y deja los archivos
como artifacts; **no publica nada**.

### Decisiones tomadas al construir (para revisar con el usuario)

- **Acercar/alejar con dos manos**: la distancia se mide entre los nudillos de cada mano (puntos 5 y 9),
  no entre las puntas del pellizco: al abrir los dedos para soltar, las puntas se mueven 1-2 cm y daban
  una muesca de más.
- **Pellizco con la otra mano a la vista**: el clic espera 150 ms (en vez de 66) y se cancela si la otra
  mano también pellizca, para que empezar un zoom no haga un clic izquierdo.
- **Clic limpio**: además del rebobinado de 100 ms, si la mano venía quieta el clic cae en el último punto
  quieto (hasta 250 ms atrás), porque el corrimiento del índice ocurre justo antes de reconocer el pellizco.
- **Clasificador**: suaviza los puntos de la mano (además de cada medida) para que el meñique, que tiene
  los huesos más cortos, no tiemble entre "estirado" y "doblado".
- **Mover el dibujo con dos manos en pellizco** (sugerencia S5) está **activado** por defecto; se apaga en
  Opciones > Señas. **Ctrl+Alt+X** para salir (S1). Pendiente de confirmar con el usuario.
