"""TODOS los textos de cara al usuario (español de Colombia, trato de "usted", sin jerga).

Prohibido usar palabras como "landmark", "threshold", "frame" o "Hz" (lo revisa una prueba).
"""

TXT: dict[str, str] = {
    # ---- estados ----
    "estado_PAUSA": "● PAUSADO",
    "estado_ACTIVO": "● ACTIVO",
    "estado_ARRASTRANDO": "● ARRASTRANDO",
    "estado_GIRANDO_3D": "● GIRANDO",
    "estado_DESPLAZANDO": "● DESPLAZANDO",
    "estado_SIN_MANO": "● SIN MANO",
    "estado_BLOQUEADO": "● EN ESPERA",
    "estado_DETENIDO": "● DETENIDO",
    "ayuda_PAUSA": "PAUSADO — haga la seña de activar (índice y corazón juntos) para empezar",
    "ayuda_ACTIVO": "ACTIVO — mueva el dedo índice",
    "ayuda_ARRASTRANDO": "Arrastrando — abra los dedos para soltar",
    "ayuda_GIRANDO_3D": "Girando el modelo — abra la mano para soltar",
    "ayuda_GIRANDO_3D_dos": "Girando el modelo — abra las manos para soltar",
    "ayuda_INERCIA": "El modelo sigue girando solo — cierre el puño para atraparlo",
    "ayuda_DESPLAZANDO": "Moviendo el dibujo — abra los dedos para soltar",
    "ayuda_DESPLAZANDO_3D": "Moviendo el modelo — abra los dedos para soltar",
    "ayuda_SIN_MANO": "SIN MANO — se soltaron todos los botones",
    "ayuda_BLOQUEADO": "En espera — vea el aviso",

    # ---- nombre de la seña o evento (franja grande) ----
    "sena_clic_izquierdo": "CLIC IZQUIERDO",
    "sena_arrastre_fin": "SOLTAR",
    "sena_clic_derecho": "CLIC DERECHO",
    "sena_acercar": "ACERCAR",
    "sena_alejar": "ALEJAR",
    "sena_zoom": "ACERCAR / ALEJAR",
    "sena_girar": "GIRAR",
    "sena_desplazar": "MOVER EL DIBUJO",
    "sena_desplazar_3D": "MOVER EL MODELO",
    "sena_dos_manos": "DOS MANOS…",
    "sena_soltar": "SOLTAR",
    "sena_activado": "ACTIVADO",
    "sena_pausado": "PAUSADO",
    "sena_activar_puesta": "Sostenga…",
    "sena_sostenga": "Sostenga…",
    "sena_PUNO": "PUÑO",
    "sena_ACTIVAR": "DOS DEDOS JUNTOS",
    "sena_V": "V",
    "sena_PELLIZCO": "PELLIZCO",
    "sena_PELLIZCO_CORAZON": "PULGAR + CORAZÓN",
    "sena_ABIERTA": "MANO ABIERTA",
    "sena_APUNTAR": "APUNTANDO",
    "sena_NINGUNA": "",

    # ---- avisos ----
    "aviso_sena_larga": "Seña muy larga: hágala y suéltela",
    "aviso_pausa_sin_mano": "Se pausó porque no se ven las manos.",
    "aviso_sobre_ventana": "El puntero está sobre Lycan Mouse Control: el clic no se hizo.",
    "aviso_bloqueado_admin": ("La ventana activa se abrió como administrador. Para manejarla con gestos, "
                              "abra Lycan Mouse Control también como administrador."),
    "aviso_bloqueado_envio": ("Windows no está recibiendo el ratón (pantalla bloqueada o aviso de seguridad). "
                              "Se pausó el control; se reintenta solo."),
    "aviso_desbloqueado": "Listo: se puede volver a activar.",
    "aviso_error": "Algo falló y se pausó el control. Se soltaron todos los botones. Puede seguir trabajando.",
    "aviso_motor_detenido": ("El control con las manos se detuvo por un error. Se soltaron todos los botones. "
                             "Cierre y vuelva a abrir Lycan Mouse Control."),
    "aviso_fatal": "El error se repitió varias veces. Lycan Mouse Control se cerrará para no causar problemas.",
    "aviso_camara_perdida": "La cámara se desconectó. Reintentando…",
    "video_sin_imagen": "Sin imagen de la cámara",
    "video_abriendo": "Abriendo la cámara…",
    "aviso_no_camara": ("No encuentro la cámara. Revise que ningún otro programa (Zoom, Teams, Cámara) "
                        "la esté usando."),
    "aviso_lento": "Su equipo va lento: cierre otros programas o baje la resolución.",
    "aviso_camara_lenta": ("La cámara entrega pocas imágenes por segundo. Puede que otro programa (Zoom, Teams, "
                           "Cámara) la esté usando o que haya poca luz."),
    "aviso_camara_ocupada": ("Otro programa (Zoom, Teams, Cámara) está usando la cámara; ciérrelo y espere "
                             "unos segundos."),
    "aviso_no_guardo": ("No se pudo guardar la configuración (la carpeta no permite escribir). "
                        "Los cambios se perderán al cerrar."),
    "aviso_config_solo_lectura": ("Al abrir no se pudo leer su configuración; para no borrarla, en esta "
                                  "sesión los cambios no se guardan. Cierre y vuelva a abrir el programa."),
    "aviso_sin_registro": ("No se pudo crear el registro (la carpeta no permite escribir). El programa funciona, "
                           "pero no quedarán anotados los problemas."),
    "aviso_no_arranca": ("No se pudo arrancar. Revise la cámara y vuelva a abrir el programa. "
                         "Detalles en ? > Abrir carpeta de registros."),
    "aviso_no_abre": ("No se pudo abrir Lycan Mouse Control. Vuelva a intentarlo; si sigue pasando, "
                      "los detalles quedan en la carpeta de registros."),
    "aviso_brazo_alto": "Tiene el brazo muy levantado. Apoye el codo: se cansará menos.",
    "aviso_descanso": "Lleva {n} minutos usando las manos. Baje los brazos y descanse un minuto.",
    "aviso_perfil": "Perfil: {nombre}",
    "aviso_sugerir_3d": "Este programa es 3D. ¿Pasar a Mouse Control 3D? (Ctrl+Alt+D)",
    "aviso_modo_2D": "Mouse Control 2D (en pausa).",
    "aviso_modo_3D": "Modo 3D: cierre el puño y muévalo para girar el modelo.",
    "aviso_modo_3D_dos": "Modo 3D: cierre las dos manos y gírelas como un volante para girar el modelo.",
    "aviso_dibujo_fino_si": "Modo dibujo fino: el puntero se mueve más suave.",
    "aviso_dibujo_fino_no": "Modo dibujo fino apagado.",
    "aviso_config": "Se restableció la configuración.",
    "aviso_ya_abierto": "Lycan Mouse Control ya está abierto.",
    "aviso_simulado": "MODO ENSAYO: el ratón no hará nada (solo se muestra lo que haría).",
    "aviso_cerrar": "Se cerrará Lycan Mouse Control y el ratón volverá a funcionar normal.",

    # ---- botones y menú ----
    "btn_pausar": "⏸ Pausar",
    "btn_activar": "▶ Activar",
    "btn_modo": "2D/3D",
    "btn_opciones": "⚙",
    "btn_ayuda": "?",
    "btn_mini": "—",
    "menu_practicar": "Volver a practicar señas",
    "menu_opciones": "Opciones…",
    "menu_chuleta": "Chuleta de señas",
    "menu_registros": "Abrir carpeta de registros",
    "menu_admin": "Reiniciar como administrador",
    "menu_ver_todo": "Ver todo (según el programa)",
    "menu_salir": "Salir (Ctrl+Alt+X)",

    # ---- modos ----
    "modo_2D": "Mouse Control 2D",
    "modo_3D": "Mouse Control 3D",

    # ---- ayudas de cada seña (chuleta) ----
    "chuleta_titulo": "Señas de {modo}",
    "ch_activar": "Índice y corazón juntos, una vez: activar",
    "ch_pausar": "La misma seña dos veces seguidas: pausar",
    "ch_mover": "Dedo índice: mover el puntero",
    "ch_clic": "Pellizco pulgar + índice: clic izquierdo",
    "ch_arrastrar": "Pellizco sostenido: arrastrar",
    "ch_derecho": "Puño cerrado: clic derecho",
    "ch_zoom": "Acercar o alejar: con pellizco en las dos manos, sepárelas o júntelas.",
    "ch_desplazar": "Mover el dibujo: haga pellizco con las dos manos y muévalas juntas.",
    "ch_desplazar_3D": "Mover el modelo: haga pellizco con las dos manos y muévalas juntas.",
    "ch_puno_3d": ("En 3D el puño quieto espera un poco más antes del clic derecho, para alcanzar a "
                   "girar si lo mueve."),
    "ch_puno_3d_dos": ("En 3D el puño de una mano espera un poco más antes del clic derecho, para no "
                       "confundirlo con el agarre de las dos manos."),
    "ch_girar": ("Girar el modelo: cierre las dos manos como si agarrara un volante y gírelas. "
                 "Abra las manos para soltar."),
    "ch_zoom1": "Pellizco pulgar + corazón y subir o bajar la mano: acercar o alejar (variante)",
    "ch_atajos": ("{pausar} pausar o activar · {salir} salir · {ventana} mostrar la ventana · "
                  "{modo} cambiar 2D/3D · {dibujo_fino} dibujo fino"),

    # ---- temas de ayuda ----
    "tema_postura": ("Postura: apoye el codo en la mesa y mueva la muñeca. La mano a 40-60 cm de la cámara. "
                     "Pausar es como levantar el ratón para reacomodarlo."),
    "tema_luz": ("Poca luz: encienda una lámpara frente a usted, no detrás. Si hay una ventana detrás, "
                 "la cámara ve su mano oscura."),
    "tema_larga": "La seña de activar sostenida más de 1.5 segundos no cuenta: hágala y suéltela.",
    "tema_admin": ("Si el programa de dibujo se abrió como administrador, Windows no deja que otro programa "
                   "lo maneje. Abra Lycan Mouse Control también como administrador (menú ?)."),
    "tema_freecad": ("FreeCAD: en Editar > Preferencias > Visualización > Navegación, elija el estilo "
                     "«Blender». Así girar y mover funcionan mejor. Con el programa en «Automático», "
                     "Lycan Mouse Control nota ese cambio solo; si eligió el programa a mano, escoja "
                     "«FreeCAD (estilo Blender)» en ⚙ > Programa."),
    "tema_presionado": ("Si algo quedó presionado (por ejemplo, después de cerrar el programa a la fuerza): "
                        "presione y suelte Shift y el botón de la rueda del ratón."),
    "tema_complemento": ("Lycan Mouse Control es un complemento del ratón: sirve para girar en 3D, "
                         "presentar o descansar la mano. Para puntos exactos use el zoom y el enganche del programa."),

    # ---- asistente ----
    "as_titulo": "Primeros pasos — Lycan Mouse Control",
    "as_paso": "Paso {n} de {m}",
    "as_ensayo": "No se preocupe: mientras practica, el ratón no hará nada.",
    "as_atras": "Atrás",
    "as_repetir": "Repetir",
    "as_saltar": "Saltar esta seña",
    "as_siguiente": "Siguiente",
    "as_terminar": "Terminar",
    "as_logrado": "¡Bien! {k} de {n}",
    "as_listo": "Listo. Puede volver a este asistente desde el menú ? > Volver a practicar señas.",
    "as_bienvenida": ("Bienvenido. En unos minutos le enseñamos a manejar el puntero con las manos. "
                      "Puede saltar cualquier paso."),
    "as_postura": ("Apoye el codo en la mesa y ponga la mano a unos 40 a 60 cm de la cámara, "
                   "con la palma hacia la pantalla."),
    "as_camara": "Revisemos la cámara y la luz. Debe ver su mano en el recuadro.",
    "as_mano": "¿Con qué mano va a mover el puntero?",
    "as_mano_der": "Derecha",
    "as_mano_izq": "Izquierda",
    "as_calibrar": "Ajuste a su mano (unos 40 segundos). Siga las instrucciones.",
    "as_activar": ("Junte el dedo índice y el corazón, estirados y pegados, como diciendo «dos». "
                   "Sosténgalos un momento (un cuarto de segundo)."),
    "as_mover": "Mueva el dedo índice hasta cada círculo.",
    "as_clic": ("Junte la punta del pulgar con la del índice y suéltelas: eso es un clic. Hágalo 3 veces. "
                "Después junte los dedos, mueva la mano y suéltelos: eso es arrastrar."),
    "as_derecho": "Cierre la mano en puño un momento y ábrala: eso es el clic derecho.",
    "as_zoom": "Acercar o alejar: con pellizco en las dos manos, sepárelas o júntelas.",
    "as_pausar": "Para pausar, haga la seña de activar dos veces seguidas.",
    "as_girar": ("Girar el modelo: cierre las dos manos como si agarrara un volante y gírelas. "
                 "Abra las manos para soltar."),
    "as_desplazar": "Mover el dibujo: haga pellizco con las dos manos y muévalas juntas.",
    "as_desplazar_3D": "Mover el modelo: haga pellizco con las dos manos y muévalas juntas.",
    "as_soltar": "Abra las manos para soltar.",
    "as_soltar_un_puno": "Abra la mano para soltar.",
    "as_pista": "Pista: {texto}",
    "as_reactivar": ("Está en pausa: haga la seña de activar (índice y corazón juntos) para seguir "
                     "practicando."),
    "as_sin_imagen": ("Todavía no llega imagen de la cámara. Espere unos segundos; si sigue así, revise que "
                      "esté conectada y que ningún otro programa la use."),
    "pista_activar": "estire índice y corazón bien pegados y doble los otros dos dedos.",
    "pista_clic": "acerque bien las puntas del pulgar y del índice, hasta tocarse.",
    "pista_derecho": "cierre todos los dedos y deje el pulgar por encima.",
    "pista_zoom": "muestre las dos manos en pellizco, separadas, y luego sepárelas más.",
    "pista_mover": "mueva la mano despacio, con el codo apoyado.",
    "pista_girar": "las dos manos en puño, bien separadas, y gírelas como un volante.",
    "pista_general": "acerque la mano a la cámara y revise que haya buena luz.",

    # ---- calibración ----
    "cal_luz_poca": "Hay poca luz: encienda una lámpara frente a usted, no detrás.",
    "cal_luz_mucha": "Hay demasiada luz detrás de usted (ventana).",
    "cal_luz_ok": "La luz está bien.",
    "cal_cerca": "Acérquese un poco.",
    "cal_lejos": "Aléjese un poco.",
    "cal_distancia_ok": "La distancia está bien.",
    "cal_zona": ("Con el codo apoyado, mueva el dedo índice por todo el espacio que le resulte cómodo "
                 "durante 5 segundos."),
    "cal_abierta": "Abra la mano",
    "cal_puno": "Cierre el puño",
    "cal_pellizco": "Junte pulgar e índice",
    "cal_juntos": "Junte índice y corazón",
    "cal_v": "Haga la V",
    "cal_repetir": "Las dos posturas se parecen mucho ({medida}). Repita, marcando más la diferencia.",
    "cal_ok": "Ajuste guardado.",
    "cal_sin_mano": "No veo su mano. Póngala dentro del recuadro.",

    # ---- opciones ----
    "op_titulo": "Opciones — Lycan Mouse Control",
    "op_general": "General",
    "op_puntero": "Puntero",
    "op_senas": "Señas",
    "op_comodidad": "Comodidad",
    "op_atajos": "Atajos",
    "op_modo": "Modo",
    "op_mano": "Mano principal",
    "op_camara": "Cámara",
    "op_camara_invalida": "Escriba un número de 0 a 3.",
    "op_resolucion": "Resolución",
    "op_res_640": "640 x 480 (recomendada)",
    "op_res_320": "320 x 240 (rápida)",
    "op_monitor": "Pantalla de trabajo",
    "op_monitor_todo": "Todo el escritorio",
    "op_monitor_principal": "Principal",
    "op_inicio": "Abrir al encender el computador",
    "op_estable_rapido": "Más estable ↔ Más ágil",
    "op_tam_zona": "Tamaño de la zona de la mano (%)",
    "op_velocidad": "Velocidad del puntero",
    "op_velocidad_giro": "Velocidad de giro 3D",
    "op_lento": "Lento",
    "op_rapido": "Rápido",
    "op_relativo": "Modo relativo (como un touchpad)",
    "op_fino": "Modo dibujo fino",
    "op_sensibilidad": "Sensibilidad",
    "op_tiempo_confirmar": "Tiempo para confirmar el puño (ms)",
    "op_doble": "Tiempo para la doble seña (ms)",
    "op_invertir": "Invertir acercar/alejar",
    "op_zoom1": "Zoom con una mano (pulgar + corazón)",
    "op_desplazar": "Mover el dibujo con dos pellizcos",
    "op_codo": "Modo codo apoyado",
    "op_pausa_sin_mano": "Pausar sin manos (segundos)",
    "op_descanso": "Descanso cada (min, 0 = nunca)",
    "op_sonidos": "Sonidos",
    "op_aviso_cursor": "Aviso junto al puntero",
    "op_opacidad": "Opacidad de la ventana (%)",
    "op_atajo_pausar": "Pausar / activar",
    "op_atajo_salir": "Salir",
    "op_atajo_ventana": "Mostrar / ocultar la ventana",
    "op_atajo_modo": "Cambiar 2D / 3D",
    "op_atajo_fino": "Modo dibujo fino",
    "op_atajo_restablecer": "Restablecer",
    "op_atajo_capturar": "Haga clic y presione la combinación…",
    "op_perfil": "Programa",
    "op_perfil_auto": "Automático (según el programa)",
    "op_fabrica": "Volver a los valores de fábrica",
    "op_practicar": "Volver a practicar señas",
    "op_guardar": "Guardar",
    "op_cancelar": "Cancelar",
    "op_atajo_invalido": "El atajo «{texto}» no sirve: {motivo}",
    "op_atajo_caracter": "El atajo {texto} escribe «{car}» en su teclado. Elija otro.",
    "op_atajo_repetido": "El atajo {texto} ya está asignado a «{funcion}». Elija otro para «{otra}».",
    "op_fabrica_pregunta": "¿Volver a los valores de fábrica?\n\nSe borrarán su ajuste de mano (calibración) "
                           "y sus opciones. Los atajos se conservan.\n\nNada queda guardado hasta que "
                           "pulse «Guardar»; con «Cancelar» todo vuelve como estaba.",

    # --- 1.0.2 paquete A ---
    # señas y ayuda
    "sena_PELLIZCO_ANULAR": "PULGAR + ANULAR",
    "sena_PELLIZCO_MENIQUE": "PULGAR + MEÑIQUE",
    "sena_menique_doble_clic": "DOBLE CLIC",
    "sena_menique_clic_derecho": "CLIC DERECHO",
    "sena_menique_clic_medio": "CLIC DEL MEDIO",
    "sena_menique_enter": "ENTER",
    "sena_menique_esc": "ESC",
    "sena_menique_suprimir": "SUPRIMIR",
    "sena_menique_deshacer": "DESHACER",
    "ch_anular": "Junte el pulgar con el anular: es un clic. Sosténgalo para arrastrar. El índice que apunta no se mueve.",
    "ch_menique": "Junte el pulgar con el meñique: hace la acción que usted escogió (de fábrica, doble clic).",
    "ch_menique_accion": "Junte el pulgar con el meñique: {accion}. Se cambia en ⚙ > Clic.",
    "tema_tecla": ("Clic con tecla o pedal: apriete la tecla para hacer clic y sosténgala para arrastrar. "
                   "En pausa la tecla funciona normal. Mientras el control está activo, esa tecla no escribe. "
                   "Si usa «Teclas del mouse» de Windows, apáguelas."),
    # Opciones, pestaña "Clic"
    "op_clic": "Clic",
    "op_clic_indice": "Clic con pulgar + índice",
    "ay_clic_indice": "El clic de siempre. Apáguelo si el puntero se le corre al pellizcar.",
    "op_clic_anular": "Clic con pulgar + anular",
    "ay_clic_anular": "El índice queda quieto y el clic cae donde apunta.",
    "op_menique": "Pulgar + meñique hace",
    "ay_menique": "Escoja qué pasa al juntar el pulgar con el meñique.",
    "mq_doble_clic": "Doble clic",
    "mq_clic_derecho": "Clic derecho",
    "mq_clic_medio": "Clic del medio",
    "mq_enter": "Enter",
    "mq_esc": "Esc",
    "mq_suprimir": "Suprimir",
    "mq_deshacer": "Deshacer (Ctrl+Z)",
    "mq_nada": "Nada",
    "op_tecla_activa": "Clic con una tecla o pedal",
    "ay_tecla_activa": "Sostener la tecla = botón abajo. Un toque = clic. Dos toques = doble clic.",
    "op_tecla_nombre": "Tecla de clic: {nombre}",
    "op_tecla_numerico": "¿Su teclado tiene números a la derecha?",
    "op_si": "Sí",
    "op_no": "No",
    "op_cambiar_tecla": "Cambiar tecla",
    "op_grabando": "Apriete ahora la tecla o el pedal que quiere usar… (Esc para cancelar)",
    "op_grabar_cancelada": "No se cambió la tecla.",
    "op_tecla_con_mod": "Suelte Ctrl, Alt o Windows y apriete solo la tecla que quiere usar.",
    "op_tecla_comun": "Ojo: mientras el control esté activo, «{nombre}» no escribirá.",
    "ay_tecla_numerico": ("Sí: se usa el 5 de los números de la derecha. No: apriete la tecla o el pedal "
                          "que quiere usar."),
    "op_sin_clic": ("Ojo: con los dos pellizcos y la tecla apagados no le queda clic izquierdo. "
                    "Prenda al menos uno."),
    "op_tecla_grabada": "Listo: la tecla es {nombre}.",
    "op_tecla_no_sirve": "Esa tecla no sirve (Ctrl, Shift, Alt o Windows). Escoja otra.",
    "op_tecla_sin_gancho": "El clic con tecla no está disponible ahora. Cierre y vuelva a abrir el programa.",
    "ay_tecla_aviso": ("Mientras el control está activo, esa tecla no escribe. Si usa «Teclas del mouse» de "
                       "Windows, apáguelas."),
    # asistente
    "as_tecla": "También puede hacer clic con una tecla o un pedal. ¿Su teclado tiene números a la derecha?",
    "as_tecla_si": "Use el 5 de los números de la derecha. Apriételo 2 veces para practicar: cada toque es un clic.",
    "as_tecla_no": ("Apriete la tecla que quiere usar (o pise el pedal). Mejor una que la otra mano alcance "
                    "fácil. (Esc para cancelar)"),
    "as_tecla_saltar": "No quiero clic con tecla",
    "as_tecla_listo": "Listo: la tecla es {nombre}. Apriétela 2 veces para practicar: cada toque es un clic.",
    "pista_tecla": "apriete la tecla: cada toque es un clic.",
    "as_clic_anular": ("Ahora junte el pulgar con el anular. El índice queda quieto y el clic no se corre. "
                       "Haga 2 clics."),
    "pista_clic_anular": "toque el pulgar con el dedo anular.",
    # avisos
    "aviso_tecla_suelta": "Se soltó el clic: la tecla parecía pegada.",
    "aviso_gancho_perdido": "Windows apagó el clic con tecla. Ya se volvió a prender.",
    "aviso_menique": "Meñique: {accion}",
    "aviso_tecla_nueva": "Nuevo: el 5 del teclado numérico hace clic. Se cambia o apaga en ⚙ > Clic.",

    # --- 1.0.2 paquete B ---
    "sena_lanzar": "LANZAR",
    "sena_despiezar": "DESPIEZAR",
    "sena_armar": "ARMAR",
    "ch_girar_un_puno": ("Cierre el puño y muévalo: el modelo gira siguiendo la mano. Abra la mano (o apunte "
                         "con el índice) para soltar. Puño quieto = clic derecho."),
    "ch_lanzar": ("Suelte el puño mientras lo mueve rápido: el modelo sigue girando y frena solo. Cierre el "
                  "puño para atraparlo."),
    "ch_golpe": "Abra la mano de golpe = despiezar. Ciérrela de golpe = armar. Solo si el programa tiene atajo.",
    # Opciones, pestaña "Girar"
    "op_girar": "Girar",
    "op_girar_con": "Girar el modelo con",
    "gi_un_puno": "Un puño",
    "gi_dos_punos": "Dos puños",
    "gi_ambos": "Los dos",
    "ay_girar_con": ("Un puño: cerrar y mover. Dos puños: como un volante (lo de antes). Los dos: sirven "
                     "ambos."),
    "op_k_un_puno": "Extra para un puño (además de la Velocidad de giro 3D)",
    "ay_k_un_puno": ("Se suma a la «Velocidad de giro 3D» de la pestaña Puntero, solo para el giro con un "
                     "puño. Más alto: el modelo gira más con menos movimiento."),
    "op_inercia": "Lanzar el modelo (sigue girando)",
    "ay_inercia": ("Si suelta moviendo rápido, el modelo sigue girando. Para frenarlo: cierre el puño, saque la "
                   "mano o apriete una tecla. Solo con el giro de un puño (o «Los dos»)."),
    "op_friccion": "Frena rápido ↔ Sigue girando",
    "op_golpe": "Abrir / cerrar la mano de golpe",
    "op_programa_atajos": "Atajos para el programa",
    "op_abrir_golpe": "Abrir de golpe manda",
    "op_cerrar_golpe": "Cerrar de golpe manda",
    "ay_atajo": "Escriba el atajo, por ejemplo Ctrl+Shift+G. Vacío = no hace nada.",
    "ay_atajo_barrido": "Escriba la tecla, por ejemplo Derecha o Alt+Derecha. Vacío = no hace nada.",
    "op_atajo_propio": "Ese atajo ya lo usa Lycan Mouse Control ({funcion}). Escoja otro.",
    "ay_edwin3d_desdoblar": ("En EDWIN CNC 3D, «Desdoblar caras» no tiene atajo: póngale uno en Preferencias ▸ "
                             "Atajos de teclado (por ejemplo Ctrl+Alt+U) y escriba el mismo aquí. En SketchUp "
                             "sirven Ctrl+Shift+G (despiezar) y Ctrl+G (armar)."),
    "op_atajo_malo": "Ese atajo no se entiende. Ejemplos: Enter, Ctrl+Z, Alt+Izquierda.",
    # asistente (paso «girar» con un puño)
    "as_girar_un_puno": "Cierre el puño y muévalo despacio: el modelo gira. Abra la mano para soltar.",
    "pista_girar_un_puno": "puño cerrado y mover. Quieto es clic derecho.",
    # avisos
    "aviso_inercia": "El modelo sigue girando. Cierre el puño para atraparlo.",
    "aviso_frenado": "Modelo detenido",
    "aviso_golpe_abrir": "Despiezar: {atajo}",
    "aviso_golpe_cerrar": "Armar: {atajo}",

    # --- 1.0.2 paquete C ---
    "estado_PASANDO_PAGINA": "● PASANDO PÁGINA",
    "ayuda_PASANDO_PAGINA": "Suba o baje la mano. Cierre la mano o apunte con el índice para terminar.",
    "sena_pasando": "PASANDO PÁGINA",
    "sena_scroll_fin": "LISTO",
    "sena_barrido_der": "SIGUIENTE",
    "sena_barrido_izq": "ANTERIOR",
    "ch_palma": ("Muestre la palma abierta y quieta un momento, con los dedos separados: suena un aviso o "
                 "se ve PASANDO PÁGINA. Suba o baje la mano para pasar la página. En los programas de diseño "
                 "hace zoom. Cierre la mano o apunte con el índice para terminar."),
    "ch_barrido": ("Pase la palma abierta, con los dedos separados, rápido a la derecha o a la izquierda: "
                   "siguiente o anterior. En programas de diseño no hace nada, salvo que le ponga una tecla "
                   "en ⚙ > Palma."),
    "ch_mano_baja": "Trabaje con la mano baja, cerca del teclado. Apoye la muñeca y no levante el brazo.",
    # Opciones, pestaña "Palma"
    "op_palma": "Palma",
    "op_scroll_palma": "Pasar página con la palma",
    "ay_scroll_palma": ("Palma abierta y quieta medio segundo, y luego subir o bajar la mano. En programas de "
                        "diseño hace zoom."),
    "op_scroll_inercia": "La página sigue un poco al soltar",
    "op_scroll_friccion": "Para rápido ↔ Sigue andando",
    "op_scroll_invertir": "Al revés: subir la mano sube por la página, como la rueda del ratón",
    "op_barrido": "Barrido a los lados",
    "ay_barrido": ("Palma abierta con los dedos separados, pasada rápido: siguiente o anterior. Escoja la "
                   "tecla por programa."),
    "op_barrido_der": "Barrido a la derecha manda",
    "op_barrido_izq": "Barrido a la izquierda manda",
    # Opciones, pestaña "Comodidad"
    "op_mano_baja": "Mano baja, cerca del teclado",
    "ay_mano_baja": ("Menos cansancio en jornadas largas. Después vuelva a calibrar: botón «Volver a "
                     "practicar señas» (abajo)."),
    # asistente
    "as_postura_elegir": "¿Cómo quiere trabajar?",
    "as_postura_neutro": "Escoja cómo va a trabajar con la mano.",
    "as_postura_ok_apoyado": "Elegido: brazo apoyado.",
    "as_postura_ok_baja": "Elegido: mano baja.",
    "as_postura_apoyado": "Brazo apoyado",
    "as_postura_baja": "Mano baja, cerca del teclado",
    "as_consejo_baja": ("Apoye la muñeca delante del teclado, con la palma hacia la pantalla. Incline la pantalla "
                        "hacia atrás (o la cámara hacia abajo) hasta ver la mano entera sobre el teclado. "
                        "Descanse cada rato."),
    "as_scroll": ("Muestre la palma abierta, con los dedos separados, y quieta hasta oír el aviso (o ver "
                  "PASANDO PÁGINA). Luego suba y baje la mano."),
    "pista_scroll": "dedos estirados y separados, mano quieta.",
    # calibración
    "cal_incline": "No se ve su muñeca. Incline la pantalla hacia atrás o la cámara hacia abajo.",
    "cal_incline_seguir": "Luego siga moviendo el índice por la zona.",
    "cal_mano_baja_ok": "Bien: se ve la mano entera sobre el teclado.",
    # avisos
    "aviso_scroll": "Pasando página: suba o baje la mano",
    "aviso_scroll_fin": "Listo",
    "aviso_barrido_der": "Siguiente",
    "aviso_barrido_izq": "Anterior",
    "aviso_baje_mano": "Baje la mano hasta la zona del teclado",
}

PALABRAS_PROHIBIDAS = ("landmark", "threshold", "frame", " hz", "hz ")


def t(clave: str, **kw) -> str:
    """Texto por clave; si falta, devuelve la clave (nunca rompe la interfaz)."""
    txt = TXT.get(clave, clave)
    try:
        return txt.format(**kw) if kw else txt
    except (KeyError, IndexError, ValueError):
        return txt


def texto_aviso(aviso) -> str:
    """Convierte un Aviso(clave, texto) en el mensaje para la ventana."""
    clave, extra = aviso.clave, aviso.texto
    if clave == "perfil":
        return t("aviso_perfil", nombre=extra)
    if clave == "descanso":
        return t("aviso_descanso", n=extra or "20")
    if clave == "modo":
        return t("aviso_modo_" + (extra or "2D"))
    if clave == "camara_ocupada":
        return t("aviso_camara_ocupada")
    if clave == "dibujo_fino":
        return t("aviso_dibujo_fino_" + (extra or "no"))
    if clave == "sugerir_3d":
        return t("aviso_sugerir_3d")
    if clave == "menique":
        return t("aviso_menique", accion=t("mq_" + (extra or "nada")))
    if clave in ("golpe_abrir", "golpe_cerrar"):              # 1.0.2 paquete B
        return t("aviso_" + clave, atajo=extra or "")
    return TXT.get("aviso_" + clave, extra or clave)
