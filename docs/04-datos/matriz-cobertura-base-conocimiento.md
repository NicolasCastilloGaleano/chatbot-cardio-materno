# Matriz de cobertura de la base de conocimiento

*Última actualización: 2026-11-11*

> **Estado: PROPUESTA.** Redactada con IA (Claude Code) a pedido de Nicolas Castillo Galeano. Qué cubre la base, sus cuotas y sus fuentes son **alcance y contenido clínico**, que no se delegan a la IA (AGENTS.md §5): lo decide el equipo con el líder del proyecto y queda en un ADR. Este documento **no cambia** `knowledge/kb/entries.jsonl`. Backlog: B-035. Pendiente de aprobación: punto 11.

## Estado de la ampliación (2026-11-10)
Un compañero del equipo cargó la ampliación en la hoja y se exportó a `entries.jsonl`: **2.828 registros** (1.413 CV y 1.415 MI), con los 1.600 originales sin cambios.

| Comparado con la propuesta | Resultado |
|---|---|
| Categorías nuevas | Las 14, con 33 a 85 registros cada una (propuesta: 100). Las más pequeñas: MI-N5 salud mental (33), MI-N2 alimentación infantil (44), CV-N7 corazón y mujer (49) |
| Categorías originales | Crecieron 400 registros: por ejemplo, *Infantil — dolor, neurología, piel, desarrollo y cuidados* pasó de 100 a 196 y *Presión arterial* a 150. Revisar la regla de atracción del §5 |
| *Solucionar* / *Indagar* en las nuevas | Varía por categoría (CV-N4 tiene 52/0; CV-N3, 41/44) |
| Formato con fuente y revisión (§7) | No se aplicó: los registros siguen sin fuente individual |
| Revisión clínica (§8, fase 5) | Pendiente |

## 1. Propósito
Hoy la base (1.600 registros) responde bien a una sola necesidad: *"tengo un síntoma, ¿qué hago?"*. Las personas también preguntan qué comer, qué hacer mientras llega la ayuda, cómo pedir una cita o si una creencia es cierta. Esta matriz define **qué debe cubrir** la base ampliada, **en qué proporción** y **de qué fuentes**, para que crezca sin sesgarse y para medir la cobertura antes y después de ampliarla.

El informe de vacíos (HU-15, `scripts/report_gaps.py`) sigue siendo la fuente de los vacíos **observados**. Esta matriz cubre los **previsibles**, antes de que alguien los encuentre.

## 2. Línea base (aproximada)
Estructura actual: 2 dominios × 8 categorías × 100 registros, con 50 % *Indagar* y 50 % *Solucionar*, todas por sistema del cuerpo o por síntoma.

Conteo por **palabras clave en la pregunta** (2026-11-08). Es una **aproximación que sobrecuenta**: "no quiere comer" cuenta como alimentación aunque sea un síntoma. La fase 1 (§8) la reemplaza por una clasificación revisada.

| Intención | Registros (CV / MI) | Lectura |
|---|---|---|
| Alimentación | 149 (59 / 90) | Casi siempre como síntoma (rechazo del alimento, vómito), no como "qué puedo comer" |
| Medicamentos | 146 (90 / 56) | Sobre todo "¿lo suspendo?"; pocas interacciones u olvidos |
| Rutas y controles | 150 (69 / 81) | Menciones de urgencias o cita; casi nada de cómo navegar el sistema (EPS, programas, vacunas) |
| Hábitos y prevención | 117 (74 / 43) | Disperso |
| Salud mental | 86 (41 / 45) | Ansiedad asociada a un síntoma; casi nada de salud mental perinatal |
| Automonitoreo | 81 (28 / 53) | Poco sobre la técnica (tomar la presión, contar movimientos fetales) |
| Primeros auxilios | 60 (31 / 29) | Muy bajo para lo que importa en una demostración |
| Mitos y creencias | 25 (10 / 15) | Casi ausente |

Población mencionada en la pregunta: gestante 263, niño 385, recién nacido 60, posparto 118, cuidador 175 y **adulto mayor 2** (un vacío claro en el dominio cardiovascular).

## 3. Ejes de la matriz
Cada registro se ubica en una **celda**: dominio × categoría × intención × población × enfoque.

### 3.1 Intención (qué necesita la persona)
| Código | Intención | Ejemplo de pregunta |
|---|---|---|
| I1 | Síntoma y qué hacer | "Se me hinchan los pies en la tarde" |
| I2 | Acción inmediata mientras llega la ayuda | "Mi papá se desmayó, ¿qué hago mientras llega la ambulancia?" |
| I3 | Alimentación según la condición | "Tengo la presión alta, ¿puedo comer embutidos?" |
| I4 | Hábitos y prevención | "¿Puedo hacer ejercicio en el embarazo?" |
| I5 | Medicamentos y adherencia (**sin dosis**) | "Se me olvidó la pastilla de la presión, ¿qué hago?" |
| I6 | Automonitoreo | "¿Cómo me tomo bien la presión en la casa?" |
| I7 | Rutas de atención, controles y derechos | "¿Cada cuánto son los controles prenatales?" |
| I8 | Salud mental y bienestar | "Desde que nació el bebé lloro todo el día" |
| I9 | Mitos y creencias | "¿Es verdad que en la dieta no me puedo bañar?" |

### 3.2 Población
P1 gestante · P2 puérpera o lactante · P3 recién nacido (0–28 días) · P4 lactante y niño menor de 5 años · P5 adulto con riesgo cardiovascular · P6 adulto mayor · P7 cuidador o familiar que pregunta por otra persona.

### 3.3 Atributos de redacción (no son celdas, son cuotas)
Registro coloquial o con errores de escritura, contexto rural (distancia, transporte, puesto de salud) y mensaje corto tipo WhatsApp.

## 4. Categorías nuevas propuestas
Se conserva el esquema de **100 registros por categoría**. Las 16 categorías actuales no se tocan en esta ampliación; siguen cubriendo sobre todo I1.

| Código | Dominio | Categoría nueva | Intenciones principales | Poblaciones |
|---|---|---|---|---|
| CV-N1 | CV | Alimentación y peso en riesgo cardiovascular (hipertensión, diabetes, colesterol, sal y líquidos en la falla cardíaca, anticoagulados y vitamina K) | I3, I9 | P5, P6, P7 |
| CV-N2 | CV | Hábitos y prevención (tabaco, alcohol, actividad física, sueño, estrés) | I4, I9 | P5, P6 |
| CV-N3 | CV | Medicamentos y adherencia (olvidos, efectos esperados, interacciones con alimentos, no suspender sin consultar) | I5 | P5, P6, P7 |
| CV-N4 | CV | Acción inmediata y primeros auxilios cardiovasculares (infarto, signos de ACV, desmayo, RCP solo con las manos, qué decir al 123 y qué llevar) | I2 | P5, P6, P7 |
| CV-N5 | CV | Automonitoreo y controles (presión en casa, glucometría, exámenes, programa de riesgo cardiovascular, rehabilitación cardíaca) | I6, I7 | P5, P6 |
| CV-N6 | CV | Rutas de atención y derechos (EPS, citas, urgencias, segunda opinión, apoyo al cuidador) | I7 | P5, P6, P7 |
| CV-N7 | CV | Corazón y mujer (hipertensión crónica y embarazo, riesgo después de una preeclampsia, anticonceptivos y presión, menopausia) | I4, I7, I3 | P1, P2, P5 |
| MI-N1 | MI | Alimentación en el embarazo y la lactancia (náuseas, acidez, diabetes gestacional, anemia, suplementos como información) | I3, I9 | P1, P2 |
| MI-N2 | MI | Alimentación infantil (lactancia exclusiva, alimentación complementaria, menores de 5 años) | I3, I4, I9 | P3, P4, P7 |
| MI-N3 | MI | Control prenatal, controles del niño y vacunación | I7, I6 | P1, P3, P4 |
| MI-N4 | MI | Primeros auxilios infantiles y prevención de accidentes (atragantamiento, quemaduras, caídas, intoxicaciones, sueño seguro) | I2, I4 | P3, P4, P7 |
| MI-N5 | MI | Salud mental perinatal y apoyo familiar | I8 | P1, P2, P7 |
| MI-N6 | MI | Planificación familiar, intervalo entre embarazos y regreso a las actividades después del parto | I4, I7 | P2 |
| MI-N7 | MI | Rutas de atención y derechos (EPS, acompañante, parto digno, licencias, registro del recién nacido) | I7 | P1, P2, P7 |

**Tamaño resultante:** 16 + 14 = 30 categorías, **3.000 registros** (1.500 por dominio). Los mitos (I9) y el cuidador (P7) no tienen categoría propia: van como cuota dentro de cada categoría (§5).

## 5. Reglas de balance
Dentro de cada categoría nueva de 100 registros:

| Regla | Valor propuesto |
|---|---|
| Enfoque *Solucionar* / *Indagar* | 70 / 30 (ver decisión D3) |
| Peso máximo de un subtema | ≤ 15 registros |
| Cuota por población | Según la tabla del §4, con un mínimo de 15 para cada población listada |
| Pregunta del cuidador (P7) | ≥ 15 |
| Registro coloquial o con errores | ≥ 15 |
| Contexto rural | ≥ 15 |
| Mitos y creencias (I9) | ≥ 10 donde aplique |

Entre categorías:
- **Igual tamaño no basta.** En la búsqueda vectorial, una zona densa "atrae" consultas vecinas. Se mide la **atracción** de cada categoría: el porcentaje de preguntas de prueba de *otras* categorías que recuperan sus registros. Una categoría con atracción alta se redacta más específica o se reduce.
- **Nada de duplicados:** un registro con similitud ≥ 0,92 (por definir en la fase 1) con otro existente se descarta o se fusiona.
- **Equilibrio entre dominios:** 1.500 / 1.500.

## 6. Fuentes
Se priorizan fuentes **oficiales colombianas, públicas y citables**. **Todas están por verificar:** versión vigente, URL y condiciones de uso. Ninguna se ha descargado.

| Fuente | Para qué | Categorías |
|---|---|---|
| Guías Alimentarias Basadas en Alimentos (GABA) del ICBF: población mayor de 2 años; gestantes, lactantes y menores de 2 años | Alimentación en lenguaje sencillo | CV-N1, MI-N1, MI-N2 |
| Resolución 3280 de 2018 (MinSalud): Ruta Integral Materno Perinatal y Ruta de Promoción y Mantenimiento de la Salud, con sus modificaciones | Controles, frecuencias y qué incluye cada atención | MI-N3, MI-N6, MI-N7, CV-N5 |
| Programa Ampliado de Inmunizaciones (PAI): esquema nacional vigente | Vacunación | MI-N3 |
| Guías de Práctica Clínica de MinSalud/IETS, **versión para pacientes y cuidadores** (embarazo y puerperio, hipertensión, síndrome coronario agudo, falla cardíaca, recién nacido) | Orientación clínica ya escrita para el público | Todas |
| AIEPI, componente comunitario (OPS/MinSalud) | Prácticas clave en el hogar y signos de peligro en niños | MI-N2, MI-N4 |
| OPS: iniciativa HEARTS; OMS: recomendaciones de atención prenatal y fichas descriptivas en español | Hipertensión, prevención y control prenatal | CV-N1, CV-N2, CV-N5, MI-N3 |
| Cruz Roja Colombiana; recomendaciones de RCP solo con las manos (AHA/ILCOR) | Primeros auxilios | CV-N4, MI-N4 |
| Ley 1751 de 2015, Ley 2244 de 2022 (parto digno), normas vigentes de licencias | Derechos | CV-N6, MI-N7 |
| Dirección Territorial de Salud de Caldas | Líneas, servicios y rutas locales. **Lo aporta el equipo; la IA no lo inventa** | CV-N6, MI-N7 |
| MedlinePlus en español (NLM) | Complemento. Solo páginas de autoría de la NLM: parte del contenido es de terceros con derechos | Complemento |

### Decisión sobre la CIE-10
La **CIE-10** (Clasificación Internacional de Enfermedades de la OMS) es una lista de **códigos de diagnóstico**: no trae orientación, alimentación ni rutas. **No se usa como fuente de contenido**, porque además empujaría al asistente a nombrar diagnósticos (AGENTS.md §1).

Se propone usarla **solo como lista de control interna**: revisar en los capítulos IX (I00–I99), XV (O00–O99) y XVI (P00–P96) que ninguna condición frecuente quede sin orientación. Los códigos no entran en los registros, el índice ni las respuestas.

## 7. Formato propuesto del registro
Se agregan campos para resolver la limitación de B-019 (registros sin fuente, revisor ni fecha). Cambiar el formato exige un **ADR nuevo** y cambios en el cargador del RAG, el modelo de datos y el diccionario de datos.

```json
{"id": "…", "domain": "materno_infantil", "category": "MI-N1 …", "focus": "Solucionar",
 "intent": "I3", "population": ["P1"],
 "question": "…", "answer": "…",
 "source_id": "GABA-GESTANTES", "source_section": "…",
 "status": "borrador | revisado | validado", "reviewed_by": "…", "reviewed_at": "AAAA-MM-DD"}
```

Las fuentes se describen una sola vez en un catálogo (p. ej., `knowledge/kb/sources.json`) con título, entidad, versión, URL y fecha de consulta. Los 1.600 registros actuales quedarían con `source_id: "PILOTO-2026-10"` hasta su revisión.

Estilo de las respuestas, igual que la base actual: unos 550 caracteres, frases **autocontenidas y citables** (ADR 0010 y selector de evidencia, ADR 0019), sin dosis y sin diagnóstico.

## 8. Proceso por fases
| Fase | Qué se hace | Criterio para pasar |
|---|---|---|
| 0. Aprobación | El equipo decide la matriz, las cuotas y las fuentes (§9) | Decisión registrada en un ADR y en *pendientes de aprobación* |
| 1. Medición de la línea base | Banco de preguntas sintéticas: unas 20 por celda, de varios "personajes" (gestante rural, hijo que cuida a su papá…). Clasificación de los 1.600 registros por intención, con IA y revisión por muestreo | Porcentaje de preguntas con evidencia sobre el umbral (0,50) y con veredicto `si` del selector, por celda |
| 2. Fuentes | Conseguir los documentos, llenar el catálogo y extraer los fragmentos por categoría | Catálogo revisado por el equipo |
| 3. Redacción | Por lotes de una categoría (100 registros). La IA escribe la pregunta y la respuesta **a partir del fragmento citado**, nunca de memoria | Lote completo con todas sus cuotas |
| 4. Controles automáticos | Duplicados; términos prohibidos (dosis, "usted tiene…"); longitud; frases citables; coherencia con `knowledge/alarm_rules.json`: si la pregunta activa una alarma, la respuesta no puede contradecir su nivel de urgencia | Cero errores bloqueantes |
| 5. Revisión clínica | **100 %** en CV-N3, CV-N4 y MI-N4 (medicamentos y primeros auxilios). En el resto, una muestra estratificada ≥ 20 % por categoría; si falla más del 10 % de la muestra, se revisa el lote entero | `status: validado` y decisión del líder para el prototipo |
| 6. Integración y medición | Reconstruir el índice, repetir el banco de la fase 1, `tests/live/retrieval_probe.json` y `pytest -m live`; medir la atracción de cada categoría | Mejora en las celdas nuevas **sin retroceso** en las preguntas que ya se respondían |

**Orden sugerido para la demostración:** primeros auxilios (CV-N4, MI-N4), alimentación (CV-N1, MI-N1) y rutas y controles (MI-N3, CV-N6). Son las preguntas más frecuentes y las más vistosas.

## 9. Decisiones pendientes del equipo
| # | Decisión | Propuesta |
|---|---|---|
| D1 | ¿Se aprueban las 14 categorías nuevas y el tamaño de 3.000 registros? | Sí, con la posibilidad de crecer por lotes |
| D2 | ¿Qué categorías van primero? | Las del orden sugerido del §8 |
| D3 | Proporción *Solucionar*/*Indagar* en las categorías nuevas | 70/30: son preguntas de información y el selector solo usa *Solucionar* |
| D4 | ¿Se aprueba el formato con fuente, intención, población y revisión? | Sí, con un ADR. Resuelve también B-019 |
| D5 | Fuentes autorizadas y quién aporta los datos locales de Caldas | La tabla del §6; los datos locales los aporta el equipo |
| D6 | Nivel de revisión clínica y quién la hace | La del §8, fase 5 |
| D7 | ¿Se sigue redactando con IA a partir de fuentes? | Sí, anclada al fragmento y con el registro en la bitácora IA |

## 10. Lo que queda fuera
- Dosis, ajustes de medicamentos y diagnósticos (Res. 2654/2019: teleorientación, no prescripción).
- Decidir si hay alarma: lo hacen las reglas de `domain/` (ADR 0004). La base solo orienta.
- Datos de personas reales: las preguntas son sintéticas (AGENTS.md §4).

## 11. Ronda 2: determinantes sociales y temas faltantes (B-036)
> **Estado: PROPUESTA en curso** (2026-11-11). Decisiones del usuario: los DSS van como categorías dentro de cada dominio (sin dominio nuevo ni cambios de código), Claude redacta un borrador a partir de fuentes citadas y la meta es una base de unos **4.000 registros** (unos 1.200 nuevos). El equipo valida antes de pegar en la hoja.

### 11.1 Lecciones de la ronda 1 (pruebas en vivo en MN5, 2026-11-11)
- Los registros nuevos son escenarios muy específicos. Las preguntas generales ("¿qué alimentos ayudan a controlar la presión?", "acidez a las 34 semanas, ¿es normal?") no superan el umbral de 0,50 y reciben la abstención.
- Las 14 categorías nuevas quedaron con 33 a 85 registros, frente a 100 propuestos.
- La sonda de recuperación no conocía las categorías nuevas.

### 11.2 Determinantes sociales de la salud
Marco de la OMS: los determinantes **estructurales** (ingreso, educación, ocupación, género, etnia, estatus migratorio) y los **intermedios** (vivienda, agua, alimentos, condiciones de trabajo, factores psicosociales, acceso al sistema de salud). En un asistente de teleorientación, un registro DSS **orienta sobre la barrera concreta** (cómo llegar, a qué tiene derecho, qué hacer con lo que hay), sin juzgar ni suponer nada de la persona.

### 11.3 Categorías de la ronda 2
El nombre exacto (columna *Categoría* de la hoja) es el de la tabla.

| Bloque | Categoría | Registros |
|---|---|---|
| A. DSS | CV-S1 — Acceso y barreras de atención (afiliación, SISBEN, copagos, transporte, distancia rural, migrantes) | 50 |
| A. DSS | CV-S2 — Alimentación y entorno con recursos limitados (comer sano con poco dinero, humo de leña, agua, actividad física rural) | 50 |
| A. DSS | CV-S3 — Trabajo, ingresos y cuidado (jornaleros, recolección de café, volver al trabajo, incapacidad, cuidador, adulto mayor solo) | 50 |
| A. DSS | CV-S4 — Educación, cultura y comunicación (entender recetas y etiquetas, remedios caseros, interculturalidad, conectividad) | 50 |
| A. DSS | CV-S5 — Factores psicosociales (estrés económico, soledad, duelo, consumo ligado al contexto) | 50 |
| A. DSS | MI-S1 — Acceso en el embarazo y la infancia (sin EPS, migrantes, transporte a controles, plan de parto rural, hogar de paso) | 50 |
| A. DSS | MI-S2 — Alimentación y hogar con recursos limitados (inseguridad alimentaria, programas del ICBF, agua, saneamiento, leña) | 50 |
| A. DSS | MI-S3 — Violencias y protección (violencia de pareja e intrafamiliar, violencia sexual, maltrato infantil, embarazo adolescente) | 50 |
| A. DSS | MI-S4 — Trabajo, estudio y redes de apoyo (embarazo y trabajo agrícola, licencias, madre adolescente, madre sola, papel del padre) | 50 |
| A. DSS | MI-S5 — Cultura y saberes tradicionales (parteras, dieta de los 40 días, plantas, enfoque intercultural) | 50 |
| B. Completar | Las categorías `CV-N*` y `MI-N*` hasta 80 o más, empezando por MI-N5 (33), MI-N2 (44), CV-N7 (49), MI-N6 (50), CV-N4 (52), MI-N4 (52) y CV-N1 (55) | ≈ 300 |
| C. Faltantes | CV-T1 — Diabetes, colesterol, riñón y obesidad | 60 |
| C. Faltantes | CV-T2 — Adulto mayor (polifarmacia, caídas, memoria, cuidador) | 60 |
| C. Faltantes | CV-T3 — Chagas, fiebre reumática y cardiopatías congénitas | 50 |
| C. Faltantes | MI-T1 — Salud preconcepcional y embarazo adolescente | 60 |
| C. Faltantes | MI-T2 — Infecciones en el embarazo y tamizajes (sífilis, VIH, hepatitis B, toxoplasmosis, dengue, zika) | 60 |
| C. Faltantes | MI-T3 — Pérdida gestacional, duelo perinatal, prematuridad y madre canguro | 50 |
| C. Faltantes | MI-T4 — Crecimiento, malnutrición, anemia, desparasitación y salud oral infantil | 60 |

### 11.4 Reglas de redacción
| Regla | Valor |
|---|---|
| Preguntas **generales y básicas** (`Tipo = general`) | ≥ 30 % de cada categoría |
| Coloquiales, de un cuidador, en contexto rural | ≥ 15 % cada una |
| *Solucionar* / *Indagar* | 70 / 30 |
| Longitud de la respuesta | 300 a 650 caracteres, en frases autocontenidas y citables (ADR 0010) |
| Prohibido | Dosis, diagnósticos ("usted tiene…"), juicios sobre la persona, datos locales inventados (teléfonos o direcciones que no estén en una fuente) |
| Fuente | Cada registro cita un `id` de `docs/04-datos/fuentes-base-conocimiento.md` |

Formato del borrador: un CSV por categoría en `docs/04-datos/borradores-kb/ronda-2/`, con las columnas `Categoría, Enfoque, Preguntas, Respuestas, Fuente, Tipo`. `scripts/export_sheet_kb.py` ignora las dos últimas, así que `entries.jsonl` no cambia de formato. `scripts/check_kb.py` revisa cuotas, longitudes, términos prohibidos, duplicados y fuentes.

### 11.5 Fuera de la base (para decidir el equipo)
- **Reglas de alarma** para ideación suicida y para violencia con riesgo inminente: hoy no existen en `knowledge/alarm_rules.json`. La base solo orienta sobre rutas; decidir una alarma no se delega a la IA (ADR 0004).
- Preguntas sobre el propio asistente (quién es, qué guarda): van en plantillas, no en la base.

### 11.6 Revisión
Revisión del 100 % en MI-S3 (violencias), MI-T2 (infecciones) y los primeros auxilios (CV-N4, MI-N4). En el bloque A conviene la revisión de trabajo social o salud pública. En el resto, una muestra estratificada ≥ 20 %, como en el §8.
