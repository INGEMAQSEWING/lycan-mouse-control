# Decisiones de Lycan Mouse Control

Cada decisión nueva se agrega al final, con fecha y la versión a la que pertenece.

## 2026-11-15 — Plan de la 1.0.2 (ver `docs/plan-1.0.2.md`)

1. **El pellizco con el índice sigue activo de fábrica** junto con el del anular. Cada uno tiene su casilla para apagarlo. La pinza de dos manos solo usa el índice.
2. **Pulgar + meñique hace doble clic de fábrica.** Se puede cambiar a clic derecho, clic del medio, Enter, Esc, Suprimir, Deshacer o Nada. Nunca dispara con un botón abajo.
3. **Tecla de clic de fábrica: el 5 del teclado numérico**, reconocido por su código de escaneo (0x4C sin "extendida"), así funciona con y sin Bloq Num y nunca toca el 5 de la fila de arriba.
4. **En pausa la tecla de clic pasa normal al programa.** Solo se suprime con el control ACTIVO. Si el bajar pasó, el subir también pasa (para que no quede pegada).
5. **Gancho de teclado con ctypes (WH_KEYBOARD_LL)**, sin pynput, con perro guardián que lo reinstala si Windows lo quita. No guarda ni registra ninguna otra tecla.
6. **Girar con un puño es lo de fábrica en 3D**; dos puños queda como opción ("dos puños" o "los dos").
7. **Puño en 3D: la espera del clic derecho sube de 250 a 300 ms**, para alcanzar a arrancar el giro. Quieto ≤ 0.02 anchos = clic derecho; > 0.03 = gira; entre los dos, nada.
8. **Lanzar con inercia al girar: apagado de fábrica.** En el scroll con la palma: prendido de fábrica.
9. **Scroll con la palma: palma estirada (separación ≥ 0.60) y quieta 500 ms.** La mano relajada (0.44–0.52) nunca lo arranca.
10. **Barrido: perfiles de diseño sin tecla de fábrica.** Genérico: flechas Derecha/Izquierda. Perfil nuevo "navegador": Alt+Derecha/Alt+Izquierda.
11. **EDWIN CNC 3D no tiene atajo para "Desdoblar caras"** (`plugins/edwin_cnc.py:1095` y `:1120`, sin atajo). El perfil edwin3d queda con abrir/cerrar de golpe SIN atajo; el usuario puede ponerle uno en EDWIN (Preferencias ▸ Atajos de teclado) y escribirlo en Opciones. Alternativa: Ctrl+Shift+G (Explode Group) / Ctrl+G (Make Group).
12. **Una seña cuya acción está en "nada" no se detecta**, para que no le quite cuadros a otra seña.
13. **Opciones pasa a 600x520** con 8 pestañas: General, Puntero, Señas, Clic, Girar, Palma, Comodidad, Atajos.
14. **`VERSION_CONFIG` sigue en 1**: las claves nuevas se rellenan solas desde fábrica. `zona.codo_apoyado` se deja aunque no se usa.

## 2026-11-15 — Paquete A «Clics» de la 1.0.2 (hecho)

15. **La tecla de clic no presiona si no se ve la mano.** Con el control activo la tecla igual se traga (no escribe), pero sin mano a la vista no baja el botón: «mano perdida» suelta todo y el puntero no lo maneja nadie. Así las secuencias desordenadas nunca dejan el botón abajo sin mano.
16. **El perro guardián del gancho lo vuelve a poner cada 60 s sin teclas, sin avisar.** No hay forma de saber si Windows lo quitó (y GetLastInputInfo también cuenta nuestros movimientos del puntero). Se pone el nuevo antes de quitar el viejo, así no hay hueco. El aviso «Windows apagó el clic con tecla» sale solo cuando ponerlo había fallado y luego funcionó.
17. **La repetición del teclado llega a la máquina como «tecla_repite»** (se traga en el programa). La máquina la usa solo para la seguridad; nunca vuelve a bajar el botón con una repetición.
18. **El asistente cuenta los clics del anular y de la tecla con lo que decide la máquina** (`Vista.cuentas`), no con los botones que salen: con el asistente al frente la salida no deja pasar los clics.
19. **El meñique con una tecla (Enter, Esc, Suprimir, Deshacer) muestra un aviso corto** («Meñique: Enter»); con los clics basta el sonido y el nombre en la franja.
20. **Mientras la tecla sostiene el botón, el pellizco no lo toca** (ni lo suelta ni lo vuelve a bajar), y la tecla no baja si el pellizco ya tiene el botón.
21. **Al grabar una tecla se traga también su soltar y sus repeticiones**, para que no llegue al programa la mitad de la pulsación. Ctrl, Shift, Alt y Windows se rechazan con aviso y se sigue esperando otra tecla.
22. **«Dos dedos cerca del pulgar» da NINGUNA solo cuando el anular o el meñique están en pellizco con el índice estirado** y no ganan claro. El pellizco del corazón (variante) además exige ganar claro frente al anular y el meñique cuando esas señas se buscan.
23. **`palma_estirada` y `sep` ya quedan en las medidas** (los usan los paquetes B y C); en el paquete A no cambian nada de lo que hace la mano.

## 2026-11-15 — Paquete B «Girar con un puño» de la 1.0.2 (hecho)

24. **De fábrica `orbita.girar = "un_puno"` apaga el giro con dos puños.** Las pruebas de la 1.0.1 que giran con dos puños ahora prenden la opción «Dos puños» (`DOS_PUNOS` en las pruebas). Con «Los dos», si las dos manos están en puño gana el de dos manos.
25. **La velocidad para lanzar se mide con la mano, no con el puntero.** El filtro del puntero se atrasa y con un lanzamiento rápido daba la mitad de la velocidad real (no llegaba nunca al umbral de 0,4 monitores por segundo). Se usa el centro del puño (sin filtro) de los últimos ~150 ms, sin el cuadro de abrir, con la misma ganancia del giro.
26. **La inercia también se reagarra en el borde**, como el giro con dos puños: suelta el botón, vuelve al punto de agarre, espera 600 ms (para no hacer doble clic del medio) y sigue con la velocidad que le quedaba. Nunca dura más de 4 s en total. Atrapar con el puño durante ese reagarre sigue esperando el reagarre (el botón está arriba).
27. **Sin mano, la inercia frena al perder la pista (150 ms), no en el primer cuadro sin mano.** Es la misma regla de «mano perdida» de siempre: un cuadro suelto que MediaPipe pierde no debe frenar la pieza.
28. **El golpe mide el tiempo desde el último cuadro de PUÑO, no desde el «puño en curso».** El «puño en curso» del clasificador sigue prendido mientras la mano se abre despacio, y con él una mano que se abre en 200 ms o más también parecía «de golpe».
29. **Hueco del golpe: 150 ms o 3,5 cuadros (el plan decía 2,5).** La separación de los dedos va suavizada y la palma estirada aparece un cuadro más tarde; a 15 cuadros por segundo 2,5 cuadros no alcanzaban nunca.
30. **El puño de «armar» queda «usado»:** no da clic derecho, no gira y, si se abre de golpe, no despieza (si no, armar y despiezar se dispararían seguidos). Lo mismo un puño que dio clic derecho o que giró.
31. **El puño de una mano en 3D espera 300 ms (`senas.tiempos_ms.puno_3d`, de 150 a 1000)**; en 2D sigue en 200 ms (250 con otra mano a la vista). Puño que se mueve despacio (menos de 0,02 anchos en esos 300 ms) sigue siendo clic derecho.
32. **El texto obligatorio del modo 3D cambió** a «Modo 3D: cierre el puño y muévalo para girar el modelo.» (antes «dos manos cerradas»), porque ahora de fábrica se gira con un puño. «Girando el modelo — abra la mano para soltar».
33. **`gestos.por_programa` se limpia al cargar:** solo quedan programas con diccionario y textos (hasta 60 letras). Un texto que no se entiende como atajo se guarda tal cual pero no se usa (el gesto no se detecta). En Opciones no se guarda un atajo que no se entiende y se avisa.
34. **Avisos en pantalla del paquete B:** «La pieza sigue girando…» al lanzar, «Pieza detenida» al frenar con una tecla, y «Despiezar: …» / «Armar: …» con el atajo. Al empezar a girar no sale aviso (ya lo dice el estado GIRANDO), para no llenar la pantalla.

## 2026-11-15 — Paquete C «Palma y comodidad» de la 1.0.2 (hecho)

35. **La espera de la palma quieta solo empieza con la mano abierta 3 cuadros seguidos y la separación de los dedos de verdad en 0,60 o más.** La separación va suavizada: al pasar de apuntar (que mide ~0,8) a la mano abierta relajada quedaba un cuadro «estirada» y la histéresis (se pierde con < 0,54) la dejaba pegada; una mano casi estirada (0,57) arrancaba el scroll. Una vez empezada, la espera sigue con la histéresis de siempre.
36. **La palma estirada quieta medio segundo ahora pasa página aunque después se cierre el puño.** Lo de la 1.0.1 «mano abierta quieta → puño = clic derecho» sigue igual con la mano abierta relajada (como se suele tener). La prueba vieja que usaba la palma estirada quieta 1,5 s antes del puño ahora se corre también con «Pasar página con la palma» apagado.
37. **Terminar el scroll con el puño no deja la página andando sola.** Cerrar la mano es «agarrar»: la inercia sale solo si se termina con otra seña (apuntar, un pellizco, la V…). Si no, el puño que termina el scroll la atraparía al instante.
38. **Atrapar con la palma estirada (2 cuadros) vuelve al modo «pasar página»** (la página sigue otra vez a la mano); atrapar con el puño la detiene y termina.
39. **La inercia del scroll nunca dura más de 6 s** (el plan no ponía tope; con el frenado más suave, «Sigue andando», duraba más de 10 s).
40. **El scroll tiene su propio signo y no usa «Invertir acercar/alejar» ni el `invertir_rueda` del perfil**: subir la mano = rueda negativa (el contenido sube), con `scroll.invertir` al revés. En programas de diseño la rueda hace zoom, como dice el plan.
41. **Con rueda fraccionaria (EDWIN CNC 3D) el scroll no manda nada por debajo de un cuarto de muesca** (el temblor de la mano quieta no debe acercar/alejar) y alejar va en muescas enteras, igual que el zoom (decisión de la ronda 4 por el piso de 5 cm de EDWIN CNC 3D).
42. **El puño que termina el scroll queda «usado» para el golpe**: abrirlo de golpe no despieza y cerrarlo no arma (además del rearme que ya evita el clic derecho y el giro).
43. **El barrido tampoco sale 300 ms después de un gesto o de soltar un botón** (el plan no lo decía): soltar un arrastre moviendo la mano rápido no debe mandar una flecha. La historia del barrido se borra mientras hay un gesto.
44. **El scroll tampoco arranca 1 s después de un barrido** (el plan lo pedía para gesto, arrastre, giro y golpe): pasar la mano y dejarla quieta no debe ponerse a pasar página.
45. **Una palma que sube muy despacio (menos de 0,10 anchos por segundo) cuenta como quieta**: es lo que dice el plan; el scroll arranca con la referencia en la posición de ese momento, así que no salta.
46. **Con la mano baja la calibración acepta la mano hasta 0,32 de ancho** (antes 0,25 = «Aléjese un poco»), y si la muñeca no se ve en el 90 % de los cuadros de la zona, se repite la zona con «Incline la pantalla…».
47. **El aviso «Baje la mano» sale una sola vez** mientras la mano siga arriba; vuelve a poder salir cuando la mano baja a la zona.
48. **Perfil nuevo «Navegador de internet»** (Chrome, Edge, Firefox, Brave, Opera) con orbitar y desplazar como el genérico; en Opciones ▸ Palma, al escribir la tecla de fábrica de un programa no se guarda nada (solo se guarda lo que el usuario cambia).
49. **La versión pasa a 1.0.2** (`version.py`) con este paquete, el último de la 1.0.2.

