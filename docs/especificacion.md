# Lycan Mouse Control: especificación v1.0

| Dato | Valor |
|---|---|
| Producto | Lycan Mouse Control (Lycan Developments / EDWIN CNC) |
| Qué hace | Convierte la cámara del portátil en un ratón manejado con gestos de las manos, pensado para diseño (CAD 2D y modelado 3D) |
| Modos | **Mouse Control 2D** y **Mouse Control 3D** (el 3D tiene las mismas señas que el 2D más las de girar y desplazar el modelo) |
| Equipo de referencia | Portátil con Windows 11, 8 GB de RAM, sin NVIDIA, cámara "HP TrueVision HD Camera", pantalla 1366x768 al 100 % |
| Lenguaje | Python 3.10 (siempre `py -3.10`), mediapipe 0.10.14 (`mp.solutions.hands`), opencv, numpy 2.2.6, Pillow, tkinter 8.6, ctypes. **Sin pynput ni pyautogui** |
| Carpeta | `C:\dev\lycan-mouse-control` |
| Idioma | Todo lo que ve el usuario va en español de Colombia, con trato de "usted" y sin jerga |
| Fecha | 2026-11-12 |
| Estado | Especificación para construir. Nada se publica, no se crea repositorio y no se hace push en esta fase |

> Convención de este documento: **[ACORDADO]** marca lo que el usuario decidió y no se cambia; **[SUGERENCIA]** marca lo que la investigación propone cambiar o agregar. Las sugerencias quedan anotadas en la sección 16 y **no** se aplican sin que el usuario las apruebe.

---

## 1. Objetivo y alcance

### 1.1 Qué debe lograr la v1.0
1. Mover el puntero con el dedo índice, sin temblor, con precisión suficiente para enganchar puntos en EDWIN CNC CAD-CAM cuando se combina con el zoom del programa.
2. Hacer clic izquierdo, arrastrar, clic derecho y usar la rueda (acercar y alejar) con señas.
3. En 3D: girar (orbitar) y desplazar el modelo en SketchUp, EDWIN CNC 3D, FreeCAD y Blender con la seña de "agarrar con dos manos".
4. Activar y pausar con la seña acordada, y pausar o salir desde el teclado en cualquier momento.
5. **No dejar nunca un botón ni una tecla presionados** si se pierde la mano, se pausa, se sale o el programa falla.
6. Funcionar a 25 cuadros por segundo o más en el portátil del usuario.
7. Entregarse como instalador de Windows (PyInstaller + Inno Setup), sin pedir permisos de administrador.

### 1.2 Fuera de alcance en la v1.0
- Reemplazar el ratón al 100 %. Se presenta como **complemento** (orbitar en 3D, presentar, descansar la mano del ratón). La ayuda lo dice con claridad.
- Escribir texto o dictar coordenadas (eso sigue siendo con el teclado).
- Ratones 3D (3Dconnexion), varias cámaras a la vez y sistemas distintos de Windows 10/11 de 64 bits.
- Firma digital del ejecutable (se evalúa después).
- Publicación, repositorio y página de descarga (fase posterior).

---

## 2. Arquitectura general

### 2.1 Hilos y flujo de datos

```
 [Hilo CÁMARA]                [Hilo MOTOR]                                    [Hilo INTERFAZ = principal, tkinter]
 cv2.VideoCapture ──► cuadro ──► Detector (MediaPipe) ──► Seguidor de manos ──► Clasificador de señas
 (solo guarda el      + t_captura                                                      │
  último cuadro)                                                                       ▼
                                  Filtros (One Euro) ◄── Mapeo zona→pantalla ◄── Máquina de estados ──► Salida Windows (SendInput)
                                                                                       │
                                                                       Estado para pintar (cola de 1) ───► Ventana, indicador, sonidos
 [Hilo ATAJOS] RegisterHotKey + GetMessageW ──► cola de órdenes ──► Motor / Interfaz
 [Temporizador 1 s en el motor] ventana activa ──► Perfiles (cambia perfil, detecta ventana de administrador)
```

- **Cámara** (`captura.py`): lee sin parar y guarda solo el cuadro más reciente con su `t_captura = time.perf_counter()`. Nunca hace cola. Así no se acumula retraso.
- **Motor** (`motor.py`): un solo bucle que toma el último cuadro, corre MediaPipe, clasifica, decide y envía a Windows. Es el **único** que llama a la salida de ratón, salvo `soltar_todo()`, que es seguro desde cualquier hilo.
- **Interfaz** (`ui/`): tkinter en el hilo principal. Solo pinta lo que el motor deja en una `queue.Queue(maxsize=1)` (se descarta el viejo). Nunca toca la cámara ni MediaPipe.
- **Atajos** (`sistema/atajos.py`): hilo propio con `RegisterHotKey` y `GetMessageW`. El registro y el bucle van en el mismo hilo. Las órdenes pasan por una cola; nunca se toca tkinter desde este hilo.

### 2.2 Regla de oro de la arquitectura
**La lógica de señas y estados es pura**: recibe puntos de mano y tiempos, y devuelve una lista de **acciones** (`Mover(x,y)`, `Bajar('izq')`, `Subir('medio')`, `Rueda(+120)`, `Tecla('shift', abajo)`, `SoltarTodo`, `Aviso(...)`). No importa ctypes, ni cv2, ni tkinter. Una capa delgada (`salida/windows.py`) convierte esas acciones en `SendInput`. Esto permite probar todo con pytest sin cámara y sin mover el ratón real, usando una **salida simulada** que solo anota las acciones.

### 2.3 Estructura de carpetas

```
C:\dev\lycan-mouse-control\
  lanzar.py                         # from lycan_mouse_control.app import main; main()
  requirements.txt                  # versiones fijas (sección 13.1)
  requirements-dev.txt              # + pytest, pyinstaller
  lycan_mouse_control\
    __init__.py
    version.py                      # VERSION = "1.0.0"
    app.py                          # main(): DPI, argumentos (--check, --minimizado, --simular), arranque y cierre seguro
    constantes.py                   # índices de puntos de la mano, valores de fábrica
    config.py                       # lectura/escritura de config.json, validación, valores por defecto
    registro.py                     # registro de errores en archivo
    captura.py                      # hilo de cámara
    detector.py                     # MediaPipe Hands -> ManoDetectada (puntos de imagen y en metros)
    seguidor.py                     # identidad estable de cada mano, mano principal, orden por x
    geometria.py                    # funciones puras: escala de palma, doblez, distancias, ángulos
    senas.py                        # clasificador puro: puntos -> Sena (con histéresis)
    filtros.py                      # OneEuro, Histeresis, Antirrebote, PromedioExp
    mapeo.py                        # zona activa -> monitor elegido (espejo, aspecto, recorte)
    puntero.py                      # filtro + zona muerta + rebobinado/ancla de pellizco + modo relativo
    estados.py                      # máquina de estados principal (activar/pausar, clic, arrastre, zoom, órbita, desplazar)
    acciones.py                     # dataclasses de acciones (Mover, Bajar, Subir, Rueda, Tecla, SoltarTodo, Aviso)
    perfiles.py                     # perfiles por programa y traductor de acciones abstractas (orbitar/desplazar/rueda)
    motor.py                        # bucle: une todo, mide fps y latencia
    salida\
      __init__.py
      base.py                       # interfaz Salida (aplicar(acciones), soltar_todo())
      windows.py                    # SendInput real (a partir de referencia\winput.py)
      simulada.py                   # anota acciones y estado de botones/teclas para pruebas y modo ensayo
    sistema\
      dpi.py                        # SetProcessDpiAwarenessContext(-4) con respaldos
      pantallas.py                  # escritorio virtual y monitores (EnumDisplayMonitors)
      ventanas_win.py               # ventana activa, nombre del .exe, elevación, WS_EX_NOACTIVATE
      atajos.py                     # HotkeyThread (RegisterHotKey) + comprobación de AltGr con ToUnicode
      sonidos.py                    # winsound en hilo aparte
    ui\
      textos.py                     # TODOS los textos de cara al usuario en un diccionario TXT
      ventana_principal.py
      indicador_cursor.py
      asistente.py                  # asistente de primera vez (modo ensayo, sin SendInput)
      calibracion.py
      opciones.py
      ayuda.py                      # globos "?" y chuleta de señas
  pruebas\                          # pytest (sección 12)
    sintetico\mano_sintetica.py     # generador de manos por código
    ...
  herramientas\
    grabar.py                       # graba sesiones reales (.npz: puntos 21x3 por cuadro + seña pedida) para pruebas de regresión
  recursos\                         # lycan-mouse.ico, sonidos .wav opcionales
  empaquetado\                      # .spec, rthook, version_info.txt, .iss, workflow (ya existen)
  referencia\                       # winput.py, puntero_ref.py, test_winput.py, test_tk.py (código probado de la investigación)
  docs\especificacion.md            # este documento
```

El paquete se llama `lycan_mouse_control` porque así lo espera `empaquetado\lycan-mouse-control.spec` (`lanzar.py` → `from lycan_mouse_control.app import main`).

---

## 3. Módulos en detalle

### 3.1 `app.py`: arranque y cierre
Orden obligatorio de `main()`:
1. `sistema.dpi.activar()` **en la primera línea**, antes de importar tkinter o leer medidas de pantalla: `user32.SetProcessDpiAwarenessContext(-4)` (PER_MONITOR_AWARE_V2); si falla, `shcore.SetProcessDpiAwareness(2)`; si falla, `user32.SetProcessDPIAware()`. Se registra cuál quedó.
2. Configurar el registro de errores (3.13).
3. Leer argumentos:
   - `--check`: importa mediapipe, crea `Hands(model_complexity=0)`, procesa `np.zeros((480,640,3), np.uint8)` **sin abrir la cámara ni mover el ratón** y sale con código 0 (o 1 y el error en el registro). Lo usa el workflow, porque el servidor de GitHub no tiene cámara.
   - `--minimizado`: arranca con la ventana en modo mini (para "Abrir al encender el computador").
   - `--simular`: usa `salida/simulada.py` (nada llega a Windows). Útil para soporte y para probar.
4. Cargar `config.json` (3.12).
5. Crear la salida, registrar `atexit.register(salida.soltar_todo)` y los manejadores de señales (`signal.SIGINT`, `SIGBREAK`).
6. Arrancar hilos: cámara, motor y atajos.
7. Crear la interfaz. Si `config["primera_vez"]` es verdadero, abrir el asistente.
8. `root.protocol("WM_DELETE_WINDOW", salir_seguro)`.
9. Todo el bucle va dentro de `try/except/finally`; el `finally` llama `soltar_todo()`, detiene los hilos y libera la cámara.

`salir_seguro()`: `soltar_todo()` → detener motor → soltar cámara → anular atajos (`UnregisterHotKey` + `PostThreadMessageW(WM_QUIT)`) → guardar posición de la ventana → `root.destroy()`.

Instancia única: un mutex con nombre (`CreateMutexW(None, False, "Local\\LycanMouseControl")`). Si ya existe, se muestra "Lycan Mouse Control ya está abierto." y se trae al frente la ventana existente.

### 3.2 `captura.py`: cámara
- Abrir con `cv2.VideoCapture(indice, cv2.CAP_DSHOW)`; si no entrega cuadros en 2 s, probar `cv2.CAP_MSMF`.
- Pedir 640x480 a 30 fps, `CAP_PROP_BUFFERSIZE=1`. Probar `FOURCC 'MJPG'`; si los fps bajan, volver al formato por defecto.
- Intentar desactivar la bajada automática de fps con poca luz (`CAP_PROP_AUTO_EXPOSURE` / prioridad de exposición) solo si la cámara lo acepta; si no, no insistir.
- `cv2.flip(frame, 1)` **una sola vez, aquí**, antes de todo lo demás. Con la imagen en espejo, la etiqueta "Right" de MediaPipe corresponde a la mano derecha real y el puntero va hacia donde va la mano. **Nunca** se vuelve a invertir x en otro lugar.
- Publica `Cuadro(imagen_bgr, t_captura, numero)` en una ranura protegida con `Lock` (se sobrescribe).
- Si `read()` falla 15 veces seguidas: estado `CAMARA_PERDIDA`, se avisa al motor (que hace `soltar_todo()`), y se reintenta abrir cada 2 s. Texto: "La cámara se desconectó. Reintentando…".
- Si no abre al inicio: "No encuentro la cámara. Revise que ningún otro programa (Zoom, Teams, Cámara) la esté usando."

### 3.3 `detector.py`: MediaPipe
- `mp.solutions.hands.Hands(static_image_mode=False, model_complexity=0, max_num_hands=N, min_detection_confidence=0.6, min_tracking_confidence=0.5)`.
- `N = 2` en 3D. En 2D, `N = 2` por defecto porque el zoom con dos manos lo necesita. **Compuerta de rendimiento:** si la prueba de la sección 11 muestra menos de 25 fps con `N = 2` en 2D, el 2D pasa a `N = 1` y se activa por defecto la variante de zoom con una mano (5.2).
- Entrada: la imagen en espejo, reducida a 640x360 o 640x480 y convertida a RGB, con `rgb.flags.writeable = False`.
- Salida por mano: `ManoDetectada(img: ndarray 21x3, mundo: ndarray 21x3, etiqueta: 'Left'|'Right', confianza: float)`.
  - `img`: `multi_hand_landmarks`, coordenadas 0..1 de la imagen. Se usan para el **puntero** y para las **distancias entre las dos manos**.
  - `mundo`: `multi_hand_world_landmarks`, en metros, con origen en el centro de la mano. Se usan para **clasificar las señas** (no cambian con la distancia a la cámara).
  - La `z` de `img` no se usa para nada.
- Mide `t_fin_mediapipe` para el cálculo de latencia.

### 3.4 `seguidor.py`: identidad de las manos
- MediaPipe intercambia el orden y a veces la etiqueta de las manos entre cuadros. No se confía en ninguno de los dos.
- A cada mano detectada se le asigna la pista anterior cuyo punto 9 (base del corazón, en `img`) esté más cerca. Si la distancia supera 0.25 del ancho de la imagen, es una mano nueva.
- La etiqueta (izquierda/derecha) de cada pista se decide por **mayoría de votos en los últimos 15 cuadros**.
- **Mano principal** (configurable: Derecha, por defecto; Izquierda): mueve el puntero y hace los clics. Si solo hay una mano en cuadro, esa mano es la principal aunque su etiqueta diga otra cosa (el usuario puede usar cualquier mano sola).
- Para gestos de dos manos, las manos se ordenan **por la x de la muñeca (punto 0)** en cada cuadro: "izquierda en pantalla" y "derecha en pantalla".
- Un salto de una pista mayor a 0.15 de la imagen en un cuadro se marca como sospechoso (posible confusión entre manos) y ese cuadro no produce movimiento de órbita ni de desplazamiento.
- Mano perdida: una pista sin detección se conserva 150 ms (con posición predicha por velocidad durante 100 ms como máximo) y luego se elimina.

### 3.5 `geometria.py`: medidas puras
Índices de MediaPipe: 0 muñeca; pulgar 1-4; índice 5-8; corazón 9-12; anular 13-16; meñique 17-20 (MCP = nudillo de la base, PIP = articulación del medio, DIP = articulación de la punta).

| Función | Definición |
|---|---|
| `escala_palma(w)` | `(|0-5| + |0-17| + |5-17| + |0-9|) / 4` con puntos en metros (típico 0.075-0.095 m) |
| `centro_palma(w)` | `C = promedio de 0, 5, 9, 13, 17` |
| `ang(a, b)` | `degrees(arccos(clip(dot(a,b)/(|a||b|+1e-9), -1, 1)))` |
| `doblez(w, dedo)` | `ang(MCP→PIP, PIP→DIP) + ang(PIP→DIP, DIP→punta)`; 0° = recto. Dedos: índice (5,6,7,8), corazón (9,10,11,12), anular (13,14,15,16), meñique (17,18,19,20) |
| `razon_dedo(w, dedo)` | `|punta-0| / |PIP-0|` (solo para desempatar) |
| `pellizco(w)` | `p = |4-8| / escala_palma` |
| `pellizco_corazon(w)` | `pc = |4-12| / escala_palma` |
| `separacion_ic(w)` | `s = |8-12| / |5-9|` (índice-corazón comparado con sus nudillos) |
| `angulo_ic(w)` | `a = ang(8-5, 12-9)` |
| `pulgar_recogido(w)` | `|4-9|/palma < 0.55` o `|4-13|/palma < 0.55` |
| `punta_cerca_palma(w, punta)` | `|punta-C| / palma` |

Todas son funciones puras sobre `ndarray` de 21x3 y se prueban una por una.

### 3.6 `filtros.py`
- `Histeresis(entrar, salir, menor_es_dentro=True)` → `actualizar(valor) -> bool`. Solo cambia de estado al cruzar el umbral contrario.
- `Antirrebote(ms_entrar, ms_salir)` → `actualizar(crudo: bool, t: float) -> bool`. **Siempre en milisegundos medidos con `time.perf_counter()`**, nunca en número de cuadros, para que funcione igual a 15 o a 30 fps.
- `PromedioExp(alfa=0.5)` para suavizar cada medida (doblez, p, s) antes de compararla con los umbrales.
- `OneEuro(mincutoff, beta, dcutoff)` (Casiez 2012): `cutoff = mincutoff + beta·|derivada filtrada|`, `alfa = 1/(1 + tau/dt)`, `tau = 1/(2π·cutoff)`. `dt` sale del `t_captura` real de cada cuadro. Tiene `reset()`.

### 3.7 `senas.py`: clasificador de una mano
Entrada: `w` (puntos en metros, 21x3), el estado anterior (para la histéresis) y los umbrales (de fábrica o calibrados). Salida: **una sola** `Sena` por mano y cuadro, más las medidas (para la barra en vivo y la depuración).

Estados de cada dedo largo (con histéresis; entre los dos umbrales se conserva el estado anterior, "dudoso"):
- EXTENDIDO si `doblez < 60°`; deja de serlo si `doblez > 85°`.
- DOBLADO si `doblez > 110°`; deja de serlo si `doblez < 90°`.
- Desempate con `razon_dedo`: extendido si `> 1.20`, doblado si `< 0.95`.

Pulgar: extendido si `ang(3-2, 4-3) < 35°` y `|4-5|/palma > 0.55`; recogido según `pulgar_recogido`.

`Sena` (enum) y reglas. **Se evalúan en este orden y gana la primera que se cumpla:**

| Prioridad | Seña | Condición (puntos en metros, distancias divididas por la palma) |
|---|---|---|
| 1 | `PUNO` | Los 4 dedos largos DOBLADOS y al menos 3 de las puntas 8, 12, 16, 20 con `|punta-C| < 0.55`; pulgar con `|4-C| < 0.75` |
| 2 | `ACTIVAR` (índice + corazón juntos) | Índice y corazón EXTENDIDOS; anular y meñique DOBLADOS; **juntos** por las dos medidas: `s < 1.25` (sale con `s > 1.50`) y `a < 10°` (sale con `a > 15°`). Pulgar libre |
| 3 | `V` | Índice y corazón EXTENDIDOS; anular y meñique DOBLADOS; `s > 1.9` (sale con `s < 1.6`) y `a > 20°` |
| 4 | `PELLIZCO_CORAZON` | Solo si la variante de zoom con una mano está activada: `pc < 0.28` (sale con `> 0.42`) y `p > 0.5` |
| 5 | `PELLIZCO` | `p < 0.28` (sale con `p > 0.42`), doblez del índice `< 140°` y `|8-C| > 0.55` (no es un puño) |
| 6 | `ABIERTA` | Los 5 dedos extendidos y separación media entre puntas vecinas `> 0.35` |
| 7 | `APUNTAR` | Índice EXTENDIDO y corazón no extendido |
| 8 | `NINGUNA` | Ninguna de las anteriores |

Notas:
- El puño se revisa **antes** que el pellizco, porque al cerrar la mano la punta del pulgar queda cerca de la del índice.
- `V` existe en el clasificador aunque no tenga acción por defecto: sirve para **no confundirla** con `ACTIVAR` y queda disponible para la variante de zoom con una mano propuesta en 16.
- Lado de la palma: `n = (5-0) × (17-0)`; con la etiqueta de la mano dice si la palma mira a la cámara. Solo produce un aviso en la depuración, no bloquea (al orbitar los puños giran).
- Los umbrales de la tabla son los **de fábrica**. La calibración (8.3) puede moverlos como máximo ±40 % respecto a esos valores.

### 3.8 `mapeo.py`: zona activa a pantalla
- Rectángulo de la zona activa en coordenadas 0..1 de la imagen **ya en espejo**. Por defecto (modo "codo apoyado"): `x0=0.20, x1=0.80, y0=0.25, y1=0.70`; el alto se ajusta para que la proporción de la zona coincida con la del monitor (un círculo hecho con la mano sale círculo), sin bajar del 30 % de la imagen.
- Se mapea **a un solo monitor**: el elegido en la configuración; por defecto el principal (`GetMonitorInfoW`, `dwFlags & 1`). Opción "Todo el escritorio" solo si el usuario la pide (con dos pantallas el gesto se vuelve el doble de sensible).
- Fuera de la zona se recorta (clamp) al borde: el borde de la pantalla se alcanza sin sacar el dedo del cuadro.
- Las medidas de pantalla y monitores se vuelven a leer cada 5 s y al recibir `WM_DISPLAYCHANGE` (proyector o segundo monitor).

### 3.9 `puntero.py`: posición del puntero
Punto que se sigue: **punta del índice (punto 8)** de la mano principal, en `img` [ACORDADO: "mover con el dedo índice"]. Ver la sugerencia S2 sobre el nudillo.

Cadena por cuadro (solo cuando el estado lo permite, ver 4):
1. Mapear el punto 8 a píxeles del monitor (3.8).
2. Filtrar **en píxeles de pantalla** con `OneEuro(mincutoff=0.5, beta=0.015, dcutoff=1.0)` por eje (mejor equilibrio en la simulación: temblor quieto 1.5 px, retraso 32 ms a 300 px/s). "Modo dibujo fino": `mincutoff=0.3, beta=0.01`.
3. Zona muerta de **1.5 px** después del filtro: si el salto respecto al último punto enviado es menor, no se mueve (máximo permitido 2 px en modo absoluto). Nunca menos que 0.6 px de la cámara llevados a la pantalla (con el mapeo de fábrica 1 px de la cámara son ~3.6 px de pantalla, así que queda en ~2.1 px; crece si la zona activa es chica).
   **Bloqueo de quieto** (ronda 4): si la velocidad filtrada se mantiene por debajo de 40 px/s durante 150 ms, para volver a mover hace falta pasar de **5 px** (o 1.4 px de la cámara llevados a la pantalla, si es más). Al pasarlos se vuelve a la zona muerta normal, así el arranque sigue rápido. En los primeros 0.6 s de quieto el puntero termina de llegar con el promedio de los últimos 200 ms. Resultado: con temblor de 2 px (σ) el puntero no se mueve más de 2 px en 10 s, a 30 y a 15 cuadros/s.
4. Enviar con `Mover(x, y)` absoluto.

**Clic limpio (contra el "efecto Heisenberg")**: al cerrar el pellizco la punta del índice se corre 10-30 px hacia el pulgar.
- Se guarda un historial de las últimas ~12 posiciones filtradas con su tiempo.
- Cuando el pellizco se confirma, se **rebobina** a la posición de hace ~100 ms y se **ancla** ahí: el botón baja en la posición anclada.
- Mientras la mano no se aleje más de **14 px** de pantalla del ancla, se sigue enviando el punto anclado (clic quieto, sin mini-arrastre).
- Si se aleja más de 14 px, es **arrastre**: el puntero vuelve a seguir la mano (sin salto: se toma el ancla como origen).
- El desplazamiento del arrastre se mide con el **promedio de los nudillos del índice y del corazón (puntos 5 y 9)**, no con la punta del índice: al abrir o cerrar el pellizco la punta se mueve 1-2 cm (unos 200 px) aunque la mano esté quieta.
- En cuanto la seña deja de ser PELLIZCO (antirrebote de salida) el punto de soltar queda quieto: el botón sube donde estaba.
- Al abrir el pellizco, el puntero se congela 100 ms en la posición del momento de soltar (para que la apertura no corra el punto de soltar).

**Reinicio de filtros** (`reset()`): al activar, al reaparecer la mano, al salir de un gesto de dos manos y al cambiar de monitor. Así no hay "latigazo" desde la posición vieja.

**Modo relativo (opcional, apagado por defecto)**: el puntero se mueve por el desplazamiento de la mano, como un touchpad. Ganancia `g = gmin + (gmax-gmin)·smoothstep((v-0.05)/(0.8-0.05))` con `v` = velocidad de la mano en unidades de imagen/s, `gmin=0.6`, `gmax=3.0`. `dx_pantalla = du · ancho_monitor · g` y `dy_pantalla = (dv / aspecto_cámara) · ancho_monitor · g` (u se normaliza por el ancho de la imagen y v por el alto; sin dividir por el aspecto 4:3 el movimiento vertical saldría un 33 % más rápido). La velocidad `v` se mide también con `dv / aspecto_cámara`. Embrague: con la mano en `NINGUNA` o pausado el puntero no se mueve y se puede reacomodar la mano. En modo absoluto **no** hay aceleración.

**Salida de la zona**: si el índice está a menos del 8 % del borde de la zona, el rectángulo de la vista previa se pinta naranja ("Su mano está saliendo de la zona"). Si la mano está fuera de la zona, el puntero sigue a la mano recortado al borde de la pantalla (así se recorren la barra de tareas y los menús). Solo se queda quieto si lleva más de 0.5 s fuera de la zona **y** la punta está a menos del 3 % del borde de la imagen (ahí MediaPipe ya no es confiable); al volver, el puntero llega a la posición nueva en 3-4 cuadros (120 ms), sin saltar.

### 3.10 `estados.py`: máquina de estados principal
Ver la sección 4 (es el corazón del programa).

### 3.11 `salida/`: ratón y teclado de Windows
Base: `referencia\winput.py` (probado en el portátil). Reglas:
- `SendInput` con estructuras `INPUT` (`sizeof == 40` en 64 bits, con `assert`). `argtypes`/`restype` declarados en todas las funciones de ctypes (sin eso, `GetCurrentProcess` se trunca y falla).
- Mover: `MOUSEEVENTF_MOVE | ABSOLUTE | VIRTUALDESK` (`0x0001|0x8000|0x4000`) con la fórmula **redondeando hacia arriba** (probada en los 1366 píxeles, cero errores):
  `nx = ((x - vx)*65536 + vw - 1)//vw`, `ny = ((y - vy)*65536 + vh - 1)//vh`, con `vx, vy, vw, vh = GetSystemMetrics(76, 77, 78, 79)`.
  La fórmula `(x*65536 + w/2)//w` corre el puntero 1 px en la mitad de los casos: **prohibida**.
- **Movimientos durante órbita y desplazamiento**: se envían también en absoluto, como `posición_actual_del_cursor (GetCursorPos) + delta`. No se usan movimientos relativos de `SendInput` porque Windows les aplica la velocidad y la "precisión del puntero mejorada" del usuario, y porque Blender reubica el cursor ("continuous grab") en los bordes.
- Botones en eventos separados: izquierdo `0x02/0x04`, derecho `0x08/0x10`, medio `0x20/0x40`. Un clic suelto (down + up) va en una sola llamada `SendInput`.
- Rueda: `MOUSEEVENTF_WHEEL (0x0800)` con `mouseData` en múltiplos de 120, salvo el perfil que admite fracciones (6).
- Teclas: Shift con `VK_LSHIFT (0xA0)`, Ctrl `VK_LCONTROL (0xA2)`, `KEYEVENTF_KEYUP (0x0002)`.
- `dwExtraInfo = 0x4C59434E` ('LYCN') en todos los eventos propios.
- Registro de lo presionado: `botones_abajo: set`, `teclas_abajo: set`, bajo `Lock`. `Bajar` no hace nada si ya está abajo (no hay dos "down" seguidos).
- `soltar_todo()`: en **una** llamada `SendInput` envía `LEFTUP`, `RIGHTUP`, `MIDDLEUP` de todos los botones que el programa presionó, y luego suelta Shift, Ctrl y Alt (siempre en ese orden: primero botones, después teclas). Vacía el acumulador de la rueda. Soltar de más no hace daño. Es seguro desde cualquier hilo.
- `SM_SWAPBUTTON (23)`: si el usuario tiene los botones invertidos (zurdo), se intercambian izquierdo y derecho al enviar, para que "clic izquierdo" sea el clic principal lógico.
- **UIPI**: si la ventana activa pertenece a un proceso elevado (administrador) y nosotros no, `SendInput` falla **en silencio**. Cada 500 ms se revisa `foreground_is_elevated()`; si es así, se pausa el envío y se avisa: "La ventana activa se abrió como administrador. Para manejarla con gestos, abra Lycan Mouse Control también como administrador." El menú ofrece "Reiniciar como administrador" (`ShellExecuteW(None, "runas", ...)`).
- Si `SendInput` devuelve menos eventos de los pedidos (pantalla bloqueada, aviso de UAC): pausa automática, aviso y reintento silencioso cada 1 s. El programa no se cierra.
- **No se envía nada si la ventana activa es la propia** (ver 9.2).

`salida/simulada.py`: implementa la misma interfaz, guarda la lista de acciones con su tiempo, y lleva el estado de botones y teclas para que las pruebas verifiquen que todo quedó suelto. Se usa en las pruebas, en el asistente y con `--simular`.

### 3.12 `config.py`: configuración
Archivo: `%APPDATA%\Lycan Mouse Control\config.json` (UTF-8). Escritura atómica (archivo temporal + `os.replace`). Si falta, está vacío o dañado: se renombra a `config.dañado-AAAAMMDD-HHMMSS.json`, se usan los valores de fábrica y se avisa "Se restableció la configuración.". Cada valor se valida (tipo y rango); un valor fuera de rango vuelve al de fábrica y se anota en el registro.

```json
{
  "version": 1,
  "primera_vez": true,
  "modo": "2D",
  "mano_principal": "derecha",
  "camara": {"indice": 0, "ancho": 640, "alto": 480, "fps": 30},
  "pantalla": {"monitor": "principal"},
  "zona": {"x0": 0.20, "y0": 0.25, "x1": 0.80, "y1": 0.70, "codo_apoyado": true},
  "puntero": {"modo": "absoluto", "mincutoff": 0.5, "beta": 0.015, "dcutoff": 1.0,
              "zona_muerta_px": 1.5, "umbral_arrastre_px": 14, "rebobinado_ms": 100,
              "dibujo_fino": false, "relativo": {"gmin": 0.6, "gmax": 3.0}},
  "senas": {
    "pellizco": {"entrar": 0.28, "salir": 0.42},
    "pellizco_corazon": {"entrar": 0.28, "salir": 0.42, "activo": false},
    "juntos": {"s_entrar": 1.25, "s_salir": 1.50, "a_entrar": 10, "a_salir": 15},
    "v": {"s_entrar": 1.9, "s_salir": 1.6},
    "doblez": {"extendido": [60, 85], "doblado": [110, 90]},
    "tiempos_ms": {"pellizco": [66, 66], "puno": 200, "puno_espera": 500, "puno_tras_pellizco": 300,
                   "activar_min": 120, "activar_max": 1500, "activar_en_pausa": 250, "soltar_min": 100,
                   "doble_ventana": 700, "ignorar_tras_activar": 800, "agarre_3d": 150,
                   "mano_perdida": 150, "pausa_sin_mano_s": 10}
  },
  "zoom": {"paso_log": 0.08, "zona_muerta_log": 0.05, "max_muescas_s": 8, "invertir": false,
           "una_mano": false},
  "orbita": {"k_vol": 1.0, "k_mov": 0.8, "ganancia": 1.0, "max_px_cuadro": 60},
  "perfiles": {"automatico": true, "manual": "generico", "personalizados": {}},
  "atajos": {"pausar": "Ctrl+Alt+M", "salir": "Ctrl+Alt+X", "ventana": "Ctrl+Alt+O",
             "modo": "Ctrl+Alt+D", "dibujo_fino": "Ctrl+Alt+P"},
  "comodidad": {"sonidos": true, "aviso_cursor": true, "opacidad": 0.94,
                "descanso_min": 20, "aviso_brazo_alto": true},
  "ventana": {"x": null, "y": null, "mini": false},
  "calibracion": {"fecha": null, "luz": null, "tam_mano": null}
}
```

Las calibraciones guardadas sobrescriben los valores de `senas` y `zona`. El botón "Volver a los valores de fábrica" restaura todo menos `atajos` y `ventana`.

### 3.13 `registro.py`: registro de errores
- Carpeta: `%APPDATA%\Lycan Mouse Control\registros\`, archivo `registro.txt` con `RotatingFileHandler` (1 MB, 3 copias), UTF-8.
- Contenido: inicio (versión, Windows, DPI aplicado, monitores, cámara elegida, fps reales), cambios de estado, cambios de perfil, avisos (UIPI, cámara perdida, atajo ocupado), excepciones con traza completa y cada `soltar_todo()` con su motivo.
- Cada 60 s, una línea de rendimiento: fps medios, latencia media y p95, uso de CPU del proceso.
- Con `console=False` (ejecutable sin consola) `sys.stdout`/`sys.stderr` son `None`: se redirigen a un archivo nulo para que ningún `print` rompa el programa.
- Excepción no atrapada en cualquier hilo (`sys.excepthook`, `threading.excepthook`): `soltar_todo()`, registro, pausa y aviso "Algo falló y se pausó el control. Se soltaron todos los botones. Puede seguir trabajando." El programa no se cierra salvo que el error se repita 3 veces en 1 minuto.
- Menú "?" > "Abrir carpeta de registros" para enviarlos a soporte.
- Nunca se guardan imágenes de la cámara.

### 3.14 `perfiles.py`
Ver la sección 6.

### 3.15 `ui/`
Ver la sección 8.

---

## 4. Máquina de estados

### 4.1 Estados principales

| Estado | Qué significa | Color / texto en la ventana |
|---|---|---|
| `PAUSA` | No se envía nada a Windows. **Estado inicial** [ACORDADO] | Gris #8A8F98, "● PAUSADO" |
| `ACTIVO` | El índice mueve el puntero y las señas actúan | Verde #1FA34A, "● ACTIVO" |
| `ARRASTRANDO` | Hay un botón sostenido (izquierdo, medio o combinación) | Azul #2F6FEB, "● ARRASTRANDO" |
| `GIRANDO_3D` / `DESPLAZANDO` | Arrastre de cámara en curso | Naranja #FF9F1C, "● GIRANDO" / "● DESPLAZANDO" |
| `SIN_MANO` | Activo pero sin mano (todo suelto) | Rojo #D93636, "● SIN MANO" (la franja de ayuda dice "se soltaron todos los botones") |
| `BLOQUEADO` | Ventana de administrador o pantalla bloqueada | Rojo, con el aviso correspondiente |

El estado se comunica siempre con **texto + color + símbolo** (no solo color, por daltonismo).

### 4.2 Activar y pausar [ACORDADO: una vez = activar, dos veces seguidas = pausar, arranca en pausa]
Definiciones (tiempos de `config.senas.tiempos_ms`):
- **Seña completa**: `ACTIVAR` pasa de ausente a presente, se sostiene entre 120 y 1500 ms, y luego queda ausente al menos 100 ms. Si se sostiene más de 1500 ms **no cuenta** (evita disparos al acomodar la mano); la ventana muestra "Seña muy larga: hágala y suéltela".

Comportamiento:
- **En `PAUSA`**: cuando `ACTIVAR` lleva 250 ms sostenida, se pasa a `ACTIVO` **de inmediato** (no espera la ventana de doble seña), con sonido de activar y anillo de progreso que se llena en esos 250 ms. Durante los 800 ms siguientes a soltarla se ignora cualquier otra seña `ACTIVAR` (si el usuario hace dos por costumbre, no se vuelve a pausar).
- **En `ACTIVO`** (subestados `ESPERA` y `UN_TOQUE`):
  - `ESPERA` → al terminar una seña completa → `UN_TOQUE` (arranca el reloj de 700 ms).
  - `UN_TOQUE` → si aparece otra `ACTIVAR` que empiece antes de 700 ms y se sostenga 120 ms → **`PAUSA`** (no hace falta soltar la segunda).
  - `UN_TOQUE` → si pasan 700 ms → `ESPERA` (una seña sola en activo no hace nada).
- Mientras `ACTIVAR` está presente: **el puntero se congela** y se bloquean los clics (la seña no dibuja ni hace clic).
- Al entrar a `PAUSA` por cualquier vía: `soltar_todo()` **antes** de actualizar la interfaz, sonido de pausar.

Otras vías:
- Atajo `Ctrl+Alt+M`: alterna `PAUSA`/`ACTIVO` (al pausar, `soltar_todo()`).
- Pausa automática: sin ninguna mano durante `pausa_sin_mano_s` (10 s por defecto, ajustable 3-60).
- Pausa forzada: cambio de modo 2D/3D, cámara perdida, `BLOQUEADO`, error.

### 4.3 Mano perdida
- Mano principal ausente más de **150 ms** → `soltar_todo()`, quitar el ancla, reiniciar filtros, estado `SIN_MANO`, sonido grave si había un botón sostenido. Durante los primeros 100 ms la posición se predice con la velocidad.
- Al volver la mano: `ACTIVO` otra vez, con filtros reiniciados. **No** se vuelve a presionar nada de forma automática.
- En gestos de dos manos, perder cualquiera de las dos más de 150 ms termina el gesto (suelta el botón y las teclas).

### 4.4 Gestos de una mano (estado `ACTIVO`, mano principal)

**Clic izquierdo y arrastre** [ACORDADO: pellizco pulgar + índice; sostenido = arrastrar]
- `PELLIZCO` confirmado tras 66 ms → rebobinado y ancla (3.9) → `Bajar('izq')` en la posición anclada → estado `ARRASTRANDO`.
- Sale del pellizco (66 ms por encima de 0.42) → `Subir('izq')`. Si la mano no se alejó más de 14 px del ancla, el resultado es un clic limpio; si se alejó, fue un arrastre.
- Doble clic: dos pellizcos dentro del tiempo de doble clic de Windows (`GetDoubleClickTime()`, 500 ms por defecto). Como ambos caen en la misma posición anclada (±4 px), Windows los toma como doble clic por sí solo.

**Clic derecho** [ACORDADO: puño cerrado]
- `PUNO` sostenido **200 ms** → un clic derecho (`Bajar` + `Subir` en una sola llamada) en la posición congelada.
- Condiciones para no disparar por error:
  1. Debe venir desde un estado distinto de `PELLIZCO`: si hubo pellizco en los últimos 300 ms, el puño se ignora (al cerrar la mano se pasa por un "pellizco").
  2. Si hay un botón sostenido (arrastre), el puño no hace clic derecho: primero se suelta el arrastre.
  3. **En 3D** (o si hay otra mano a la vista): espera **250 ms** y exige que no aparezca una segunda mano en puño (eso sería orbitar) y que la mano no se mueva más de 0.02 de la imagen.
  4. Tras disparar, espera 500 ms y exige que la mano deje de estar en puño antes de volver a contar.
- Mientras el puño está presente, el puntero se congela.

**Mover**: con `APUNTAR`, `ABIERTA`, `NINGUNA`, `V` o durante el arrastre, el puntero sigue al índice. Se congela con `ACTIVAR`, `PUNO` y durante los gestos de dos manos.

### 4.5 Gestos de dos manos (2D y 3D)
Solo se activan cuando **ambas** manos muestran la misma seña de forma estable durante 100 ms (150 ms para el agarre 3D). Al empezar cualquier gesto de dos manos: si había un botón izquierdo sostenido, se suelta primero.

**Dos manos en pellizco: acercar/alejar o desplazar** [ACORDADO para acercar/alejar; desplazar es SUGERENCIA S5]
- Al confirmar las dos manos en `PELLIZCO`: se congela el puntero donde estaba, se guarda `d0` = distancia en la imagen entre los puntos medios de pellizco de cada mano (`(4+8)/2`) y `M0` = punto medio entre ellas.
- **Bloqueo por dominancia** (lo que pase primero decide y queda fijo hasta soltar):
  - `|ln(d/d0)| > 0.05` → **ZOOM**.
  - `|M - M0| > 0.03` (unidades de imagen) → **DESPLAZAR** (sujeto a la sugerencia S5; si el usuario no la aprueba, este camino se apaga y solo existe el zoom).
- ZOOM: `L = ln(d/d0)`. Cada vez que `L > +0.08` → `Rueda(+120)` (separar = acercar) y `d0 = d`; si `L < -0.08` → `Rueda(-120)`. Respeta el límite de muescas por segundo y la casilla "Invertir acercar/alejar" del perfil. El puntero queda congelado: el programa acerca hacia donde estaba apuntando.
- DESPLAZAR: aplica la combinación "desplazar" del perfil (6) en la posición actual del puntero y mueve el cursor según `ΔM` mapeado 1:1 a la pantalla (con el mismo One Euro).
- Termina cuando cualquiera de las dos manos sale del pellizco (66 ms) o se pierde (150 ms): `Subir` de botones y luego teclas.

**Variante de una mano para acercar/alejar** (desactivada por defecto, se prueba con el usuario): `PELLIZCO_CORAZON` sostenido 100 ms congela el puntero; mover la mano hacia arriba = acercar, hacia abajo = alejar; una muesca de 120 por cada 4 % de la altura de la imagen; máximo 8 por segundo. Se elige el corazón para no chocar con el clic (índice) ni con activar (índice + corazón sin pulgar). Se activa sola si la compuerta de rendimiento deja el 2D con una sola mano (3.3).

### 4.6 Solo 3D: girar y desplazar el modelo [ACORDADO: dos manos cerradas agarrando y girando = orbitar con el botón del medio; abrir las manos = soltar]

**Agarrar (empezar a girar)**
- Las dos manos en `PUNO`, estables 150 ms, con separación entre centros `s > 0.15` de la imagen (con los puños juntos MediaPipe las confunde).
- **Dos puños nunca producen clic derecho.**
- Se mueve el cursor al punto medio de las dos manos `M` llevado a pantalla con el mapeo de la zona, se espera 1 cuadro, y se aplica la combinación "orbitar" del perfil (en EDWIN CNC 3D el modelo gira alrededor del punto que queda bajo el puntero al presionar, es decir, "donde lo agarró").
- Protección contra doble clic del medio: no se vuelve a presionar el medio antes de 600 ms desde el último `MIDDLEUP`, salvo que el cursor esté a más de 10 px de esa posición (en EDWIN CNC 3D el doble clic del medio recentra la vista; en LibreCAD hace "ver todo").

**Girar (mientras se sostiene)**
- `Ci`, `Cd` = centros de palma (promedio de 0, 5, 9, 13, 17 en `img`) de la mano izquierda y derecha en pantalla. `M = (Ci+Cd)/2`, `v = Cd - Ci`, `θ = atan2(v.y, v.x)` desenvuelto. `M` filtrado con One Euro (mincutoff 1.0, beta 0.02), `θ` con mincutoff 0.8.
- Por cuadro: `dx = G·[k_vol·Δθ·(H_monitor/π) + k_mov·ΔM.x·W_monitor]`, `dy = G·k_mov·ΔM.y·H_monitor`, con `k_vol = 1.0`, `k_mov = 0.8`, `G` = ganancia del perfil. En EDWIN CNC 3D (`π/alto_vista` radianes por píxel) girar las manos 30° como un volante gira el modelo unos 30° sobre la vertical.
- Zona muerta: se ignoran `|Δθ| < 0.02 rad` y `|ΔM| < 0.003` por cuadro. Movimiento máximo 60 px por cuadro.
- Salto imposible (`|Δθ| > 0.6 rad` o `|ΔM| > 0.15`, MediaPipe confundió las manos): se descarta el cuadro.
- El movimiento se envía en absoluto como `GetCursorPos() + (dx, dy)` (3.11).
- Si el cursor llega a menos de 5 px del borde: **reagarre automático**: soltar, volver el cursor al punto donde se agarró, esperar 600 ms y volver a presionar (a más de 10 px del punto de soltar para que no sea doble clic).

**Soltar** [ACORDADO: abrir las manos]
- Cualquiera de las dos manos con 3 o más dedos extendidos durante 66 ms (2 cuadros), o una mano perdida 150 ms, o pausa → `Subir('medio')` (y `Subir('izq')` en FreeCAD estilo CAD) **y después** se sueltan las teclas.

**Desplazar el modelo (pan)** [ACORDADO: Shift + medio en SketchUp/Blender; la seña concreta no estaba fijada]
- Seña: **dos manos en pellizco moviéndose juntas sin cambiar la distancia** (el camino DESPLAZAR del bloqueo por dominancia de 4.5). Se eligió porque no choca con el clic derecho (un puño) ni con orbitar (dos puños). Ver S5.
- Combinación según el perfil: Shift abajo → esperar 20 ms → `MIDDLEDOWN` → movimientos → `MIDDLEUP` → esperar 15 ms → Shift arriba. **Shift baja antes del medio y sube después**, porque SketchUp, Blender y EDWIN CNC 3D deciden entre orbitar y desplazar al presionar el medio.
- Nunca se envía rueda mientras haya Shift o Ctrl sostenidos (en LibreCAD eso desplaza en vez de acercar): antes de un zoom se termina cualquier desplazamiento.

### 4.7 Tabla de transiciones que sueltan todo
`soltar_todo()` se llama, **siempre antes de actualizar la interfaz**, en: paso a `PAUSA` (seña doble, atajo, automática), mano perdida > 150 ms, fin de cualquier gesto de dos manos, cambio de modo 2D/3D, cambio de perfil en pleno arrastre (la ventana activa cambió de programa), cámara perdida, `BLOQUEADO`, atajo de salir, cierre de la ventana, `finally` del bucle del motor, `atexit`, manejadores de señales y excepciones no atrapadas.

---

## 5. Tabla final de señas

Medidas: `p` = pulgar-índice / palma; `pc` = pulgar-corazón / palma; `s` = separación índice-corazón / separación de sus nudillos; `a` = ángulo índice-corazón; doblez en grados (0 = recto). Todas con puntos en metros. Tiempos en ms medidos con reloj real.

### 5.1 Mouse Control 2D

| Seña (lo que hace el usuario) | Acción | Umbral inicial | Tiempo | Protección contra errores |
|---|---|---|---|---|
| Índice + corazón estirados y **pegados**, una vez (en pausa) | **Activar** | `s < 1.25` y `a < 10°` (salir `s > 1.50`, `a > 15°`); anular y meñique doblados (> 110°) | Sostener 250 ms | Distinta de la V por `s` y `a`; ignora otra seña 800 ms después |
| La misma seña **dos veces seguidas** (en activo) | **Pausar** + soltar todo | Igual | 1.ª: 120-1500 ms y soltar ≥ 100 ms; 2.ª dentro de 700 ms, sostenida 120 ms | Una sola en activo no hace nada; > 1500 ms no cuenta; mientras está puesta no se mueve ni hace clic |
| Índice estirado (o mano relajada) | **Mover el puntero** | Índice extendido (< 60°) | Continuo | One Euro (0.5 / 0.015 / 1.0), zona muerta 1.5 px |
| Pellizco pulgar + índice y soltar | **Clic izquierdo** | Entra `p < 0.28`, sale `p > 0.42`; doblez índice < 140°; `|8-C| > 0.55` | 66 ms para entrar y para salir | Rebobinado 100 ms + ancla; < 14 px = clic limpio |
| Pellizco sostenido y mover | **Arrastrar** (izquierdo sostenido) | Igual | Mientras dure | Mano perdida 150 ms → suelta |
| Dos pellizcos rápidos | **Doble clic** | Igual | Dentro de `GetDoubleClickTime()` (500 ms) | Mismo punto anclado |
| Puño cerrado | **Clic derecho** | 4 dedos > 110°, ≥ 3 puntas con `|punta-C| < 0.55`, pulgar `|4-C| < 0.75` | 200 ms; espera 500 ms y abrir antes de repetir | Ignorado si hubo pellizco en 300 ms o hay botón sostenido |
| Dos manos en pellizco, separarlas / juntarlas | **Acercar / alejar** (rueda) | Bloqueo si `|ln(d/d0)| > 0.05`; una muesca de 120 cada 0.08 en `ln` | Ambas manos estables 100 ms | Puntero congelado; máx. 8 muescas/s en LibreCAD; nunca con Shift/Ctrl abajo |
| Dos manos en pellizco moviéndose juntas | **Desplazar el dibujo** (S5) | Bloqueo si `|ΔM| > 0.03` | Ambas manos estables 100 ms | Combinación "desplazar" del perfil (botón del medio en 2D) |
| *(Variante, apagada)* Pellizco pulgar + corazón y subir/bajar la mano | Acercar / alejar con una mano | `pc < 0.28` y `p > 0.5` | 100 ms | 1 muesca por 4 % de alto, máx. 8/s |
| Sin mano | **Soltar todo** | — | 150 ms | Pausa automática a los 10 s |

### 5.2 Mouse Control 3D (todo lo de 2D más:)

| Seña | Acción | Umbral inicial | Tiempo | Protección |
|---|---|---|---|---|
| Dos manos cerradas "agarrando" y girando como un volante / subiendo y bajando | **Girar el modelo** (orbitar: combinación "orbitar" del perfil, normalmente botón del medio sostenido) | Dos `PUNO`, separación `> 0.15` de la imagen | Estables 150 ms | Nunca clic derecho con dos puños; zona muerta `Δθ < 0.02 rad`, `ΔM < 0.003`; máx. 60 px/cuadro; descarta saltos (sin reiniciar los filtros); un cuadro en que MediaPipe no ve una mano se salta sin tocar nada; reagarre en el borde; sin doble clic del medio (600 ms / 10 px) |
| Dos manos en pellizco moviéndose juntas | **Desplazar el modelo** (pan: Shift + medio en SketchUp, Blender y EDWIN CNC 3D) | Igual que en 2D | 100 ms | Shift baja antes del medio y sube después |
| Abrir las manos (≥ 3 dedos extendidos en cualquiera) | **Soltar** | Dedos < 60° | 66 ms | También al perder una mano 150 ms |
| Puño con **una** mano | Clic derecho | Igual que 2D | **250 ms** y sin segunda mano en puño | Evita abrir el menú contextual al empezar a girar |

### 5.3 Atajos de teclado globales

| Atajo | Acción | Nota |
|---|---|---|
| `Ctrl+Alt+M` | Pausar / activar | [ACORDADO]. Libre en el equipo y no produce ningún carácter con AltGr |
| `Ctrl+Alt+X` | Salir (suelta todo antes) | El usuario dijo "otro para salir". **No se usa `Ctrl+Alt+Q`**: en el teclado latinoamericano es AltGr+Q = "@" y le quitaría la arroba en todo Windows |
| `Ctrl+Alt+O` | Mostrar / ocultar la ventana | Se verifica con `ToUnicode` al registrar |
| `Ctrl+Alt+D` | Cambiar 2D / 3D | Se verifica con `ToUnicode`; si produce carácter, se usa `Ctrl+Alt+F9` |
| `Ctrl+Alt+P` | Modo dibujo fino (sí/no) | Libre y sin carácter |

Reglas: `MOD_CONTROL|MOD_ALT|MOD_NOREPEAT (0x0003|0x4000)`. Al registrar cada atajo se comprueba con `ToUnicode` que la combinación no produzca un carácter en el teclado actual; si lo produce, no se registra y se avisa. Si `RegisterHotKey` falla con el error 1409: "El atajo Ctrl+Alt+M ya lo usa otro programa. Puede cambiarlo en Opciones > Atajos." Todos son configurables.

---

## 6. Perfiles por programa

### 6.1 Detección
- Cada 1 s: `GetForegroundWindow` → `GetWindowThreadProcessId` → `OpenProcess(0x1000)` → `QueryFullProcessImageNameW`; se compara el nombre del .exe (sin distinguir mayúsculas, con comodines) con la lista.
- "Automático" por defecto; también selector manual. Al cambiar de perfil: si hay un arrastre, `soltar_todo()`; aviso corto "Perfil: SketchUp (3D)".
- Si la ventana activa es la propia, se conserva el perfil anterior.
- El perfil también propone el modo (2D o 3D), pero **no** lo cambia solo: muestra "Este programa es 3D. ¿Pasar a Mouse Control 3D? (Ctrl+Alt+D)". (Cambiar de modo solo por cambiar de ventana sería impredecible.)

### 6.2 Tabla de perfiles

| Perfil | .exe (a confirmar con el usuario) | Orbitar | Desplazar | Rueda | Ver todo | Notas |
|---|---|---|---|---|---|---|
| **EDWIN CNC 3D** (IngeTrazo) | `ingetrazo.exe` | Medio | Shift + medio (también cambia en vivo si se presiona Shift a mitad) | Admite fracciones (`delta/120`): zoom suave, mínimo 15 por evento a 30 Hz; zoom hacia el puntero | `Shift+Z` (o `F2`) | Pivote = punto bajo el puntero al presionar. Doble clic del medio = recentrar (evitar). Si hay ratón 3D en uso, ignora la rueda |
| **SketchUp** | `SketchUp.exe` | Medio | Shift + medio | ±120 | `Shift+Z` | Orbitar falla si el botón de la rueda está reasignado en el software del ratón |
| **FreeCAD** (estilo "CAD", el de fábrica) | `FreeCAD.exe`, `freecad.exe` | Medio + izquierdo (medio abajo, 20 ms, izquierdo abajo; al terminar izquierdo arriba antes que medio) | Medio | ±120 | `V`, `F` | El izquierdo puede seleccionar algo. En la ayuda se recomienda el estilo Blender |
| **FreeCAD (estilo Blender)** | (selección manual) | Medio | Shift + medio | ±120 | `V`, `F` | Recomendado |
| **Blender** | `blender.exe` | Medio | Shift + medio | ±120 | `Inicio` | Por defecto orbita y acerca al centro de la vista; sugerir "Zoom to Mouse Position" |
| **EDWIN CNC CAD-CAM / LibreCAD (2D)** | `EDWIN-CNC.exe`, `EDWIN-CNC*.exe`, `librecad.exe` | — (2D) | Medio (arranca tras moverse 7 px) | **Solo ±120 y máximo 8 por segundo**: cada evento hace un paso completo de ×1.137 sin importar el tamaño | Doble clic del medio | Ctrl+rueda desplaza vertical y Shift+rueda horizontal: nunca rueda con modificadores |
| **Genérico** | cualquier otro | — en 2D / medio en 3D | Medio en 2D / Shift + medio en 3D | ±120, máximo 10 por segundo | — | Por defecto |

Extras previstos (no obligatorios en v1.0, mismo formato): Fusion 360 (`Fusion360.exe`: medio = desplazar, Shift + medio = orbitar, doble clic medio = ajustar) y AutoCAD (`acad.exe`: medio = desplazar, Shift + medio = órbita, doble clic medio = extensión).

### 6.3 Formato de un perfil

```python
@dataclass(frozen=True)
class Perfil:
    clave: str                     # "edwin3d"
    nombre: str                    # "EDWIN CNC 3D"
    exes: tuple[str, ...]          # ("ingetrazo.exe",)
    modo_sugerido: str             # "3D"
    orbitar: Combinacion | None    # Combinacion(botones=("medio",), teclas=())
    desplazar: Combinacion         # Combinacion(botones=("medio",), teclas=("shift",))
    rueda_fraccion: bool           # True solo en EDWIN CNC 3D
    max_muescas_s: float           # 8 en LibreCAD
    ver_todo: tuple[str, ...] | str  # ("shift","z") o "doble_medio"
    ganancia_orbita: float = 1.0
    invertir_rueda: bool = False
```

`perfiles.py` traduce acciones abstractas (`EmpezarOrbita`, `EmpezarDesplazar`, `Zoom(muescas)`, `TerminarArrastre`) a acciones concretas con el orden y las esperas de la sección 4.6. El usuario puede agregar perfiles personalizados en `config.perfiles.personalizados` (con el mismo formato) y elegir un .exe desde Opciones.

"Ver todo" no tiene seña en la v1.0 (ver S6); queda en el perfil para la ayuda y para un botón de la ventana.

---

## 7. Seguridad: "soltar todo"

1. **Un solo responsable**: `salida.soltar_todo()` (3.11). Sabe qué presionó el programa (`set` con `Lock`) y además, por seguridad, envía la subida de Shift, Ctrl y Alt aunque no figuren.
2. **Cuándo**: todas las situaciones de 4.7, sin excepción.
3. **Orden**: primero botones del ratón, después teclas. En un desplazamiento: `MIDDLEUP` y luego Shift arriba.
4. **Cierre de golpe** (matar el proceso desde el Administrador de tareas): no se puede atrapar. Mitigación: EDWIN CNC 3D ya termina el arrastre si recibe un movimiento sin botones; la ayuda explica "Si algo quedó presionado, presione y suelte Shift y el botón de la rueda del ratón".
5. **Ventana propia**: la ventana de Lycan Mouse Control usa `WS_EX_NOACTIVATE` y antes de cada `Bajar` se revisa si el cursor está sobre ella; si lo está, el clic se ignora (9.2).
6. **UIPI y pantallas seguras**: detección y aviso (3.11); nunca se asume que un evento llegó.
7. **Rueda**: nunca con Shift o Ctrl sostenidos; el acumulador se vacía con `soltar_todo()`.
8. **No hay "toque de Midas"**: arranca en pausa, la seña de activar exige 250 ms sostenidos y anular y meñique doblados, el clic derecho exige 200 ms y venir desde mano no pellizcada, y la pausa automática corta el control si no hay manos.
9. **Asistente y `--simular`**: usan la salida simulada; nada llega a Windows.

---

## 8. Interfaz

### 8.1 Ventana principal (siempre visible)
- 336 x 330 px, abajo a la derecha con 16 px de margen (la posición se recuerda). `-topmost`, `-toolwindow`, `-alpha 0.94`, no redimensionable.
- `WS_EX_NOACTIVATE (0x08000000)` con `SetWindowLongW(GetParent(root.winfo_id()), GWL_EXSTYLE=-20, ...)`: hacer clic sobre ella **no** le quita el foco al CAD.
- De arriba abajo:
  1. Barra de estado (28 px): "● PAUSADO / ACTIVO / ARRASTRANDO / GIRANDO / SIN MANO", chip "2D"/"3D", nombre del perfil. Se puede arrastrar para mover la ventana.
  2. Video de 320x240 en espejo con: rectángulo de la zona activa (blanco; naranja cerca del borde), esqueleto de la mano (mano activa en el color del estado), punto en la punta del índice, línea pulgar-índice que se pone verde al cerrar el pellizco, anillo de progreso (`cv2.ellipse`) mientras se sostiene una seña, fps en pequeño.
  3. Franja de 44 px con el **nombre de la seña** en Segoe UI 20 negrita ("CLIC IZQUIERDO", "Sostenga…"). Si no se reconoce nada, la última seña queda en gris 800 ms (no parpadea).
  4. Botones: "⏸ Pausar", "2D/3D", "⚙", "?", "—" (modo mini de 160x120 sin botones; doble clic para volver).
- Borde de 3 px del color del estado (se ve con la vista periférica).
- Video: se reutiliza **un solo** `ImageTk.PhotoImage` con `paste()`; el dibujo se hace con cv2 en el hilo del motor sobre la imagen de 320x240; la interfaz se refresca con `after(66)` (unos 15 fps), suficiente y barato.
- Barra de diagnóstico (se muestra con un clic en los fps): seña detectada, `p`, `s`, `a`, doblez de cada dedo, estado de activación ("ESPERANDO SEGUNDA SEÑA"), latencia.
- Sin `-toolwindow` la ventana no aparece en la barra de tareas: se recupera con `Ctrl+Alt+O` y con un icono en la bandeja del sistema (si se implementa con `Shell_NotifyIconW`; si no, basta el atajo).

### 8.2 Indicador junto al cursor (opcional, activado por defecto)
Toplevel sin bordes, `-topmost`, `-transparentcolor '#010101'`, con `WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE` (los clics lo atraviesan). 24 px abajo a la derecha del cursor, muestra 1-2 palabras ("CLIC", "ARRASTRE", "GIRAR", "PAUSADO") 700 ms después de cada cambio. Texto en negrita sobre color sólido.

### 8.3 Asistente de primera vez y calibración
- Se abre si `primera_vez` es verdadero, y siempre desde "⚙ > Volver a practicar". Toplevel de 720x520. **Usa la salida simulada**: "No se preocupe: mientras practica, el ratón no hará nada."
- Barra "Paso N de M" y botón "?" en cada paso. Botones "Atrás", "Repetir", "Saltar esta seña", "Siguiente" (se habilita al lograr 3 de 3).
- Pasos: 1 Bienvenida → 2 Postura (codo apoyado, mano a 40-60 cm) → 3 Cámara y luz → 4 Mano principal (Derecha / Izquierda) → 5 Calibración → 6 Activar → 7 Mover (4 dianas) → 8 Clic (3 veces) y arrastrar una ficha → 9 Clic derecho → 10 Acercar/alejar → 11 Pausar. Si eligió 3D: + Girar, Desplazar, Soltar.
- Si pasan 15 s sin lograr la seña, aparece una pista concreta.
- **Calibración** (unos 40 s):
  1. Luz: brillo medio en gris; `< 60` → "Hay poca luz: encienda una lámpara frente a usted, no detrás."; `> 200` → "Hay demasiada luz detrás de usted (ventana)."
  2. Distancia: ancho de la mano (puntos 0 a 17) en la imagen entre 0.08 y 0.25; menos → "Acérquese un poco"; más → "Aléjese un poco".
  3. Zona cómoda: "Con el codo apoyado, mueva el dedo índice por todo el espacio que le resulte cómodo durante 5 segundos." Percentiles 5 y 95 de x e y + 5 % de margen; mínimo 30 % x 30 %.
  4. Posturas (2 s cada una, ~40 cuadros): "Abra la mano", "Cierre el puño", "Junte pulgar e índice", "Junte índice y corazón", "Haga la V". Para cada medida con postura "dentro" (mediana A) y "fuera" (mediana B): `entrar = A + 0.35·(B-A)`, `salir = A + 0.55·(B-A)`. Si las dos posturas se traslapan (diferencia de medianas < 3 desviaciones estándar de cualquiera), se pide repetir y se explica por qué. El valor calibrado no puede alejarse más de ±40 % del de fábrica.
- Al terminar: "Listo. Puede volver a este asistente desde ⚙ > Volver a practicar."

### 8.4 Opciones (5 pestañas, 520x460)
- **General**: modo 2D/3D, mano principal, cámara (índices 0-3 probados, con nombre si se obtiene), resolución (640x480 recomendada / 320x240 rápida), monitor de trabajo, "Abrir al encender el computador".
- **Puntero**: "Más estable ↔ Más rápido" (mapea `mincutoff` 0.3-1.5 y `beta` 0.005-0.05; sin hablar de Hz), tamaño de la zona 30-80 %, "Calibrar zona", modo absoluto/relativo, modo dibujo fino.
- **Señas**: por cada seña, barra en vivo con el valor medido y las dos marcas de umbral + deslizador "Sensibilidad" (estilo Google Project Gameface); tiempo para confirmar 150-600 ms; ventana de la doble seña 400-1200 ms (700 por defecto); "Invertir acercar/alejar"; variante de zoom con una mano (sí/no).
- **Comodidad**: modo codo apoyado, pausa sin mano (3-60 s), recordatorio de descanso (10-60 min o nunca; por defecto 20), sonidos, aviso junto al puntero, opacidad 60-100 %.
- **Atajos**: un campo por atajo que captura la combinación + "Restablecer".
- Abajo: "Volver a practicar señas", "Volver a los valores de fábrica", "Guardar", "Cancelar". Los cambios se ven en vivo y "Cancelar" los revierte.

### 8.5 Ayuda "?"
- En cada pantalla, un globo con 2-3 líneas: qué hace, error común y cómo saltar.
- En la ventana principal: chuleta de señas del modo actual (Seña → Acción) con dibujos de 48 px generados desde manos sintéticas (sin archivos externos).
- Temas fijos: postura y cansancio; poca luz; "la seña de activar sostenida más de 1.5 s no cuenta"; programas abiertos como administrador; cómo dejar FreeCAD en estilo Blender; "si algo quedó presionado".

### 8.6 Sonidos (activados por defecto, en hilo aparte)
Activar 880 Hz 60 ms; pausar 440 Hz 60 ms + 330 Hz 60 ms; clic: tic corto (`.wav` con `PlaySound SND_ASYNC`, o 1200 Hz 15 ms); mano perdida con botón sostenido 300 Hz 120 ms.

### 8.7 Cansancio
- Zona activa pequeña con ganancia: basta mover la muñeca 10-15 cm para cruzar la pantalla.
- Si la muñeca pasa más de 60 s en el 30 % superior de la imagen, una vez por sesión: "Tiene el brazo muy levantado. Apoye el codo: se cansará menos."
- Cada 20 min de uso activo acumulado: "Lleva 20 minutos usando las manos. Baje los brazos y descanse un minuto." (no bloquea, se cierra solo a los 10 s).
- La pausa se explica como "levantar el ratón para reacomodarlo".

### 8.8 Textos (todos en `ui/textos.py`, diccionario `TXT`)
Ejemplos obligatorios:
- "PAUSADO — haga la seña de activar (índice y corazón juntos) para empezar"
- "ACTIVO — mueva el dedo índice"
- "SIN MANO — se soltaron todos los botones"
- "Modo 3D: dos manos cerradas para girar el modelo."
- "Girar el modelo: cierre las dos manos como si agarrara un volante y gírelas. Abra las manos para soltar."
- "Mover el dibujo: haga pellizco con las dos manos y muévalas juntas."
- "Acercar o alejar: con pellizco en las dos manos, sepárelas o júntelas."
- "Junte el dedo índice y el corazón, estirados y pegados, como diciendo «dos». Sosténgalos medio segundo."
- "Se cerrará Lycan Mouse Control y el ratón volverá a funcionar normal."
- "Su equipo va lento: cierre otros programas o baje la resolución." (fps < 20 durante 5 s)

Ningún texto usa palabras como "landmark", "threshold", "frame" o "Hz".

---

## 9. Comportamientos de Windows que hay que respetar

1. **DPI**: `SetProcessDpiAwarenessContext(-4)` antes de todo (3.1). Sin esto, con escala del 125-150 % el puntero no llega a los bordes o cae corrido.
2. **Ventana propia**: `WS_EX_NOACTIVATE`; los `Bajar` sobre su rectángulo (`GetWindowRect`) se ignoran y el aviso dice "El puntero está sobre Lycan Mouse Control". Opción: moverla sola a la esquina contraria.
3. **Varias pantallas**: escritorio virtual con origen posiblemente negativo; mapeo a un solo monitor; relectura en `WM_DISPLAYCHANGE`.
4. **UIPI**: detección, aviso y opción de reiniciar como administrador.
5. **Botones invertidos para zurdos**: `SM_SWAPBUTTON`.
6. **Doble clic**: `GetDoubleClickTime()` y `SM_CXDOUBLECLK/SM_CYDOUBLECLK` para el clic y para evitar el doble clic accidental del medio.
7. **AltGr**: ningún atajo que produzca un carácter (`ToUnicode`).

---

## 10. Rendimiento

| Medida | Objetivo | Mínimo aceptable | Cómo se mide |
|---|---|---|---|
| Cuadros procesados por segundo, 2D, una mano | **≥ 25 fps** | 20 fps (aviso al usuario) | `motor` cuenta cuadros procesados/s; media de 60 s con la HP TrueVision y luz normal |
| Cuadros por segundo, 3D, dos manos | **≥ 25 fps** | 20 fps | Igual |
| Latencia mano → puntero | ≤ 120 ms media | ≤ 170 ms | `t_envio - t_captura` (sin contar la pantalla) |
| CPU del proceso | ≤ 60 % de un portátil de 4 hilos | ≤ 75 % | `psutil` o `GetProcessTimes` en la prueba de rendimiento |
| Memoria | ≤ 400 MB | ≤ 500 MB, estable en 30 min | Prueba de 30 min sin crecimiento > 30 MB |
| `SendInput` | < 0.2 ms por llamada | — | Medido: 48-99 µs |
| Arranque hasta "PAUSADO" con video | ≤ 6 s | ≤ 10 s | Desde el .exe instalado |

Medidas para lograrlo:
- `model_complexity=0`, `static_image_mode=False` (el seguimiento evita correr el detector de palma en cada cuadro), imagen de 640x360/480.
- Cámara en hilo propio con `BUFFERSIZE=1` y solo el último cuadro.
- La interfaz pinta a ~15 fps y reutiliza un `PhotoImage`; el dibujo sobre el video se hace en la imagen de 320x240.
- Nada de `print` ni de registro por cuadro (el registro de rendimiento es cada 60 s).
- Compuerta 2D (3.3): si con `max_num_hands=2` no se llega a 25 fps, el 2D usa 1 mano.
- Aviso de poca luz si los fps de la cámara bajan de 20 (la HP TrueVision baja a ~15 fps en interiores oscuros).

---

## 11. Plan de pruebas automáticas (pytest)

Regla del usuario: **probar todas las reglas** (datos faltantes, errores, uso real), no solo el camino feliz. Comando: `py -3.10 -m pytest -q pruebas` (el workflow usa la misma carpeta). Ninguna prueba automática abre la cámara ni mueve el ratón real; las que sí lo hacen están marcadas `@pytest.mark.manual` y se excluyen por defecto.

### 11.1 Generador de manos sintéticas (`pruebas/sintetico/mano_sintetica.py`)
- Modelo cinemático simple de la mano derecha en metros: muñeca en el origen, 5 cadenas de dedos con longitudes de segmento típicas (palma ~0.085 m), ángulos de flexión por articulación (MCP, PIP, DIP) y de separación lateral por dedo.
- Posturas predefinidas: `abierta`, `puno`, `apuntar`, `pellizco` (punta 4 sobre punta 8), `pellizco_corazon`, `juntos` (índice + corazón extendidos, separación ~0), `v` (separación ~25°), `relajada`, `intermedia(a, b, t)` (interpolación entre dos posturas para simular transiciones).
- Variaciones: escala 0.7-1.3 (manos pequeñas y grandes), rotación 3D aleatoria (±40° en cada eje, palma hacia la cámara), espejo (mano izquierda = reflejo en x), ruido gaussiano por punto (σ = 1, 2 y 4 mm), punto faltante simulado (desplazamiento grande en un dedo).
- Proyección a coordenadas de imagen (`img`) con una cámara pinhole de 640x480 a distancias de 30, 50 y 90 cm, para probar el puntero y las distancias entre manos.
- Semilla fija (`numpy.random.default_rng(1234)`) para que las pruebas sean repetibles.

### 11.2 Pruebas de geometría y clasificador
| Prueba | Criterio |
|---|---|
| `escala_palma` igual en la misma mano a 30, 50 y 90 cm | Diferencia < 2 % |
| `doblez` de un dedo recto y uno cerrado bajo 200 rotaciones aleatorias | Recto < 40°, cerrado > 150° |
| Cada postura × 200 variaciones (escala, rotación, ruido 2 mm, espejo) | Clasificación correcta ≥ 98 % (con ruido 4 mm ≥ 90 %) |
| `juntos` contra `v` | 0 confusiones con ruido ≤ 2 mm |
| `puno` nunca clasificado como `pellizco` | 0 en 1000 variaciones |
| Transición `abierta → puno` interpolada en 10 pasos | Ninguna salida `PELLIZCO` sostenida ≥ 66 ms a 30 fps |
| Pellizco en el borde (p oscila 0.27-0.43 con ruido) | Histéresis: como máximo 1 cambio de estado |
| Mano cerca y lejos con el mismo umbral | Mismo resultado |
| Datos raros: puntos `NaN`, todos iguales, palma de tamaño 0 | No lanza excepción; devuelve `NINGUNA` |
| Umbrales calibrados fuera de ±40 % | Se recortan al límite |

### 11.3 Pruebas de filtros
- `OneEuro`: con ruido σ = 6 px quieto, temblor < 2 px; retraso a 300 px/s < 60 ms; `dt` variable (15-30 fps) sin saltos; `reset()` evita el latigazo.
- `Histeresis` y `Antirrebote`: tablas de valores y tiempos, incluida una caída de fps a la mitad a mitad de una seña.
- Zona muerta: movimientos < 1.5 px no producen `Mover`.

### 11.4 Secuencias de cuadros para la máquina de estados
Cada prueba arma una lista de `(t, manos)` con el generador y la pasa por `estados` + `perfiles` + **salida simulada**. Se verifican las acciones y, al final, que no quede nada presionado.

| # | Caso | Resultado esperado |
|---|---|---|
| E1 | Arranque sin señas | Estado `PAUSA`, ninguna acción |
| E2 | En pausa: `juntos` 300 ms | `ACTIVO` en ~250 ms; sin clics |
| E3 | En pausa: doble seña por costumbre | Queda `ACTIVO` (la 2.ª se ignora 800 ms) |
| E4 | Activo: seña completa + 2.ª a 500 ms | `PAUSA` y `SoltarTodo` |
| E5 | Activo: dos señas separadas 1000 ms | Sigue `ACTIVO` |
| E6 | Activo: seña sostenida 2 s | No cuenta; sigue `ACTIVO`; aviso "Seña muy larga" |
| E7 | Activo: seña de 80 ms (muy corta) | No cuenta |
| E8 | Mientras `juntos` está puesta | Ningún `Mover` ni clic |
| E9 | Pellizco quieto | `Bajar('izq')` y `Subir('izq')` en la posición rebobinada; ningún `Mover` intermedio |
| E10 | Pellizco con corrimiento de 25 px en los 100 ms previos | El clic cae en la posición de antes del corrimiento (±2 px) |
| E11 | Pellizco y mover 200 px | Arrastre: `Bajar`, varios `Mover`, `Subir` |
| E12 | **Mano desaparece a mitad de arrastre** | `Subir('izq')` a los ≤ 150 ms; estado `SIN_MANO` |
| E13 | **Transición pellizco → puño** | Ningún clic derecho; si hubo clic izquierdo, termina con `Subir` |
| E14 | Abierta → puño 250 ms | Un clic derecho; no repite mientras siga el puño |
| E15 | Puño de 150 ms | Nada |
| E16 | 3D: puño con una mano y a los 150 ms aparece la otra en puño | Ningún clic derecho; empieza la órbita |
| E17 | 3D: dos puños girando 30° como volante | `Bajar('medio')`, movimientos con dx positivo ≈ `30/180·H`, ningún dy grande; `Subir('medio')` al abrir |
| E18 | 3D: **perder una mano en pleno giro** | `Subir('medio')` en ≤ 150 ms |
| E19 | 3D: soltar y volver a agarrar a los 300 ms en el mismo punto | No hay dos `MIDDLEDOWN` a menos de 600 ms y 10 px |
| E20 | 3D: desplazar en SketchUp | Orden exacto: Shift abajo, medio abajo, movimientos, medio arriba, Shift arriba |
| E21 | **Salir con Ctrl+Alt+X en pleno giro 3D / desplazamiento** | `SoltarTodo` suelta medio y Shift antes de cerrar |
| E22 | Dos manos que **se cruzan** (intercambian x y etiqueta) | Sin saltos de órbita (cuadro descartado); sin clic derecho |
| E23 | Zoom dos manos: separar 30 % | `Rueda(+120)` × 3 (ln 1.3 = 0.26 → 3 pasos de 0.08); puntero sin moverse |
| E24 | Zoom en LibreCAD con separación muy rápida | Nunca más de 8 muescas por segundo; todas de ±120 exactos |
| E25 | Zoom en EDWIN CNC 3D | Se permiten deltas fraccionarios ≥ 15 |
| E26 | Zoom con temblor (±3 %) | Ninguna muesca (zona muerta 5 %) |
| E27 | Rueda pedida mientras hay Shift abajo | Primero se termina el desplazamiento; nunca `Rueda` con Shift/Ctrl abajo |
| E28 | "Rascarse la cara": mano entra rápido, puño parcial, sale | Ningún clic (en pausa y en activo) |
| E29 | 10 s sin manos | `PAUSA` automática |
| E30 | Cambio de perfil en pleno arrastre | `SoltarTodo` |
| E31 | Cambio de modo 2D↔3D | `SoltarTodo` y `PAUSA` |
| E32 | fps cae de 30 a 12 durante un pellizco | Mismo comportamiento (tiempos en ms) |
| E33 | Cursor sobre la ventana propia + pellizco | No se envía `Bajar` |
| E34 | Ventana activa elevada | Estado `BLOQUEADO`, sin acciones, aviso |
| E35 | `SendInput` falla (simulado) | Pausa y aviso; el programa sigue |
| E36 | Excepción en el clasificador a mitad de arrastre | `SoltarTodo` desde el `except`; pausa |

Invariantes que se revisan al final de **todas** las secuencias: cada `Bajar` tiene su `Subir`; ninguna tecla queda abajo; no hay `Bajar` repetido sin `Subir`; Shift nunca sube antes que el medio en un desplazamiento; ninguna `Rueda` con Shift/Ctrl abajo.

### 11.5 Pruebas de salida y Windows (sin mover el ratón)
- Barrido de la fórmula de coordenadas: para todo x en `[0, vw)`, `vx + (nx*vw)//65536 == x`, con pantallas de 1366, 1920, 2560 y 3840 y con origen negativo (-1920).
- `soltar_todo()` con la salida simulada en todos los estados.
- Construcción de estructuras `INPUT` (tamaño 40, banderas correctas) sin llamar a `SendInput` (se reemplaza `_send`).
- Atajos: `ToUnicode` marca `Ctrl+Alt+Q` como carácter en el teclado latinoamericano (si está instalado; si no, se omite); error 1409 produce el texto correcto.
- Configuración: archivo ausente, vacío, JSON inválido, tipos equivocados, valores fuera de rango, versión futura → valores por defecto y aviso; escritura atómica.
- Perfiles: cada nombre de .exe resuelve al perfil correcto (mayúsculas, rutas largas, comodines).
- Registro: crea la carpeta, rota a 1 MB, funciona con `sys.stdout = None`.

### 11.6 Pruebas manuales en el portátil (lista de verificación antes de entregar)
Marcadas `manual`; se hacen con la cámara real y el ratón real, y se anota el resultado:
1. Mano quieta 10 s: el puntero no se mueve más de 2 px.
2. Trazo lento y rápido en Paint y en EDWIN CNC CAD-CAM.
3. Clic, doble clic y arrastre de una entidad en EDWIN CNC CAD-CAM; enganche de un punto con el zoom.
4. Clic derecho abre el menú contextual; no se abre al girar en 3D.
5. Zoom con dos manos en EDWIN CNC CAD-CAM (sin dispararse) y en EDWIN CNC 3D (suave).
6. Girar un cubo 90° en EDWIN CNC 3D; desplazar con Shift + medio; soltar abriendo las manos.
7. Lo mismo en SketchUp, FreeCAD (estilo CAD y estilo Blender) y Blender si están instalados.
8. Sacar la mano en pleno arrastre: nada queda presionado.
9. `Ctrl+Alt+M` y `Ctrl+Alt+X` con el CAD en primer plano y en pleno giro.
10. Poca luz (lámpara apagada) y contraluz (ventana detrás): avisos correctos.
11. Escala de pantalla 125 % y 150 %: el puntero llega a las cuatro esquinas.
12. Con un segundo monitor o proyector, si hay uno disponible.
13. Un programa abierto como administrador: aparece el aviso.
14. 30 min de uso: memoria estable, fps ≥ 25 (registro de rendimiento).
15. Grabación: guardar una sesión real en `.npz` (puntos 21x3 por cuadro + etiqueta de la seña que se pidió) con `herramientas/grabar.py`, para convertirla en prueba de regresión y ajustar los umbrales de fábrica con datos de la HP TrueVision.

---

## 12. Empaquetado y distribución

Archivos ya preparados y probados en parte (`C:\dev\lycan-mouse-control\empaquetado\`):

| Archivo | Estado |
|---|---|
| `lycan-mouse-control.spec` | Probado: compila; `--check` sale con 0; carpeta de ~211 MB (con Pillow, ~11 MB), instalador estimado ~56-60 MB |
| `rthook_sin_matplotlib.py` | Probado: evita empaquetar matplotlib (~40 MB) que mediapipe importa en `drawing_utils` |
| `version_info.txt` | Datos del .exe en español de Colombia (0x240A) |
| `lycan-mouse-control.iss` | Escrito, sin compilar (Inno Setup no está instalado en el portátil) |
| `lycan-mouse-windows.yml` | Copia del workflow real, que vive en `.github/workflows/windows.yml` (deben quedar iguales) |

### 12.1 Entorno de compilación (siempre limpio, versiones fijas)
```
py -3.10 -m venv .venv-build
.venv-build\Scripts\pip install mediapipe==0.10.14 numpy==2.2.6 pyinstaller==6.22.3
.venv-build\Scripts\pip uninstall -y opencv-contrib-python
.venv-build\Scripts\pip install opencv-python-headless==4.10.0.84
.venv-build\Scripts\pyinstaller empaquetado\lycan-mouse-control.spec --noconfirm
```
El Python del portátil tiene mezclados `opencv-contrib-python 5.0.0.93` y `opencv-python-headless 4.10.0.84`: **no** se compila desde ahí.

### 12.2 Decisiones
- Modo carpeta (one-dir), sin UPX, sin consola, arrancador de PyInstaller compilado desde el código fuente en el workflow (menos falsos positivos de antivirus).
- Se incluyen solo los modelos de mano y palma de mediapipe (`collect_data_files('mediapipe', includes=['modules/hand_landmark/*','modules/palm_detection/*'])`). Se excluyen jax, jaxlib, matplotlib, sounddevice y scipy. **No** se excluye `mediapipe.tasks`.
- Se quita `opencv_videoio_ffmpeg*.dll` (la cámara usa DirectShow/MSMF).
- Instalador Inno Setup: `PrivilegesRequired=lowest` (en `AppData\Local\Programs`, sin administrador), español, `x64compatible`, `lzma2` sólido, icono en el escritorio opcional, "Abrir al encender el computador" desmarcado (`HKCU\...\Run` con `--minimizado`), `CloseApplications=force`, AppId fijo `{05FDCE37-EFA7-4182-B127-C765607E7C41}` (no cambiar nunca).
- **Ajuste pendiente del `.iss`**: hoy borra `{localappdata}\Lycan Mouse Control` al desinstalar, pero la configuración y los registros van en `%APPDATA%` (`{userappdata}\Lycan Mouse Control`). Hay que cambiar esa línea y **preguntar** al desinstalar si se borra la configuración (por defecto se conserva).
- Workflow: instala Inno Setup con `choco install innosetup` si no está (windows-2025 ya no lo garantiza), corre `pytest -q pruebas`, compila, revisa que estén los `.binarypb`/`.tflite` y que no estén jax ni matplotlib, prueba el .exe con `Start-Process ... --check -Wait -PassThru`, arma instalador + ZIP portable con LEEME y los sube como artefactos.
- SmartScreen: sin firma aparecerá "Windows protegió su PC"; el LEEME explica "Más información → Ejecutar de todas formas". Revisar en VirusTotal antes de cada versión. Firma de código: se evalúa después.

---

## 13. Dependencias

### 13.1 Ejecución (`requirements.txt`)
```
mediapipe==0.10.14
numpy==2.2.6
opencv-python-headless==4.10.0.84
Pillow
```
(tkinter, ctypes, winsound vienen con Python.) **No** se usan pynput ni pyautogui.

### 13.2 Desarrollo (`requirements-dev.txt`)
```
-r requirements.txt
pytest
pyinstaller==6.22.3
psutil          # solo para la prueba de rendimiento
```

---

## 14. Orden de construcción sugerido

1. `geometria.py`, `filtros.py`, `senas.py` + generador sintético + pruebas 11.2 y 11.3.
2. `acciones.py`, `salida/simulada.py`, `estados.py`, `perfiles.py` + secuencias 11.4.
3. `salida/windows.py` (desde `referencia\winput.py`), `sistema/*` + pruebas 11.5.
4. `captura.py`, `detector.py`, `seguidor.py`, `mapeo.py`, `puntero.py` (desde `referencia\puntero_ref.py`), `motor.py`; medición de fps (compuerta 2D de 3.3).
5. `ui/*` (ventana, indicador, opciones, ayuda), `config.py`, `registro.py`, `app.py`.
6. Asistente y calibración.
7. Grabación de sesiones reales y ajuste de umbrales de fábrica.
8. Empaquetado local (.spec + .iss) y prueba del instalador.

---

## 15. Criterios de "terminado"

La v1.0 está terminada cuando **todo** lo siguiente se cumple:

**Funciones**
- [ ] Arranca en `PAUSA`; una seña de índice + corazón juntos activa; dos seguidas pausan; `Ctrl+Alt+M` alterna; `Ctrl+Alt+X` sale.
- [ ] El índice mueve el puntero en modo absoluto, con zona activa visible y en espejo; mano quieta = puntero quieto (≤ 2 px en 10 s).
- [ ] Pellizco = clic izquierdo limpio (sin corrimiento visible); pellizco sostenido = arrastre; dos pellizcos = doble clic.
- [ ] Puño = clic derecho, sin disparos al pasar de pellizco a puño.
- [ ] Dos manos en pellizco acercan y alejan en EDWIN CNC CAD-CAM y EDWIN CNC 3D sin descontrolarse.
- [ ] 3D: dos puños orbitan en EDWIN CNC 3D y SketchUp; abrir las manos suelta; desplazar funciona con Shift + medio en el orden correcto.
- [ ] Perfiles automáticos para EDWIN CNC 3D, SketchUp, FreeCAD, Blender, EDWIN CNC CAD-CAM/LibreCAD y Genérico, con selección manual.
- [ ] Asistente de primera vez y calibración funcionando, en modo ensayo.
- [ ] Opciones con barras en vivo; configuración en `%APPDATA%\Lycan Mouse Control\config.json` que sobrevive a archivos dañados.

**Seguridad**
- [ ] Las 36 secuencias de 11.4 pasan, con sus invariantes (nada queda presionado).
- [ ] Prueba manual: sacar la mano en pleno arrastre y en pleno giro, salir con el atajo en pleno giro, y matar el motor con un error forzado: nada queda presionado.
- [ ] Aviso correcto con una ventana de administrador.
- [ ] Ningún atajo quita un carácter del teclado latinoamericano.

**Calidad**
- [ ] `py -3.10 -m pytest -q pruebas` pasa completo, sin pruebas que dependan de la cámara o del ratón real.
- [ ] Clasificador ≥ 98 % correcto en manos sintéticas con ruido de 2 mm (11.2).
- [ ] Rendimiento en el portátil: ≥ 25 fps en 2D y en 3D (o compuerta 2D aplicada y documentada), latencia media ≤ 120 ms, memoria estable en 30 min.
- [ ] Todo texto visible en español de Colombia, con "usted" y sin jerga (revisión de `ui/textos.py`).
- [ ] El registro de errores guarda inicio, cambios de estado, avisos y excepciones; nunca imágenes.

**Entrega**
- [ ] `pyinstaller` con el `.spec` en entorno limpio; `LycanMouseControl.exe --check` sale con 0.
- [ ] Instalador Inno Setup compilado en el portátil, instala sin administrador, abre, desinstala (pregunta por la configuración) y actualiza encima de una versión anterior.
- [ ] `.iss` ajustado a `{userappdata}`.
- [ ] Lista de pruebas manuales 11.6 hecha y anotada.
- [ ] Nada publicado, sin repositorio y sin push (fase siguiente).

---

## 16. Sugerencias de la investigación (no aplicadas, para decidir con el usuario)

Las señas acordadas se respetan tal cual. Estas son propuestas aparte:

- **S1. Atajo de salir.** El usuario dio `Ctrl+Alt+M` como ejemplo para pausar y pidió "otro para salir". La investigación descarta `Ctrl+Alt+Q` porque en el teclado latinoamericano es AltGr+Q = "@" y bloquearía la arroba en todo Windows. Se usa `Ctrl+Alt+X` (configurable). Confirmar con el usuario.
- **S2. Punto que mueve el puntero.** Se usa la punta del índice [ACORDADO] con rebobinado y ancla al pellizcar. Si en pruebas reales el clic sigue corriéndose, la investigación propone apuntar con el nudillo del índice (punto 5) o con el promedio de 5 y 8, que se mueve mucho menos al pellizcar (al usuario se le seguiría diciendo "mueva con el dedo índice"). Queda como opción oculta en `config` para probar.
- **S3. Clic con el pulgar contra la articulación media del índice** (como `slastra/pointer`) en vez de punta con punta: casi no mueve el índice al hacer clic. No se aplica: el usuario acordó pellizco pulgar + índice.
- **S4. Clic por espera ("dwell")**: dejar el puntero quieto 800 ms para hacer clic es el método más preciso y que menos cansa según Dube et al. 2022. Podría ser una opción de accesibilidad futura, no un reemplazo.
- **S5. Seña de desplazar.** El usuario acordó qué hace (pan con Shift + medio) pero no la seña. Se propone "dos manos en pellizco moviéndose juntas" porque no choca con el clic derecho ni con orbitar. La alternativa de la investigación ("un puño + la otra mano abierta") choca con el clic derecho y se descarta. Confirmar con el usuario.
- **S6. "Ver todo"** (Shift+Z, Inicio o doble clic del medio según el programa): sin seña en la v1.0; se propone un botón en la ventana o una seña futura.
- **S7. Variante de zoom con una mano.** Se definió con pellizco pulgar + corazón, apagada por defecto, porque puede cansar. La otra opción investigada es la "V" (índice y corazón separados) subiendo y bajando, como `slastra/pointer`; se descartó por parecerse a la seña de activar. Probar ambas con el usuario.
- **S8. Modo relativo con embrague** para trabajar con el codo apoyado y para pantallas grandes: incluido como opción apagada; podría ser el modo por defecto en 3D si las pruebas lo favorecen.
- **S9. Pausa automática sin manos.** La investigación propone entre 3 s y 20 s; se eligió 10 s (configurable). Ajustar con el uso real.
- **S10. Ejecutar como administrador** para manejar programas abiertos así (UIPI). La alternativa `uiAccess=true` exige firma digital e instalación en Program Files; no es viable sin certificado.
- **S11. Firma de código** (Azure Trusted Signing o certificado OV) para quitar el aviso de SmartScreen y reducir falsos positivos de antivirus. Fase posterior.
- **S12. Interfaz en PySide6** (la que usa EDWIN CNC 3D) si más adelante se quiere una superposición más elaborada; para la v1.0 se usa tkinter (ya instalado y el ejecutable pesa 60-100 MB menos).

---

## 17. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Umbrales sacados de valores típicos (Meta, Ultraleap, `slastra/pointer`, Casiez), no medidos con la HP TrueVision | Calibración por usuario, barras en vivo, grabación de sesiones reales (11.6-15) |
| Precisión de 1 px imposible en modo absoluto (~384 px de cámara para 1366 px de pantalla) | Zoom del CAD, enganche (snap), modo dibujo fino, modo relativo; no prometer reemplazar el ratón |
| Poca luz: la cámara baja a ~15 fps y MediaPipe pierde la mano | Aviso de luz, tiempos en ms, calibración de luz |
| Dos puños juntos: MediaPipe fusiona o confunde las manos | Separación mínima 0.15, seguidor propio, descarte de saltos, soltar en 150 ms |
| Cansancio del brazo | Codo apoyado, zona pequeña, recordatorios, pausa como embrague |
| `max_num_hands=2` en 2D puede bajar de 25 fps | Compuerta 2D (3.3) |
| Nombres de los .exe sin verificar (salvo `ingetrazo.exe` y `EDWIN-CNC.exe`, sacados del código) | Confirmar con el usuario; selector manual y perfiles personalizados |
| Varios monitores y escala 125/150 % sin probar en el equipo (solo hay 1366x768 al 100 %) | Fórmula y DPI según documentación; pruebas de barrido con tamaños simulados; prueba manual cuando haya otro monitor |
| UIPI falla en silencio | Detección de ventana elevada y aviso |
| Antivirus marcan ejecutables de PyInstaller que inyectan entrada | Arrancador propio, sin UPX, VirusTotal, envío a Microsoft, firma futura |
| mediapipe 0.10.14 compilado para numpy 1.x (funciona con 2.2.6) | Versiones fijas |

---

## 18. Referencias

- Código de referencia probado en el portátil: `C:\dev\lycan-mouse-control\referencia\winput.py` (SendInput, DPI, monitores, atajos, elevación), `referencia\test_winput.py`, `referencia\test_tk.py`, `referencia\puntero_ref.py` (One Euro, mapeo, puntero con rebobinado, pellizco con histéresis).
- EDWIN CNC 3D: `C:\dev\edwin-cnc-3d\repo\views\viewport.py` (medio = orbitar, Shift + medio = desplazar, rueda = zoom con `delta/120`, doble clic medio = recentrar), `core\camera.py`, `installer\edwin-cnc-3d.iss` (`ingetrazo.exe`).
- EDWIN CNC CAD-CAM: `C:\dev\edwin-cnc-cad-cam\librecad\src\ui\qg_graphicview.cpp` (rueda por signo, factor 1.137, medio = desplazar, doble clic medio = ver todo), `rs_actionzoompan.cpp` (umbral 7 px), `src.pro` (`EDWIN-CNC`).
- MediaPipe Hands (etiqueta de mano con imagen en espejo, puntos de imagen y en metros); 1€ Filter (Casiez 2012); Meta Interaction SDK (histéresis de pellizco); Ultraleap TouchFree; Google Project Gameface (calibración por seña); Consumed Endurance (CHI 2014); Qiu et al. 2026 (efecto Heisenberg); Dube et al. 2022; Microsoft Learn (SendInput, MOUSEINPUT, RegisterHotKey, SetProcessDpiAwarenessContext, UIPI); `slastra/pointer`.
