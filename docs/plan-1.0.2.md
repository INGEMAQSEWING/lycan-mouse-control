# Plan de la versión 1.0.2 de Lycan Mouse Control

Fecha: 2026-11-15. Parte de la 1.0.1 (commit 20abbea).
Este plan junta lo que pidió el usuario, el informe de investigación y el mapa del código.
Las decisiones quedan anotadas en `docs/decisiones.md`.

Convenciones de este documento:
- "palma" = tamaño de la mano que ya usa `senas.py` (distancia muñeca–nudillos). Las distancias entre puntas van divididas por la palma, así valen igual cerca o lejos de la cámara.
- "anchos" = fracción del ancho de la imagen de la cámara, con el aspecto corregido (lo mismo que usa hoy el puño en `estados.py:609`).
- Los tiempos van en milisegundos (no en cuadros), salvo donde se dice "cuadros".
- Todo lo que dice "se detecta solo si…" significa: si la acción está en "nada", el clasificador ni la busca, y no le quita cuadros a otra seña.

---

## 1. Lo que trae la 1.0.2 (resumen para el usuario)

1. Clic con **pulgar + anular** (clic izquierdo y arrastre). El índice que apunta queda quieto y el clic cae donde apunta.
2. **Pulgar + meñique** = la acción que usted escoja. De fábrica: **doble clic**.
3. **Clic con una tecla o un pedal**. De fábrica: el **5 del teclado numérico**. Sostener = botón abajo; soltar = soltar; un toque = clic; dos toques = doble clic.
4. **Girar la pieza con un solo puño** (modo 3D): cerrar el puño y moverlo. Puño quieto sigue siendo clic derecho.
5. **Lanzar con inercia** (apagado de fábrica): soltar el puño moviéndolo rápido deja la pieza girando y frena sola. Cerrar el puño la atrapa.
6. **Pasar página con la palma abierta**: mostrar la palma quieta un momento y subir o bajar la mano.
7. **Barrido** rápido de la mano = siguiente / anterior (fotos, navegador, documentos). En los programas de diseño no hace nada de fábrica.
8. **Modo mano baja**: trabajar con la mano cerca del teclado, sin levantar el brazo.
9. **Abrir la mano de golpe** = despiezar; **cerrar de golpe** = armar. Manda el atajo que usted ponga para cada programa.

Todo lo de la 1.0.1 sigue igual: pellizco con índice (clic y arrastre, se puede apagar), puño quieto = clic derecho, zoom con pulgar + corazón y con pinza de dos manos, desplazar con dos pinzas, giro con dos puños (ahora como opción), activar/pausar, atajos Ctrl+Alt+M/X/O/D/P, rebobinado y ancla del clic.

---

## 2. TABLA COMPLETA de señas → acciones

### 2.1 Medidas nuevas del clasificador (`senas.py` + `geometria.py`)

- `p`, `pc` (ya existen): pulgar–punta del índice y pulgar–punta del corazón, divididos por la palma.
- `pa` (nueva): mínimo de (pulgar 4 → punta 16) y (pulgar 4 → falange 15), dividido por la palma.
- `pm` (nueva): mínimo de (pulgar 4 → punta 20) y (pulgar 4 → falange 19), dividido por la palma.
- `lejos_anular` / `lejos_menique` (nuevas): distancia de la punta 16 / 20 al centro de la palma, dividida por la palma. Doblado ≈ 0.31; en pellizco ≈ 1.05.
- `sep` (ya existe como `sep_puntas`, ahora se publica en `Medidas` y `como_dict`).
- `palma_estirada` (nueva, con histéresis): ABIERTA + 5 dedos extendidos + `sep ≥ 0.60` para entrar, se pierde con `sep < 0.54`. La mano relajada mide 0.44–0.52, así que nunca es "palma estirada".
- Función nueva en `geometria.py`: `pellizco_dedo(w, punta, falange, palma) -> float`.
- Suavizado igual que `p` (alfa 0.7). La coordenada z no se usa.

### 2.2 Orden de prioridad del clasificador (gana la primera que se cumple)

| # | Seña | Condición completa |
|---|---|---|
| 1 | PUÑO | Igual que hoy: 4 dedos DOB, ≥ 3 puntas cerca de la palma, pulgar cerca. |
| 2 | PELLIZCO_ANULAR (nueva) | Se detecta solo si `senas.clic_anular` está prendido. `pa < 0.28` para entrar (sale con `pa > 0.42`); `pa < 0.6 × min(p, pc, pm)`; índice EXT; `lejos_anular > 0.65`; no "puño en curso"; tras salir del puño en curso, los 150 ms siguientes exigen `pa < 0.20` (misma regla que el pellizco de hoy). |
| 3 | PELLIZCO_MENIQUE (nueva) | Se detecta solo si `senas.menique != "nada"`. `pm < 0.26` para entrar (sale con `pm > 0.40`); `pm < 0.6 × min(p, pc, pa)`; índice EXT; `lejos_menique > 0.65`; mismas defensas de "puño en curso". |
| 4 | ACTIVAR | Igual que hoy. Va después de 2 y 3: el pulgar sobre anular y meñique DOBLADOS nunca es pellizco porque la punta doblada queda a 0.31 < 0.65. |
| 5 | V | Igual que hoy. |
| 6 | PELLIZCO_CORAZON | Igual que hoy (solo si la variante está activa y `p > 0.5`). Se agrega: `pc < 0.6 × min(p, pa, pm)`. |
| 7 | PELLIZCO (índice) | Igual que hoy. Si `senas.clic_indice` está apagado se sigue detectando (lo usa la pinza de dos manos), pero en una mano no da clic. |
| 8 | ABIERTA | Igual que hoy. Lleva además el indicador `palma_estirada`. |
| 9 | APUNTAR | Igual que hoy. |
| 10 | NINGUNA | — |

"Si no hay un ganador claro, no se dispara nada": cuando dos dedos están cerca del pulgar a la vez (la regla del 0.6 no se cumple), el resultado es NINGUNA para esos cuadros. Es preferible no hacer nada que hacer el gesto equivocado.

### 2.3 Tabla de señas y eventos → acciones (una mano = la mano principal)

| Seña o evento | Cómo se reconoce (fábrica) | Modo 2D | Modo 3D | Lo que evita confusiones |
|---|---|---|---|---|
| ACTIVAR (índice y corazón juntos) | Como hoy | En pausa: sostener 250 ms = activar. Activo: toque de 120–1500 ms; dos toques en < 700 ms = pausar | Igual | Va después de los pellizcos de anular y meñique. Prueba fija: dos pellizcos de anular seguidos NO pausan. |
| V | Como hoy | Nada | Nada | — |
| APUNTAR | Como hoy | Mueve el puntero | Igual | Nunca da barrido ni scroll. |
| PELLIZCO índice | `p` 0.28 / 0.42, 66 ms (150 ms con otra mano a la vista) | Clic izquierdo y arrastre (si `clic_indice`) | Igual | Se anula si la mano viene de cerrar o abrir el puño. |
| PELLIZCO ANULAR (nuevo) | `pa` 0.28 / 0.42, 66 ms, regla del 0.6, índice EXT, punta a > 0.65 | Clic izquierdo y arrastre (si `clic_anular`) | Igual | Regla del 0.6 frente al corazón; índice EXT frente al puño. No usa la espera de 150 ms con otra mano (la pinza no lo usa). |
| PELLIZCO MEÑIQUE (nuevo) | `pm` 0.26 / 0.40, 100 ms | Acción elegida (de fábrica doble clic). Dispara UNA vez; cerrojo hasta que la mano deje la seña 2 cuadros | Igual | No se detecta en "nada". Nunca dispara si hay un botón abajo, gesto, scroll o inercia. Puntero congelado mientras dura. |
| PULGAR + CORAZÓN | Como hoy | Zoom con una mano | Igual | Apagado de fábrica. |
| PUÑO quieto | Centro movido ≤ 0.02 anchos durante toda la espera | Clic derecho a los 200 ms | Clic derecho a los **300 ms** (antes 250) | Sin clic si hubo pellizco hace < 300 ms; cerrojo hasta abrir. |
| PUÑO en movimiento (nuevo, solo 3D) | Centro movido **> 0.03 anchos** antes de que salga el clic derecho | Nada nuevo (sigue como hoy) | GIRAR con la combinación de orbitar del perfil (botón del medio en EDWIN 3D y SketchUp) | Entre 0.02 y 0.03 no pasa nada hasta cruzar 0.03. Un puño que ya hizo clic derecho nunca gira hasta abrir la mano. Solo si `orbita.girar` es "un_puno" o "ambos". |
| SOLTAR normal (abrir mientras gira) | `_abierta` (ABIERTA o ≥ 3 dedos EXT) 66 ms | — | Suelta el botón de orbitar | Si va lento (< 0.4 anchos del monitor por segundo) o la inercia está apagada, solo suelta. |
| LANZAR (nuevo, apagado de fábrica) | Primer cuadro `_abierta` con velocidad de los últimos 150 ms > 0.4 monitores/s (tope 8 monitores/s) | — | La pieza sigue girando con el botón abajo y frena con `v ← v·e^(−fricción·dt)`; para con < 30 px/s o a los 4 s | El cuadro exacto de abrir no cuenta para la velocidad (la palma salta). |
| ATRAPAR (nuevo) | 2 cuadros de PUÑO durante la inercia | — | Velocidad 0 al instante; sigue agarrada (sin soltar ni volver a bajar el botón) | — |
| FRENO de seguridad (nuevo) | Mano fuera de la cámara, cualquier tecla (gancho), pausa o bloqueo | Frena el scroll con inercia | Frena el giro con inercia | Durante la inercia se ignoran las demás señas y el puntero no sigue a la mano. |
| PALMA quieta → SCROLL (nuevo) | `palma_estirada` + centro < 0.10 anchos/s **durante 500 ms**; pista ≥ 500 ms y no sospechosa; nada abajo ni gesto; > 1000 ms desde el último gesto, arrastre, giro o golpe | Rueda: la página sigue a la mano (aviso + sonido) | Igual (en programas de diseño la rueda hace zoom: es lo esperado) | Mano relajada sep < 0.54 no arranca. Termina con 2 cuadros de PUÑO, APUNTAR, cualquier pellizco, ACTIVAR, V o mano perdida. Cerrar la mano al final NO da clic derecho ni "armar" (rearme). |
| SCROLL con inercia (nuevo, prendido de fábrica) | Al terminar con > 4 muescas/s | Sigue y frena hasta < 0.8 muescas/s | Igual | Atrapar: puño o palma quieta. Mismos frenos de seguridad. |
| BARRIDO (nuevo) | ≥ 0.20 anchos en ≤ 250 ms, \|dx\| ≥ 2.5·\|dy\|, mano ABIERTA o ≥ 4 EXT en ≥ 70 % de los cuadros; arranca desde quieta (ver nota); pista ≥ 300 ms | Genérico: flecha Derecha / Izquierda. Navegador: Alt+Derecha / Alt+Izquierda | Perfiles de diseño: nada (no se detecta) | Se decide al cruzar el umbral. Bloqueo 800 ms; dirección contraria bloqueada 1000 ms. Nunca con APUNTAR, nunca con scroll, gesto, inercia o botón abajo. |
| ABRIR DE GOLPE (nuevo) | Último cuadro de PUÑO (o puño en curso) → primer cuadro de `palma_estirada` en ≤ max(150 ms, 2.5 cuadros); centro movido ≤ 0.05 anchos; la palma se sostiene 150 ms | Atajo "despiezar" del programa | Atajo "despiezar" del programa (edwin3d: sin atajo de fábrica) | Solo si ese puño no dio clic derecho, no giró, no hubo inercia, gesto ni botón abajo. Abrir despacio tras un giro es soltar (había gesto y tarda > 150 ms). Bloqueo 1000 ms; el scroll no puede arrancar con esa palma hasta que la mano la deje. Se detecta solo si hay atajo. |
| CERRAR DE GOLPE (nuevo) | `palma_estirada` ≥ 200 ms SIN modo scroll → PUÑO en ≤ 150 ms; centro movido ≤ 0.05; el puño queda quieto 120 ms | Atajo "armar" del programa | Igual (edwin3d: sin atajo) | Si el puño se mueve > 0.03 antes de los 120 ms, gana GIRAR. Después: cerrojo de clic derecho y de giro para ese puño hasta abrir. Si la palma ya era scroll, cerrar solo termina el scroll. Se detecta solo si hay atajo. |
| TECLA o pedal (nuevo) | Gancho de teclado de bajo nivel | Sostener = izquierdo abajo; toque = clic; dos toques = doble clic (lo decide Windows) | Igual | Solo en ACTIVO (en pausa la tecla pasa normal al programa). Se suelta sola si se pierde el soltar. |
| Dos PELLIZCOS (índice) | 100 ms | Zoom o mover el dibujo | Zoom o mover el modelo | Solo el pellizco del índice; anular y meñique no cuentan. |
| Dos PUÑOS separados > 0.15 | 150 ms | — | Girar con dos manos, solo si `orbita.girar` es "dos_punos" o "ambos" | Con "ambos", si la otra mano también hace puño gana el de dos manos (el de un puño no arranca). |
| Mano perdida, pausa o bloqueo | Como hoy | Suelta todo; termina scroll, inercia y el botón de la tecla | Igual | — |

Nota del barrido: "quieta antes" = velocidad del centro < 0.5 anchos/s en los 100 ms anteriores al arranque del movimiento.

### 2.4 Prioridad entre gestos de la máquina (`estados.py`, en cada `paso`)

1. Órdenes externas (pausa, modo, perfil, tecla_clic, frenar).
2. Inercia activa (giro o scroll): solo mira ATRAPAR y los frenos.
3. Mano perdida → soltar todo.
4. Gesto en curso: `orbita` (dos puños), `pinza`, `orbita1` (un puño), `scroll`.
5. Candidato de dos manos (pinza, dos puños).
6. Una mano: zoom con una mano → pellizco índice/anular (clic izquierdo) → meñique → golpe (abrir / cerrar) → puño (clic derecho o girar) → scroll con palma → barrido → puntero.

Regla general: nada nuevo arranca mientras haya un botón abajo (del pellizco o de la tecla), y ninguna tecla (`Pulsar`) sale con botones abajo.

### 2.5 Umbral de "quieto vs moverse" del puño (3D)

| Movimiento del centro del puño desde que cerró | Resultado |
|---|---|
| ≤ 0.02 anchos durante los 300 ms | CLIC DERECHO |
| > 0.03 anchos antes del clic derecho | GIRAR (un puño) |
| Entre 0.02 y 0.03 | Nada, hasta que cruce 0.03 o se abra la mano |
| Ya dio clic derecho | Nunca gira hasta abrir la mano |

En 2D se mantiene lo de hoy (clic derecho a 200 ms y, con otra mano a la vista, la regla del 0.02).

---

## 3. Claves de config nuevas (`config.py`)

Todas van en `FABRICA`, con su rango en `RANGOS` y, si son de lista, en `OPCIONES`. `validar` rellena desde fábrica lo que falte, así que un `config.json` de la 1.0.1 carga bien. `VERSION_CONFIG` sigue en 1. Hay una prueba por paquete que carga un config.json de la 1.0.1 (sin las claves nuevas) y comprueba los valores de fábrica.

| Clave | Fábrica | Rango u opciones | Paquete |
|---|---|---|---|
| `senas.pellizco_anular.entrar` / `.salir` | 0.28 / 0.42 | (0.05, 1.0) / (0.05, 1.5); calibrables ±40 % | A |
| `senas.pellizco_menique.entrar` / `.salir` | 0.26 / 0.40 | (0.05, 1.0) / (0.05, 1.5); calibrables ±40 % | A |
| `senas.clic_indice` | True | bool | A |
| `senas.clic_anular` | True | bool | A |
| `senas.menique` | "doble_clic" | OPCIONES: doble_clic, clic_derecho, clic_medio, enter, esc, suprimir, deshacer, nada | A |
| `senas.tiempos_ms.menique` | 100 | (40, 1000) | A |
| `tecla_clic.activa` | True | bool | A |
| `tecla_clic.vk` | 0x65 (101) | (1, 254), entero | A |
| `tecla_clic.scan` | 0x4C (76) | (0, 255), entero | A |
| `tecla_clic.extendida` | False | bool | A |
| `tecla_clic.numerico` | True | bool (True = "5 del teclado numérico": acepta vk 0x65 o 0x0C con scan 0x4C sin extendida) | A |
| `tecla_clic.nombre` | "5 del teclado numérico" | texto (si no es texto, fábrica) | A |
| `tecla_clic.preguntado` | False | bool | A |
| `senas.tiempos_ms.puno_3d` | 300 | (150, 1000) | B |
| `orbita.girar` | "un_puno" | OPCIONES: un_puno, dos_punos, ambos | B |
| `orbita.k_un_puno` | 1.2 | (0.1, 5.0) | B |
| `orbita.inercia` | False | bool | B |
| `orbita.friccion` | 1.5 | (0.3, 6.0), en 1/s | B |
| `gestos.golpe` | True | bool | B |
| `gestos.por_programa` | {} | diccionario libre (como `perfiles.personalizados`); cada texto se valida con el intérprete de teclas al usarlo; inválido = se ignora | B (lo usa también C) |
| `scroll.palma` | True | bool | C |
| `scroll.inercia` | True | bool | C |
| `scroll.friccion` | 2.0 | (0.3, 6.0), en 1/s | C |
| `scroll.invertir` | False | bool | C |
| `scroll.paso` | 0.025 | (0.005, 0.10), alto de la imagen por muesca | C |
| `gestos.barrido` | True | bool | C |
| `zona.mano_baja` | False | bool | C |

`zona.codo_apoyado` se deja (no se borra, para no romper configs viejas) pero sigue sin usarse.

`gestos.por_programa` tiene esta forma: `{"edwin3d": {"abrir_golpe": "Ctrl+Alt+U", "cerrar_golpe": "", "barrido_der": "", "barrido_izq": ""}}`. Texto vacío = "nada". Clave ausente = lo de fábrica del perfil.

### 3.1 Campos nuevos de `Perfil` (`perfiles.py`)

| Campo | edwin3d | sketchup | freecad / freecad_blender / blender | edwin2d | navegador (nuevo) | generico |
|---|---|---|---|---|---|---|
| `diseno` | True | True | True | True | False | False |
| `barrido_der` / `barrido_izq` | None | None | None | None | "Alt+Derecha" / "Alt+Izquierda" | "Derecha" / "Izquierda" |
| `abrir_golpe` / `cerrar_golpe` | None / None | None / None | None / None | None / None | None / None | None / None |

- Perfil nuevo `navegador`: chrome.exe, msedge.exe, firefox.exe, brave.exe, opera.exe. Combinaciones de orbitar y desplazar como `generico`.
- edwin3d sin atajo de fábrica: "Desdoblar caras" no trae atajo en EDWIN CNC 3D (`edwin_cnc.py:1095` y `:1120`, sin `setShortcut`). El usuario se lo puede poner en EDWIN (Preferencias ▸ Atajos de teclado, por ejemplo Ctrl+Alt+U) y escribir el mismo en Opciones. Alternativa sugerida en la ayuda: despiezar = Ctrl+Shift+G (Explode Group), armar = Ctrl+G (Make Group).
- `gesto_de(perfil, nombre, cfg) -> str | None`: primero `cfg["gestos"]["por_programa"][perfil.clave][nombre]`, si no, el campo del perfil. Vacío o inválido = None (no se detecta).
- `cargar_personalizados` acepta los campos nuevos.

---

## 4. Textos exactos en pantalla (`ui/textos.py`)

Reglas: frases cortas, sin jerga, que quepan con `wraplength` 230 en Opciones y en 1024x768.

### 4.1 Paquete A — Clics

Señas y ayuda:
- `sena_pellizco_anular`: "Pulgar + anular"
- `sena_pellizco_menique`: "Pulgar + meñique"
- `ch_anular`: "Junte el pulgar con el anular: es un clic. Sosténgalo para arrastrar. El índice que apunta no se mueve."
- `ch_menique`: "Junte el pulgar con el meñique: hace la acción que usted escogió (de fábrica, doble clic)."
- `ch_tecla`: "Apriete la tecla (o el pedal) para hacer clic. Sosténgala para arrastrar. En pausa la tecla funciona normal."

Opciones, pestaña nueva "Clic":
- `op_clic_indice`: "Clic con pulgar + índice"
- `ay_clic_indice`: "El clic de siempre. Apáguelo si el puntero se le corre al pellizcar."
- `op_clic_anular`: "Clic con pulgar + anular"
- `ay_clic_anular`: "El índice queda quieto y el clic cae donde apunta."
- `op_menique`: "Pulgar + meñique hace"
- `ay_menique`: "Escoja qué pasa al juntar el pulgar con el meñique."
- Lista: `mq_doble_clic` "Doble clic", `mq_clic_derecho` "Clic derecho", `mq_clic_medio` "Clic del medio", `mq_enter` "Enter", `mq_esc` "Esc", `mq_suprimir` "Suprimir", `mq_deshacer` "Deshacer (Ctrl+Z)", `mq_nada` "Nada"
- `op_tecla_activa`: "Clic con una tecla o pedal"
- `ay_tecla_activa`: "Sostener la tecla = botón abajo. Un toque = clic. Dos toques = doble clic."
- `op_tecla_nombre`: "Tecla de clic: {nombre}"
- `op_tecla_numerico`: "¿Su teclado tiene números a la derecha?"
- `op_si` / `op_no`: "Sí" / "No"
- `op_cambiar_tecla`: "Cambiar tecla"
- `op_grabando`: "Apriete ahora la tecla o el pedal que quiere usar…"
- `op_tecla_grabada`: "Listo: la tecla es {nombre}."
- `op_tecla_no_sirve`: "Esa tecla no sirve (Ctrl, Shift, Alt o Windows). Escoja otra."
- `ay_tecla_aviso`: "Mientras el control está activo, esa tecla no escribe. Si usa «Teclas del mouse» de Windows, apáguelas."

Asistente, paso nuevo `tecla` (tipo "tecla", después de "derecho"):
- `as_tecla`: "También puede hacer clic con una tecla o un pedal. ¿Su teclado tiene números a la derecha?"
- `as_tecla_si`: "Use el 5 de los números de la derecha. Apriételo dos veces para hacer clic."
- `as_tecla_no`: "Apriete la tecla que quiere usar (o pise el pedal). Mejor una que la otra mano alcance fácil."
- `as_tecla_saltar`: "No quiero clic con tecla"
- `pista_tecla`: "Apriete la tecla: cada toque es un clic."

Asistente, paso nuevo `clic_anular` (logro de 2, después de "clic"):
- `as_clic_anular`: "Ahora junte el pulgar con el anular. El índice queda quieto y el clic no se corre. Haga 2 clics."
- `pista_clic_anular`: "Toque el pulgar con el dedo anular."

Avisos:
- `aviso_tecla_suelta`: "Se soltó el clic: la tecla parecía pegada."
- `aviso_gancho_perdido`: "Windows apagó el clic con tecla. Ya se volvió a prender."
- `aviso_menique`: "Meñique: {accion}"

Ayuda (`ui/ayuda.py`): fila `("pellizco_anular", "ch_anular")` y `("pellizco_menique", "ch_menique")` en `FILAS_2D` y `FILAS_3D`; tema nuevo `tema_tecla` con `ch_tecla` y `ay_tecla_aviso`.

### 4.2 Paquete B — Girar con un puño

- `sena_girar_un_puno`: "Puño que se mueve"
- `ch_girar_un_puno`: "Cierre el puño y muévalo: la pieza gira siguiendo la mano. Abra la mano para soltar. Puño quieto = clic derecho."
- `ch_lanzar`: "Suelte el puño mientras lo mueve rápido: la pieza sigue girando y frena sola. Cierre el puño para atraparla."
- `ch_golpe`: "Abra la mano de golpe = despiezar. Ciérrela de golpe = armar. Solo si el programa tiene atajo."

Opciones, pestaña nueva "Girar":
- `op_girar_con`: "Girar la pieza con"
- `gi_un_puno` "Un puño", `gi_dos_punos` "Dos puños", `gi_ambos` "Los dos"
- `ay_girar_con`: "Un puño: cerrar y mover. Dos puños: como en la 1.0.1."
- `op_k_un_puno`: "Rapidez del giro con un puño"
- `op_inercia`: "Lanzar la pieza (sigue girando)"
- `ay_inercia`: "Si suelta moviendo rápido, la pieza sigue girando. Para frenarla: cierre el puño, saque la mano o apriete una tecla."
- `op_friccion`: "Frena rápido ↔ Sigue girando"
- `op_golpe`: "Abrir / cerrar la mano de golpe"
- `op_programa`: "Programa"
- `op_abrir_golpe`: "Abrir de golpe manda"
- `op_cerrar_golpe`: "Cerrar de golpe manda"
- `ay_atajo`: "Escriba el atajo, por ejemplo Ctrl+Shift+G. Vacío = no hace nada."
- `ay_edwin3d_desdoblar`: "En EDWIN CNC 3D, «Desdoblar caras» no tiene atajo: póngale uno en Preferencias ▸ Atajos de teclado (por ejemplo Ctrl+Alt+U) y escriba el mismo aquí."
- `op_atajo_malo`: "Ese atajo no se entiende. Ejemplos: Enter, Ctrl+Z, Alt+Izquierda."

Asistente: el paso `girar` (3D) cambia de texto según `orbita.girar`:
- `as_girar_un_puno`: "Cierre el puño y muévalo despacio: la pieza gira. Abra la mano para soltar."
- `pista_girar_un_puno`: "Puño cerrado y mover. Quieto es clic derecho."
- (con dos puños se usa el `as_girar` de hoy).

Avisos:
- `aviso_girando`: "Girando la pieza"
- `aviso_inercia`: "La pieza sigue girando. Cierre el puño para atraparla."
- `aviso_frenado`: "Pieza detenida"
- `aviso_golpe_abrir`: "Despiezar: {atajo}"
- `aviso_golpe_cerrar`: "Armar: {atajo}"

### 4.3 Paquete C — Palma y comodidad

- `estado_pasando`: "Pasando página"
- `ayuda_pasando`: "Suba o baje la mano. Cierre la mano o apunte con el índice para terminar."
- `sena_palma`: "Palma abierta quieta"
- `ch_palma`: "Muestre la palma abierta y quieta un momento: suena un aviso. Suba o baje la mano para pasar la página."
- `ch_barrido`: "Pase la mano rápido a la derecha o a la izquierda: siguiente o anterior. En programas de diseño no hace nada."
- `ch_mano_baja`: "Trabaje con la mano baja, cerca del teclado. Apoye la muñeca y no levante el brazo."

Opciones, pestaña nueva "Palma":
- `op_scroll_palma`: "Pasar página con la palma"
- `ay_scroll_palma`: "Palma abierta y quieta medio segundo, y luego subir o bajar la mano. En programas de diseño hace zoom."
- `op_scroll_inercia`: "La página sigue un poco al soltar"
- `op_scroll_friccion`: "Para rápido ↔ Sigue andando"
- `op_scroll_invertir`: "Al revés (subir la mano baja la página)"
- `op_barrido`: "Barrido a los lados"
- `ay_barrido`: "Mano abierta pasada rápido: siguiente o anterior. Escoja la tecla por programa."
- `op_barrido_der`: "Barrido a la derecha manda"
- `op_barrido_izq`: "Barrido a la izquierda manda"

Opciones, pestaña "Comodidad":
- `op_mano_baja`: "Mano baja, cerca del teclado"
- `ay_mano_baja`: "Menos cansancio en jornadas largas. Después vuelva a calibrar la zona."

Asistente, paso "postura" con dos botones:
- `as_postura_elegir`: "¿Cómo quiere trabajar?"
- `as_postura_apoyado`: "Brazo apoyado"
- `as_postura_baja`: "Mano baja, cerca del teclado"
- `as_consejo_baja`: "Apoye la muñeca delante del teclado, con la palma hacia la pantalla. Incline la pantalla hacia atrás (o la cámara hacia abajo) hasta ver la mano entera sobre el teclado. Descanse cada rato."
- Paso nuevo `scroll` (logro de 1, después de "zoom"): `as_scroll`: "Muestre la palma abierta y quieta hasta oír el aviso. Luego suba y baje la mano." `pista_scroll`: "Dedos estirados y separados, mano quieta."

Calibración:
- `cal_incline`: "No se ve su muñeca. Incline la pantalla hacia atrás o la cámara hacia abajo."
- `cal_mano_baja_ok`: "Bien: se ve la mano entera sobre el teclado."

Avisos:
- `aviso_scroll`: "Pasando página: suba o baje la mano"
- `aviso_scroll_fin`: "Listo"
- `aviso_barrido_der` / `aviso_barrido_izq`: "Siguiente" / "Anterior"
- `aviso_baje_mano`: "Baje la mano hasta la zona del teclado"

---

## 5. Los tres paquetes (uno después de otro: A, luego B, luego C)

### 5.0 Cómo se evitan choques en los archivos que comparten

Los paquetes se hacen en orden en el mismo repositorio, cada uno con su commit y con todas las pruebas pasando antes de empezar el siguiente. Aun así, para que los cambios sean fáciles de revisar:

- **Lógica nueva en módulos propios**, y en los archivos compartidos solo "enganches" cortos:
  - A: `lycan_mouse_control/teclas.py` (intérprete de teclas, puro), `lycan_mouse_control/sistema/teclado.py` (gancho), `lycan_mouse_control/clics.py` (decisiones del meñique y la tecla, puras).
  - B: `lycan_mouse_control/gestos_puno.py` (giro con un puño, inercia, golpe).
  - C: `lycan_mouse_control/gestos_palma.py` (scroll, barrido) y `lycan_mouse_control/mano_baja.py` (zona y consejos).
- **`config.py`**: cada paquete agrega SOLO sus claves (tabla de la sección 3), al final de cada diccionario, con un comentario `# 1.0.2 paquete A/B/C`. No se reordena nada.
- **`estados.py`**: el orden de llamadas de la sección 2.4 lo deja escrito A con funciones vacías (`_gestos_puno`, `_gestos_palma`) que devuelven "nada"; B y C solo rellenan su función. Nadie mueve el bloque del pellizco ni del puño salvo el paquete dueño (A el pellizco, B el puño).
- **`senas.py`**: solo A cambia el clasificador (pellizcos nuevos, `sep`, `palma_estirada`, `lejos_*`). B y C solo LEEN medidas. Así `palma_estirada` ya existe cuando llegan B y C.
- **`acciones.py` y `salida/`**: solo A agrega `Pulsar` y `Clic(veces)`. B y C los usan.
- **`perfiles.py`**: B agrega `abrir_golpe`, `cerrar_golpe` y `gesto_de`; C agrega `diseno`, `barrido_der/izq` y el perfil `navegador`.
- **`ui/textos.py`**: cada paquete agrega su bloque al final con un comentario `# --- 1.0.2 paquete X ---`.
- **`ui/opciones.py`**: cada paquete agrega SU pestaña (A "Clic", B "Girar", C "Palma") en una función propia `_pestana_clic`, `_pestana_girar`, `_pestana_palma`. A deja la ventana en **600x520** (cabe en 1024x768) y deja el orden final de pestañas: General, Puntero, Señas, Clic, Girar, Palma, Comodidad, Atajos (las de B y C entran cuando existan). C además agrega una casilla en Comodidad.
- **`ui/asistente.py`**: A agrega `clic_anular` y `tecla`; B solo cambia el texto de `girar`; C agrega `scroll` y la elección de postura. "pausar" sigue de último. Conteo de pasos: hoy 11 (2D) / 14 (3D) → tras A 13 / 16 → tras B 13 / 16 → tras C 14 / 17. Cada paquete actualiza `test_motor_app.py:239` y `test_ronda2.py:682-686`.
- **`docs/decisiones.md`**: cada paquete agrega sus decisiones al final, con fecha.
- **`pruebas/conftest.py`**: `verificar_invariantes` lo amplía A (no hay `Pulsar` con botones abajo; la tecla nunca deja el izquierdo abajo al final). B agrega: el botón de orbitar nunca queda abajo al final, aunque haya inercia. C agrega: no sale rueda con botones abajo.
- Ninguna prueba instala el gancho ni abre la cámara: el gancho se prueba con su función pura `decidir`, y la app con `--sin-gancho` (o `sistema=False`). Las pruebas siguen usando `LYCAN_MOUSE_DATOS` (fixture autouse).

### 5.1 PAQUETE A "Clics" (funciones 1, 2 y 3)

**Archivos:** `senas.py`, `geometria.py`, `estados.py`, `acciones.py`, `salida/base.py`, `salida/windows.py`, `salida/simulada.py`, `teclas.py` (nuevo), `clics.py` (nuevo), `sistema/teclado.py` (nuevo), `motor.py`, `app.py`, `config.py`, `calibracion.py` (`_CALIBRABLES`), `sintetico.py`, `ui/opciones.py`, `ui/asistente.py`, `ui/ayuda.py`, `ui/textos.py`, `ui/ventana_principal.py` (si muestra la seña), pruebas.

**Piezas comunes que deja hechas (las usan B y C):**
- `Pulsar(teclas: tuple[str, ...])`: baja todo en orden y sube al revés en UNA llamada de SendInput. `Clic(boton, veces=1)`; veces=2 = doble clic en una llamada.
- `salida/base.py`: `Pulsar` no sale con `foco_propio`, sobre la ventana propia, ni con botones abajo.
- `salida/windows.py`: mapa nombre → VK (enter 0x0D, esc 0x1B, supr 0x2E, tab, espacio, letras, dígitos, F1–F24, flechas 0x25–0x28, RePág, AvPág, Inicio, Fin, ctrl, shift, alt) y `KEYEVENTF_EXTENDEDKEY` para flechas, Supr, Insert, Inicio, Fin, RePág y AvPág. `dwExtraInfo = LYCAN_EXTRA`.
- `teclas.py`: `interpretar_envio("Ctrl+Shift+G") -> tuple | None` y `nombre_envio(tupla) -> str`, con ida y vuelta. Acepta nombres en español ("Supr", "Izquierda", "RePág") y en inglés ("Del", "Left").

**Función 1, anular:** clasificador (sección 2.2). En `estados.py`, `crudo = s == Sena.PELLIZCO` pasa a `s in senas_clic_izq()` según `clic_indice` y `clic_anular`; el anular se agrega a las listas de "no neutra" (:519) y a `_rearme_dos_manos` (:689). La pinza de dos manos sigue con PELLIZCO solo. El ancla queda igual (con el anular, `_antes_del_cierre` da None y se usa el punto quieto o el rebobinado: es lo correcto).

**Función 2, meñique:** bloque nuevo en `_una_mano`, parecido al del puño: confirma a los 100 ms, dispara una vez, cerrojo hasta 2 cuadros con otra seña. Clics: `ir_a(posicion_en(inicio − rebobinado))` + `Clic(IZQ, 2)` / `Clic(DER)` / `Clic(MEDIO)` (este respeta `_medio_permitido`). Teclas: `Pulsar(("enter",))`, `("esc",)`, `("supr",)`, `("ctrl","z")`. Puntero congelado mientras dura.

**Función 3, tecla o pedal:**
- `sistema/teclado.py`: hilo propio con `SetWindowsHookExW(WH_KEYBOARD_LL=13, …)` + `GetMessageW`. `argtypes`/`restype` declarados (LRESULT = c_ssize_t, WPARAM, LPARAM de 64 bits). Se guarda la referencia del HOOKPROC. El callback solo llama a `decidir` y encola; nunca hace SendInput.
- Función pura `decidir(vk, scan, extendida, abajo, inyectada, extra, estado) -> (suprimir, evento)`:
  - Inyectada (flag 0x10) o `extra == LYCAN_EXTRA` → dejar pasar, sin evento.
  - Modo grabar → suprimir y devolver `("grabada", vk, scan, extendida)` (rechaza Ctrl, Shift, Alt y Windows).
  - Si es la tecla elegida (numérico: vk 0x65 o 0x0C con scan 0x4C sin extendida; si no, vk+scan+extendida iguales): si `activa` y el motor está en ACTIVO al BAJAR → suprimir y anotar "esta pulsación se suprimió"; repeticiones del bajar → suprimir sin evento; el subir se suprime **solo si** el bajar se suprimió (si no, la tecla quedaría pegada en el otro programa). Eventos: `("tecla_clic", True/False, t)`.
  - Cualquier otra tecla con el flag `inercia_activa` del motor → dejar pasar y devolver `("frenar",)` (lo usan B y C).
- Perro guardián: si pasan 60 s sin que el hilo reciba nada mientras hay actividad, o si `SetWindowsHookExW` falla, se reinstala y sale `aviso_gancho_perdido`.
- `estados.py`: `tecla_clic(t, abajo)`. Al bajar, si ACTIVO, sin gesto, sin inercia, sin scroll y sin `izq`: `[puntero.anclar(t), Bajar(IZQ)]`, `izq=True`, `izq_fuente="tecla"`. Al subir, si la fuente es la tecla: `Subir(IZQ)` + `soltar_ancla`. Toque y doble toque los decide Windows; el ancla asegura los 4 px. Mientras la tecla sostiene, el pellizco no empieza ni suelta ese botón.
- Seguridad: el gancho anota la hora de cada bajar (también repeticiones). Si la tecla sostiene el botón y pasaron más de (retraso de repetición + 2 / velocidad de repetición + 250 ms) sin bajar repetido (valores de `SystemParametersInfo` SPI_GETKEYBOARDDELAY y SPI_GETKEYBOARDSPEED; en pruebas un valor fijo de 1000 ms), se suelta y sale `aviso_tecla_suelta`. También se suelta con pausa, bloqueo, mano perdida y cambio de programa. No se vuelve a bajar hasta un bajar nuevo. No se usa GetAsyncKeyState.
- `motor.py`: atiende `("tecla_clic", abajo, t)` y `("frenar",)`; publica `estado_base` e `inercia_activa` para el gancho.
- `app.py`: arranca el gancho junto a `HiloAtajos`; argumento `--sin-gancho`; lo detiene en `_finalizar`; `try/finally` y `atexit` mandan "soltar todo".
- Asistente: paso `tecla` (Sí / No / No quiero) + modo grabar; guarda `tecla_clic.preguntado=True`. Ojo: con el asistente en primer plano, `foco_propio=True` bloquea Bajar y Clic en la salida simulada; el paso de la tecla se cuenta con el evento `tecla_clic` de la máquina (no con el Bajar que sale).

**Pruebas del paquete A:**
- `sintetico.py`: `_objetivo` con `punta_anular` y `punta_menique`; posturas `pellizco_anular` y `pellizco_menique` en `POSTURAS` y `SENA_ESPERADA` (así `test_senas.py` las prueba con 200 variaciones, 2 y 4 mm, las dos manos). Agregarlas a `test_aleatorio.py`, con órdenes aleatorias de `tecla_clic` y `frenar`.
- Clic con anular; arrastre con anular; pulgar + corazón (variante activa) no lo roba; abrir del puño no da clic de anular; dos pellizcos de anular seguidos no pausan; `clic_indice=False` deja el anular y la pinza de dos manos funcionando.
- Meñique: una prueba por cada acción de la lista; "nada" no detecta la seña; no dispara con botón abajo; dispara una sola vez aunque se sostenga.
- `teclas.py`: ida y vuelta de Enter, Esc, Supr, Ctrl+Z, Alt+Izquierda, Ctrl+Shift+G, Ctrl+Alt+U; textos malos dan None.
- `decidir`: 5 numérico con y sin Bloq Num; el 5 normal (0x35, scan 0x06) no cuenta; inyectada pasa; repeticiones suprimidas; en pausa pasa el bajar y también el subir; bajar en ACTIVO, pausa en medio, subir → se suprime el subir; modo grabar; modificadores rechazados.
- Máquina: toque = Bajar+Subir; dos toques; sostener + mover la mano = arrastre anclado; en pausa no hace nada; seguridad suelta sola; mano perdida suelta.
- Invariantes nuevas en `conftest.py`.
- Config: config.json de la 1.0.1 carga con los valores de fábrica nuevos; valores fuera de rango vuelven a fábrica; `senas.menique` inválido vuelve a "doble_clic".
- Interfaz: pestaña "Clic" sin etiquetas cortadas (`test_ronda1_interfaz.py:242`) a 1024x768; manejadores que aceptan llamarse sin evento; conteo de pasos 13 / 16.

### 5.2 PAQUETE B "Girar con un puño" (funciones 4, 5 y 9)

**Archivos:** `gestos_puno.py` (nuevo), `estados.py` (bloque del puño y enganche), `perfiles.py`, `motor.py` (flag `inercia_activa`), `config.py`, `ui/opciones.py` (pestaña "Girar"), `ui/asistente.py` (texto de `girar`), `ui/ayuda.py`, `ui/textos.py`, `sistema/sonidos.py` (si se agrega un tono "atrapar"), pruebas.

**Función 4, un puño:**
- Espera del puño en 3D: `max(puno, puno_3d)` = 300 ms (antes 250).
- Si modo 3D, `orbita.girar` en "un_puno" o "ambos", el puño es válido, no ha disparado y el centro se movió > 0.03 anchos → `_iniciar_orbita1(t, p)`: anula el clic derecho; `pos = posicion_en(puno_inicio − rebobinado)` recortada a `zona_segura`; `ir_a(pos)`; `_medio_permitido`; `traductor.empezar(perfil.combinacion_orbitar(modo))`.
- `_paso_orbita1`: reutiliza `_rebasar_orbita` y `_paso_orbita` con M = centro del puño, dθ = 0, `dx = G·k_un_puno·dMx·W`, `dy = G·k_un_puno·dMy·H`; mismo descarte de saltos, tope, resto y reagarre en el borde.
- Termina con `_abierta` 66 ms; mano perdida → `_soltar_todo`.
- En `paso()`, `gesto=="orbita1"` va antes del candidato de dos manos. Con "un_puno" se apaga el candidato de dos puños; con "ambos", el de un puño no arranca si la otra mano también es PUÑO.
- `estado_visible` → GIRANDO_3D.

**Función 5, lanzar / atrapar / frenar (apagado de fábrica):**
- En `_paso_orbita1` se guardan los `MoverDelta` de los últimos 150 ms (sin el cuadro de abrir).
- Al primer cuadro `_abierta`: si `orbita.inercia` y v > 0.4 anchos del monitor por segundo → `gesto="inercia"` con el botón abajo. Cada `paso`: `MoverDelta(v·dt)`, `v *= exp(−friccion·dt)`, dt ≤ 0.07, reagarre en el borde. Fin con v < 30 px/s o 4 s → `traductor.terminar` + `_pedir_rearme`.
- Atrapar: 2 cuadros de PUÑO → v = 0 y vuelve a `orbita1` con los filtros rebasados, sin soltar ni volver a bajar.
- Frenos: mano perdida, orden `("frenar",)` del gancho (cualquier tecla), pausa o bloqueo (`_soltar_todo`).
- `motor.inercia_activa` se prende mientras dura (lo lee el gancho de A).

**Función 9, golpe:**
- `gestos_puno.py` lleva una pequeña historia por mano: última vez en PUÑO (o puño en curso), última vez en `palma_estirada`, y si el puño actual hizo clic derecho, giró o hubo gesto.
- Reglas exactas de la tabla 2.3. Envía `Pulsar(interpretar_envio(gesto_de(perfil, "abrir_golpe", cfg)))`.
- Solo se detecta si `gestos.golpe` y hay atajo para el programa activo.
- Cerrar de golpe: el puño de "armar" queda con cerrojo de clic derecho y de giro hasta abrir.
- La espera del clic derecho y la del golpe conviven: un puño cerrado de golpe espera 120 ms quieto (armar); si se mueve > 0.03 gira; el clic derecho no sale de un puño que ya armó.

**Pruebas del paquete B:**
- Puño quieto 300 ms en 3D = clic derecho; puño movido > 0.03 = gira con el botón del medio en edwin3d y SketchUp; entre 0.02 y 0.03 no hace nada; tras clic derecho nunca gira; en 2D el puño sigue como hoy.
- `orbita.girar`: "dos_punos" = como la 1.0.1; "ambos" con dos puños gana el de dos manos.
- Inercia apagada: soltar rápido solo suelta. Prendida: lanzar sigue y frena; atrapar con puño; frenar con mano fuera, con orden "frenar" y con pausa; el botón del medio nunca queda abajo al final (invariante).
- Golpe: perfil sin atajo no detecta nada; con atajo, abrir de golpe manda el atajo una vez; abrir despacio tras un giro NO despieza; puño que dio clic derecho y luego abre de golpe NO despieza; cerrar de golpe arma y no da clic derecho; cerrar de golpe moviéndose gira y no arma.
- Config de la 1.0.1 carga; `gestos.por_programa` con basura (no dict, textos inválidos) no rompe.
- Pestaña "Girar" sin cortes a 1024x768, con el texto de edwin3d visible; pasos 13 / 16; texto del paso `girar` según la opción.

### 5.3 PAQUETE C "Palma y comodidad" (funciones 6, 7 y 8)

**Archivos:** `gestos_palma.py` (nuevo), `mano_baja.py` (nuevo), `estados.py` (enganche y estado visible `PASANDO_PAGINA`), `perfiles.py`, `config.py`, `motor.py` (`_comodidad` y `evaluar_distancia` con mano baja), `calibracion.py`, `ui/calibracion.py`, `ui/opciones.py` (pestaña "Palma" + casilla en Comodidad), `ui/asistente.py`, `ui/ayuda.py`, `ui/textos.py`, `ui/ventana_principal.py` (color y texto del estado nuevo), `sistema/sonidos.py` (tono "scroll"), pruebas.

**Función 6, scroll con la palma:**
- Arranque y fin según la tabla 2.3. Al arrancar: `gesto="scroll"`, puntero congelado, `Aviso("scroll")` + `Sonido("scroll")`, estado `PASANDO_PAGINA`.
- Rueda: la página sigue a la mano. Subir la mano = el contenido sube = rueda negativa (con `scroll.invertir` al revés). Una muesca cada `scroll.paso` del alto de la imagen, con fracciones de 120 donde el perfil lo acepta. Cubeta propia: 20 muescas/s en perfiles no de diseño, `perfil.max_muescas_s` en los de diseño (edwin2d: ≤ 8/s y muescas enteras).
- Inercia (prendida de fábrica): si al terminar iba a > 4 muescas/s, sigue con `v *= exp(−friccion·dt)` hasta < 0.8/s. Atrapar con puño o palma quieta; mismos frenos que B; prende `motor.inercia_activa`.
- Al terminar: `_pedir_rearme`.

**Función 7, barrido:**
- Historia (t, centro, seña) de los últimos 300 ms. Condiciones y bloqueos de la tabla 2.3. Se decide al cruzar el umbral. Manda `Pulsar(interpretar_envio(gesto_de(perfil, "barrido_der", cfg)))`.
- Se detecta solo si `gestos.barrido` y el programa tiene tecla. Perfiles con `diseno=True`: nada de fábrica.

**Función 8, mano baja:**
- `zona.mano_baja`. Paso "postura" del asistente con dos botones; con "mano baja" muestra `as_consejo_baja` y en la calibración de zona revisa que la muñeca (`img[0]`) se vea (y < 0.97 en ≥ 90 % de los cuadros); si no, `cal_incline`.
- `mano_baja.recortar_zona(zona, alto_mano)`: `y1 ≤ 1 − 1.1·alto_mano`, para que la muñeca no salga de la imagen.
- Con mano baja: no sale el aviso de brazo alto (`motor.py:479`); `evaluar_distancia` acepta la mano un poco más grande (más cerca); si la mano está por encima de la zona más de 2 s, `aviso_baje_mano`.
- `Mapeo` ya centra la zona pedida, así que sirve para zonas bajas.

**Pruebas del paquete C:**
- Scroll: la palma estirada quieta 500 ms arranca; la relajada nunca arranca (también moviéndola); la palma que se mueve no arranca; la palma justo después de un giro, arrastre o golpe (< 1 s) no arranca; subir la mano = rueda negativa (e invertida con la opción); termina con puño sin dar clic derecho; inercia y freno; cubeta de edwin2d ≤ 8/s y muescas enteras; ninguna rueda con botones abajo (invariante).
- Barrido: genérico manda Derecha / Izquierda; navegador Alt+flechas; perfiles de diseño nada; el regreso de la mano no dispara al revés; una mano que entra por el lado no dispara; APUNTAR rápido no dispara; con `gestos.barrido=False` nada.
- Mano baja: recorte de la zona; aviso de brazo alto apagado; textos del asistente y de la calibración; config de la 1.0.1 carga con `mano_baja=False`.
- Pestaña "Palma" y casilla de Comodidad sin cortes a 1024x768; pasos 14 / 17 con "pausar" de último.

---

## 6. Pruebas en la máquina real (las hace el usuario, después de C)

1. El 5 del teclado numérico (o el pedal) hace clic en EDWIN CNC 3D y no escribe "5" en la casilla de medidas.
2. Con MediaPipe corriendo 15 minutos, el clic con tecla sigue funcionando (Windows no quitó el gancho).
3. El pedal manda repeticiones al sostenerlo (si no, la seguridad lo soltaría: ajustar).
4. Pellizco con anular frente al índice: el clic cae donde apunta.
5. Girar con un puño en EDWIN CNC 3D y SketchUp; puño quieto = menú del clic derecho.
6. Palma: pasar páginas en el navegador sin que arranque al reposar la mano.
7. Mano baja: calibrar con la pantalla inclinada.

## 7. Al terminar cada paquete

- `cd C:/dev/lycan-mouse-control && py -3.10 -m pytest -q -x` pasa completo.
- `docs/decisiones.md` y `docs/especificacion.md` al día.
- `git commit` (sin push ni tag) con el mensaje en español y la línea final `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- La versión se sube a 1.0.2 en el último paquete (C).
