# Solicitud de validación clínica: reglas de alarma (borrador PROVISIONAL)

*Fecha de envío: ____ · Catálogo `knowledge/alarm_rules.json` versión 0.5.0 · Generado el 2026-10-10*

**Para:** Dra. Dolly Magnolia González Hoyos y equipo clínico del proyecto.
**De:** equipo de desarrollo (Nicolas Castillo Galeano).

## Contexto
El asistente de teleorientación detecta **signos de alarma con reglas fijas**: no los decide la inteligencia artificial. Cuando un mensaje coincide con una regla, el asistente responde con un **mensaje fijo** (abajo) en lugar de una respuesta generada.

Este borrador lo redactó el equipo con apoyo de IA a partir de signos de alarma públicos (MinSalud, OPS, AIEPI). **No se usará con usuarios reales hasta que ustedes lo validen.** Para cada regla les pedimos:
1. Marcar **Aprobar**, **Corregir** o **Eliminar**.
2. Indicar la **fuente** clínica que la respalda (guía, resolución, protocolo).
3. Revisar si la **severidad** es correcta.
4. Agregar **frases** con las que la comunidad describiría ese signo (expresiones locales) y frases que **no** deberían activarla.
5. Señalar los **signos que faltan**.

**Severidades:**
- 🚨 *Urgencia inmediata*: solo se muestra el mensaje fijo de ir a urgencias o llamar al 123.
- ⚠️ *Consulta prioritaria*: el mensaje fijo de pedir cita pronto, seguido de la orientación del asistente.

## Mensajes fijos
- **`urgencia_embarazo`:** 🚨 Lo que describes puede ser un signo de alarma en el embarazo o después del parto. Acude de inmediato al servicio de urgencias más cercano o llama a la línea de emergencias 123. No esperes a que pase solo y, si puedes, ve acompañada.
  - [ ] Aprobar · [ ] Corregir: ________________________
- **`urgencia_bebe`:** 🚨 Lo que describes puede ser un signo de peligro en el bebé o en el niño. Llévalo de inmediato al servicio de urgencias más cercano o llama a la línea de emergencias 123. No le des medicamentos por tu cuenta mientras tanto.
  - [ ] Aprobar · [ ] Corregir: ________________________
- **`urgencia_cardio`:** 🚨 Lo que describes puede ser una emergencia del corazón o un accidente cerebrovascular. Llama ya a la línea de emergencias 123 o acude al servicio de urgencias más cercano. Si es posible, no vayas solo y no manejes.
  - [ ] Aprobar · [ ] Corregir: ________________________
- **`urgencia_general`:** 🚨 Lo que describes puede ser una emergencia. Acude de inmediato al servicio de urgencias más cercano o llama a la línea de emergencias 123.
  - [ ] Aprobar · [ ] Corregir: ________________________
- **`prioritaria_presion`:** ⚠️ Es importante que un profesional de salud revise la presión arterial pronto. Pide una cita prioritaria en tu EPS o centro de salud en los próximos días. Si aparece dolor en el pecho, dolor de cabeza muy fuerte, dificultad para hablar o debilidad en un lado del cuerpo, acude de inmediato a urgencias o llama al 123.
  - [ ] Aprobar · [ ] Corregir: ________________________

## Reglas

### RN-MI-01: Sangrado vaginal en el embarazo o el posparto
- **Población:** gestante/posparto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “Estoy embarazada de 5 meses y estoy sangrando”; “tengo 30 semanas de embarazo y me salió sangre”; “me está saliendo como agüita con sangre por abajo”; “sangrado vaginal en el embarazo”; “di a luz hace una semana y tengo una hemorragia”; “me está saliendo como agüita rosada por abajo, tengo 7 meses”; “secreción rosada por la vagina en el embarazo”; “secreción vaginal rosada”; “flujo rosado en el embarazo de 7 meses”; “salida de líquido rosado por la vagina en el embarazo”
- **Frases que NO deben activarla:** “me sangra la nariz”; “estoy embarazada y tengo acidez”; “estoy embarazada y me compré ropa rosada”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-02: Dolor de cabeza intenso o alteraciones visuales en el embarazo
- **Población:** gestante/posparto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “estoy embarazada y tengo un dolor de cabeza muy fuerte”; “tengo 7 meses de embarazo y veo lucecitas”; “cefalea intensa en el embarazo”; “estoy embarazada, me duele la cabeza horrible y tengo visión borrosa”; “tengo 7 meses y me duele mucho la cabeza y veo como estrellitas”; “estoy embarazada y me duele muchísimo la cabeza”; “tengo 30 semanas y estoy viendo como puntitos”; “estoy embarazada y se me nubla la vista”
- **Frases que NO deben activarla:** “estoy embarazada y me duele un poquito la cabeza”; “tengo dolor de cabeza fuerte por el trabajo”; “estoy embarazada y me duele la cabeza cuando no duermo bien”; “tengo 7 meses y veo mucha televisión”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-03: Convulsiones
- **Población:** gestante/posparto/niños · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_general`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal); Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi bebé está convulsionando”; “tuvo una convulsión hace un rato”; “convulsiones en gestante”; “se puso rígido y temblaba todo”
- **Frases que NO deben activarla:** “tengo un temblor en las manos por el frío”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-04: Hinchazón de cara, manos o pies de aparición reciente en el embarazo
- **Población:** gestante/posparto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “estoy embarazada y se me hinchó mucho la cara”; “tengo 8 meses de embarazo y las manos muy hinchadas”; “edema facial en el embarazo”
- **Frases que NO deben activarla:** “se me hincharon los pies después de caminar”; “estoy embarazada y tengo los pies un poco hinchados”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-05: Salida de líquido por la vagina (ruptura de membranas)
- **Población:** gestante · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “creo que se me rompió la fuente”; “estoy embarazada y me salió mucho líquido”; “ruptura de membranas”; “salida de líquido amniótico”; “estoy de 30 semanas y me sale agua”; “salida de líquido por la vagina en el embarazo”
- **Frases que NO deben activarla:** “tomo mucha agua durante el embarazo”; “estoy embarazada y me sale mucha saliva”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-06: Disminución o ausencia de movimientos fetales
- **Población:** gestante · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “el bebé no se mueve desde ayer”; “no lo siento moverse como antes”; “disminución de movimientos fetales”; “mi bebé se mueve menos que de costumbre”; “siento que el bebé ya no patea igual que antes, tengo 8 meses”; “disminución de los movimientos del bebé en el embarazo de 8 meses”; “el bebé patea menos que antes”; “ya no lo siento patear”
- **Frases que NO deben activarla:** “el bebé se mueve mucho en las noches”; “el bebé patea mucho en las noches”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-07: Fiebre en el embarazo o el posparto
- **Población:** gestante/posparto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “estoy embarazada y tengo fiebre”; “tengo calentura y estoy en el posparto”; “fiebre en el embarazo”
- **Frases que NO deben activarla:** “mi esposo tiene fiebre”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-08: Contracciones o dolor tipo parto antes de las 37 semanas
- **Población:** gestante · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_embarazo`
- **Fuente sugerida:** Pendiente: MinSalud, signos de alarma en el embarazo y el posparto (RIAS materno-perinatal)
- **Frases que la activan (ejemplos):** “tengo 30 semanas y tengo contracciones”; “tengo 7 meses y se me pone dura la barriga a cada rato”; “contracciones prematuras”; “amenaza de parto prematuro”
- **Frases que NO deben activarla:** “tengo 39 semanas y empezaron las contracciones”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-09: No puede comer, beber o tomar el pecho
- **Población:** recién nacido/menor de 5 años · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi bebé no quiere comer nada”; “el recién nacido no recibe el pecho”; “no quiere tomar el seno desde la mañana”; “rechazo del alimento en el lactante”
- **Frases que NO deben activarla:** “mi hijo de 10 años no quiere comer verduras”; “mi bebé come muy bien”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-10: Vomita todo lo que come o bebe
- **Población:** menor de 5 años · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “el niño vomita todo lo que come”; “todo lo devuelve, no retiene nada”; “vómito persistente”
- **Frases que NO deben activarla:** “vomitó una vez después del almuerzo”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-11: Letárgico, muy decaído o no despierta
- **Población:** recién nacido/menor de 5 años · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi bebé está muy decaído y no se despierta”; “la niña no reacciona”; “letargia en el lactante”
- **Frases que NO deben activarla:** “mi bebé duerme mucho en la tarde”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-12: Respira rápido o con dificultad
- **Población:** recién nacido/menor de 5 años · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi bebé respira muy rápido”; “al niño se le hunden las costillas al respirar”; “dificultad respiratoria en el bebé”
- **Frases que NO deben activarla:** “mi bebé respira tranquilo”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-13: Fiebre o temperatura baja en el recién nacido
- **Población:** recién nacido · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi recién nacido tiene fiebre”; “el bebé de 10 días está muy frío”; “fiebre en recién nacido”
- **Frases que NO deben activarla:** “el recién nacido está tranquilo y come bien”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-MI-14: Piel o labios muy amarillos o morados
- **Población:** recién nacido/menor de 5 años · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_bebe`
- **Fuente sugerida:** Pendiente: OPS/OMS AIEPI, signos generales de peligro en menores de 5 años
- **Frases que la activan (ejemplos):** “mi bebé está muy amarillo”; “el niño tiene los labios morados”; “ictericia en el recién nacido”
- **Frases que NO deben activarla:** “le compré un vestido amarillo a la bebé”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-01: Dolor u opresión en el pecho
- **Población:** adulto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_cardio`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “tengo un dolor muy fuerte en el pecho”; “siento como un peso en el pecho”; “me aprieta el pecho”; “dolor torácico opresivo”
- **Frases que NO deben activarla:** “me duele la espalda”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-02: Dificultad para respirar
- **Población:** adulto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_cardio`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “me falta el aire”; “mi papá no puede respirar bien”; “dificultad para respirar”
- **Frases que NO deben activarla:** “quiero respirar aire puro en el campo”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-03: Signos de accidente cerebrovascular (cara caída, debilidad de un lado, habla alterada, cefalea súbita)
- **Población:** adulto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_cardio`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “a mi papá se le torció la boca”; “mi mamá está hablando enredado”; “no puede mover el brazo derecho”; “creo que le dio un derrame cerebral”; “signos de ACV”
- **Frases que NO deben activarla:** “me duele el brazo de cargar al bebé”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-04: Desmayo o pérdida del conocimiento
- **Población:** adulto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_cardio`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “mi abuela se desmayó”; “perdió el conocimiento por unos segundos”; “síncope”
- **Frases que NO deben activarla:** “me siento un poco cansado”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-05: Presión arterial muy alta (≥ 180) o presión alta con síntomas
- **Población:** adulto · **Severidad propuesta:** 🚨 Urgencia inmediata · **Mensaje:** `urgencia_cardio`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “tengo la presión en 190 sobre 110”; “la tensión me dio 200”; “tengo la presión muy alta y me duele la cabeza”; “crisis hipertensiva”
- **Frases que NO deben activarla:** “tengo la presión en 120 sobre 80”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

### RN-CV-06: Presión arterial alta sin síntomas de alarma
- **Población:** adulto · **Severidad propuesta:** ⚠️ Consulta prioritaria · **Mensaje:** `prioritaria_presion`
- **Fuente sugerida:** Pendiente: OPS HEARTS / MinSalud, signos de alarma cardiovascular y ACV
- **Frases que la activan (ejemplos):** “mi papá tiene la presión alta”; “tengo hipertensión”; “me tomaron la presión y salió en 150”
- **Frases que NO deben activarla:** “tengo la presión normal”; “tengo la presión baja”
- [ ] Aprobar · [ ] Corregir · [ ] Eliminar
- Fuente clínica: ______________________ · Severidad correcta: [ ] Sí [ ] No → ______
- Otras frases de la comunidad: ____________________________________________

## Signos de alarma que faltan
| Signo | Población | Severidad | Fuente | Frases de ejemplo |
|---|---|---|---|---|
| | | | | |

## Limitaciones conocidas (para su conocimiento)
- El sistema **no interpreta negaciones**: “no tengo sangrado” también activa la alerta. Se prefiere alertar de más que dejar pasar un caso.
- Mientras no tengamos las rutas por municipio (DTS Caldas), el mensaje fijo remite a urgencias o a la línea 123 de forma general.
- Además del mensaje de la persona, se revisan los síntomas que el asistente identificó en la conversación. Cada alerta registra si la detectó la regla sobre el texto original o sobre lo identificado por el asistente.

## Pregunta para el equipo clínico
Hoy, una **pregunta educativa** que menciona un signo de alarma (p. ej., “¿por qué se pueden dar secreciones rosadas en el embarazo?”) recibe el mismo mensaje de urgencia que un reporte real, porque muchas personas reportan sus síntomas en forma de pregunta (“¿es normal que me salga agüita rosada? tengo 7 meses”).
Propuesta (B-017): mantener siempre la alarma, pero si el asistente identifica que es una consulta general, mostrar un mensaje condicional (“Si esto le está pasando ahora a ti o a alguien, acude de inmediato a urgencias o llama al 123”) seguido de una explicación.
- [ ] De acuerdo con la propuesta · [ ] Mantener siempre solo el mensaje de urgencia · [ ] Otra: ______________________

### Pregunta 2: fiebre en un bebé que no es recién nacido
Hoy, la única regla de fiebre infantil es RN-MI-13 (*fiebre o temperatura baja en el recién nacido*). Si alguien escribe "mi bebé tiene fiebre" sin decir la edad, ninguna regla se activa y el asistente responde con la orientación de la base de conocimiento.
- ¿Debe haber una regla para la fiebre en menores de cierta edad (p. ej., < 3 meses) o con ciertos signos acompañantes? Edad límite: ______ · Signos: ______________________
- ¿El asistente debe preguntar la edad del bebé antes de orientar? [ ] Sí · [ ] No

### Pregunta 3: "no quiere comer" frente a "no puede comer"
En la comparación de modelos del 2026-10-12, varios modelos describieron "el bebé **no quiere** comer", y RN-MI-09 dice "**No puede** comer, beber o tomar el pecho". ¿Que un bebé no quiera comer debe activar la alerta, o solo cuando no puede? [ ] Ambos · [ ] Solo "no puede" · Comentario: ______________________

### Cambios de la versión 0.4.0 (implementados para la demostración; pendientes de aprobación)
Descripciones correctas que no activaban su regla por diferencias de redacción. Se ampliaron los patrones **sin cambiar el signo, la severidad ni el mensaje** de ninguna regla:

| Regla | Ahora también reconoce | Frases que NO deben activarla |
|---|---|---|
| RN-MI-02 | "la cabeza me va a estallar/explotar" en el embarazo | "la cabeza me va a estallar con tanto ruido" (sin embarazo) |
| RN-MI-03 | "ojos en blanco" con temblores o rigidez; "le dio un ataque y se puso rígida" | "le dio un ataque de tos" |
| RN-MI-10 | "vómito de todo lo que come"; "devuelve hasta el agua" | "el cajero me devuelve el cambio" |
| RN-MI-12 | "respira rápido / con dificultad" seguido de "bebé", "niño"… | — |
| RN-MI-13 | "fiebre en bebé de N días" (hasta 29); "bebé de N días… calientico" | "mi bebé de 3 meses tiene fiebre" |
| RN-MI-14 | "piel / ojos (muy) amarillos o morados" seguido de "bebé", "niño"… | "el bebé tiene una camiseta amarilla" |
| RN-CV-03 | "parálisis / debilidad / se le durmió" + "medio cuerpo / un lado del cuerpo" | "se me durmió el brazo por dormir encima" |
| RN-CV-06 | "hipertenso", "hipertensa" (antes solo "hipertensión") | "tengo la presión normal" |

- [ ] Aprobados · [ ] Aprobados con cambios: ______________________ · [ ] Rechazados

### Códigos y ejemplos coloquiales de la versión 0.5.0 (implementados para la demostración; pendientes de aprobación)
El asistente marca el **código** del signo que describe la persona y el sistema lo cruza de forma exacta con la regla (ADR 0012). Los ejemplos se le muestran al asistente para que reconozca el lenguaje cotidiano. Los generó la IA.

| Regla | Código | Signo | Ejemplos coloquiales |
|---|---|---|---|
| RN-MI-01 | `SANGRADO_VAGINAL_EMBARAZO_POSPARTO` | Sangrado vaginal en el embarazo o el posparto | me bajó sangre estando embarazada; manché de rojo y tengo 6 meses |
| RN-MI-02 | `CEFALEA_O_VISION_EMBARAZO` | Dolor de cabeza intenso o alteraciones visuales en el embarazo | con el embarazo me duele la cabeza durísimo; estoy embarazada y veo lucecitas |
| RN-MI-03 | `CONVULSIONES` | Convulsiones | tuvo una convulsión; se sacudía todo y no respondía |
| RN-MI-04 | `HINCHAZON_EMBARAZO` | Hinchazón de cara, manos o pies de aparición reciente en el embarazo | en el embarazo se me hincharon de repente los pies y la cara; tengo las manos hinchadas como un guante y estoy embarazada |
| RN-MI-05 | `SALIDA_LIQUIDO_VAGINAL` | Salida de líquido por la vagina (ruptura de membranas) | se me rompió la fuente; me sale agüita por abajo |
| RN-MI-06 | `MOVIMIENTOS_FETALES_DISMINUIDOS` | Disminución o ausencia de movimientos fetales | el bebé ya no patea; no siento al bebé moverse |
| RN-MI-07 | `FIEBRE_EMBARAZO_POSPARTO` | Fiebre en el embarazo o el posparto | estoy embarazada y tengo calentura; acabo de dar a luz y tengo fiebre |
| RN-MI-08 | `CONTRACCIONES_PRETERMINO` | Contracciones o dolor tipo parto antes de las 37 semanas | tengo 32 semanas y siento dolores como de parto; siento contracciones y aún no cumplo los 9 meses |
| RN-MI-09 | `NO_PUEDE_COMER_BEBER_LACTAR` | No puede comer, beber o tomar el pecho | el bebé no logra mamar; el niño no puede tragar nada |
| RN-MI-10 | `VOMITA_TODO` | Vomita todo lo que come o bebe | todo lo que le doy lo vomita; no retiene nada en el estómago |
| RN-MI-11 | `LETARGICO_NO_DESPIERTA` | Letárgico, muy decaído o no despierta | el bebé está muy flojito y no se despierta; está como ido, no responde |
| RN-MI-12 | `RESPIRA_RAPIDO_O_CON_DIFICULTAD` | Respira rápido o con dificultad | al bebé se le hunden las costillas; el niño respira agitado y con quejido |
| RN-MI-13 | `FIEBRE_O_HIPOTERMIA_RECIEN_NACIDO` | Fiebre o temperatura baja en el recién nacido | mi bebé de una semana tiene calentura; el recién nacido está muy frío |
| RN-MI-14 | `PIEL_LABIOS_AMARILLOS_O_MORADOS` | Piel o labios muy amarillos o morados | el bebé está amarillito; se le pusieron los labios morados |
| RN-CV-01 | `DOLOR_OPRESION_PECHO` | Dolor u opresión en el pecho | me aprieta el pecho; siento un peso en el pecho que se va al brazo |
| RN-CV-02 | `DIFICULTAD_RESPIRAR` | Dificultad para respirar | me ahogo; me falta el aire al caminar poquito |
| RN-CV-03 | `SIGNOS_ACV` | Signos de accidente cerebrovascular (cara caída, debilidad de un lado, habla alterada, cefalea súbita) | se le torció la boca; no puede hablar bien y se le cae un lado de la cara |
| RN-CV-04 | `DESMAYO` | Desmayo o pérdida del conocimiento | se desmayó; perdió el sentido un momento |
| RN-CV-05 | `PRESION_MUY_ALTA_O_CON_SINTOMAS` | Presión arterial muy alta (≥ 180) o presión alta con síntomas | la tensión me salió en 190; tengo la presión muy alta y me duele mucho la cabeza |
| RN-CV-06 | `PRESION_ALTA_SIN_SINTOMAS` | Presión arterial alta sin síntomas de alarma | me dijeron que tengo la tensión alta; sufro de la presión |

- [ ] Aprobados · [ ] Aprobados con cambios: ______________________ · [ ] Rechazados

**Propuesta de fondo (ADR 0012, B-015, ya implementada para la demostración):** en lugar de seguir ampliando patrones, que el asistente marque el signo con un **código cerrado** del catálogo. La tabla de códigos, descripciones y ejemplos coloquiales la validaría este equipo.

### Pregunta 4: frases coloquiales de prueba
`tests/live/colloquial_alarm_phrases.json` tiene 18 frases coloquiales sintéticas (p. ej., "el niño devuelve hasta el agua" → RN-MI-10; "mi tío se cayó redondo y no respondía" → RN-CV-04) con la regla que **debería** activar cada una. Las generó la IA. ¿Están bien asignadas? Marque las que no: ______________________

## Validación
Validado por: ______________________ · Fecha: ________ · Firma: ______________________
