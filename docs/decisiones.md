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
