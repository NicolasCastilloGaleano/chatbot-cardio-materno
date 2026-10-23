# Product Backlog

*Última actualización: 2026-10-18 (B-010)*

Priorizado por el Product Owner con los aliados (decisión **no delegable** a la IA). Cada ítem se enlaza con su historia de usuario (HU) en `../01-especificacion/historias-usuario.md`.

| ID | Ítem | HU | Prioridad | Sprint | Estado |
|---|---|---|---|---|---|
| B-001 | Estructura del repositorio, reglas y documentación base | — | Alta | 0 | ✅ Hecho |
| B-012 | Chat libre por consola con Ollama (prototipo técnico) | HU-00 | Alta | 1 | ✅ Hecho |
| B-013 | Hilos conversacionales con resumen y respuesta estructurada del agente | HU-06 | Alta | 1 | ✅ Hecho |
| B-002 | Especificación ejecutable v1 con signos de alarma validados clínicamente | — | Alta | — | ⏳ Esperando la validación clínica ([solicitud](../01-especificacion/solicitud-validacion-alarmas.md)) |
| B-003 | Flujo conversacional mínimo por consola (saludo → consentimiento → tema → orientación) | HU-01, HU-02 | Alta | — | ⏳ |
| B-004 | Detección determinista de signos de alarma materno‑infantiles | HU-03 | Alta | 1 | ✅ Hecho (técnico); ⏳ validación clínica |
| B-005 | Detección determinista de signos de alarma cardiovasculares | HU-04 | Alta | 1 | ✅ Hecho (técnico); ⏳ validación clínica |
| B-006 | Direccionamiento a rutas de atención | HU-05 | Alta | — | ⏳ |
| B-007 | Integración del LLM para interpretar y redactar (con guardrails) | HU-02 | Media | — | ⏳ |
| B-008 | RAG sobre la base de conocimiento (híbrido, índice propio) + separación análisis/respuesta | HU-02 | Alta | 1 | ✅ Hecho (2026-10-12) |
| B-009 | Adaptador Telegram (multiusuario) | — | Media | — | ⏳ |
| B-010 | Adaptador WhatsApp (Cloud API, webhook y cola) con persistencia SQLite por usuario. Especificación propuesta: HU-09, ADR 0014 y 0015 | HU-09 | Media | — | ✅ Hecho (verificado en el PC de pruebas el 2026-10-18; solo números de prueba hasta el consentimiento, HU-01) |
| B-011 | Panel o registro de métricas anonimizadas | — | Baja | — | ⏳ |
| B-014 | Foco actual del hilo: campo `current_focus` en el JSON del agente, separado del `summary` (ver nota) | HU-06 | Media | — | ⏳ Diferido |
| B-015 | Síntomas reportados por el agente como **códigos cerrados** del catálogo (p. ej. `SANGRADO_VAGINAL`) en lugar de texto libre. **Solución definitiva** del filtro 2; la versión puente actual no la reemplaza. **Propuesta: ADR 0012** (códigos en paralelo con el texto libre, cruce exacto en `domain/`); se recomienda antes de elegir el modelo (ADR 0011) | HU-03, HU-04 | **Alta** | 1 | 🔄 Implementado para la demostración (ADR 0012 provisional, catálogo v0.5.0); falta la ratificación del equipo y la ronda 3 |
| B-018 | Verificación léxica de grounding: cada frase de salud de la respuesta debe estar en la evidencia citada (implementación propia, ADR 0010: `domain/grounding.py`, abstención sin LLM y texto literal) | HU-02 | Alta | 1 | ✅ Hecho (2026-10-12) |
| B-019 | Traer `kb_sync` (Google Sheets → `entries.jsonl`) y agregar a la hoja las columnas Fuente / Validado por / Fecha | HU-02 | Media | — | ⏳ |
| B-020 | Control de alcance por intención (fuera de alcance / conversacional) | HU-07 | Alta | 1 | ✅ Hecho (2026-10-12) |
| B-022 | Latencia: embedder en CPU, precalentamiento, límite de tokens, `think` por etapa, configuración por etapa en `.env` y `scripts/benchmark_models.py` (3 rondas y la combinación elegida). **ADR 0011 aceptado (2026-10-12):** análisis `mistral-small3.1:24b`, respuesta `qwen3:8b`; turno p50 de 46,5 s, con la mejor seguridad medida. La meta de 15 s queda como trabajo futuro | HU-02 | Alta | 1 | ✅ Hecho (2026-10-12) |
| B-021 | Calidad de recuperación con frases coloquiales o mixtas. **Corrección (2026-10-11):** la sonda ya exigía la categoría esperada en el top-3 (el reporte solo imprimía la primera); el problema real es que, en ACV, TVP y el mensaje mixto de la presión, la categoría correcta no queda primera ni supera el umbral de producción, y el caso termina en abstención. Paso 1 (hecho): la sonda reporta top-1 y "útil con el umbral real"; el análisis v3 reformula la consulta (`search_query`) sin el contexto ajeno y la traza la registra. Paso 2 (según la medición en vivo): ajustar la instrucción de consulta, los pesos o el umbral | HU-02 | Por definir (equipo) | 1 | 🔄 En verificación |
| B-016 | `AlertNotifier`: avisar al equipo de salud cuando se registra una alerta | HU-03, HU-04 | Media | — | ⏳ |
| B-017 | Intención del mensaje (reporte / consulta general / ambiguo) para **adaptar** la respuesta a una alarma, nunca para suprimirla (ver nota) | HU-03, HU-04 | Media | — | ⏳ |
| B-023 | Interfaz web local de chat con envío por Enter, estado de procesamiento y paneles persistentes de auditoría | HU-08 | Alta | — | ✅ Implementada y verificada automáticamente; recorrido visual pendiente |
| B-024 | Base de conocimiento v2 por cuadros y etapas ([plan de migración](plan-migracion-rag2.md), fase 2): modelo y conversor (MIG-05/06, ADR 0016 propuesto), carga y recalibración (MIG-07), evaluación (MIG-08). Reemplaza el `kb_sync` de B-019 por `scripts/convert_rag_xlsx.py` | HU-02 | Alta | — | 🔄 MIG-05 a MIG-08 implementados; la v2 se activa por `.env` (rama `feat/fase2-3-base-v2-y-etapas`). Reemplazar la v1 espera P1/P7 |
| B-025 | Estado del caso y evidencia por etapas (plan de migración, fase 3: MIG-09 a MIG-13, ADR 0017 propuesto). Cubre la indagación en varios turnos, la ruta de atención desde la ruta base del cuadro (B-006) y el foco del caso (B-014) | HU-02, HU-05, HU-06 | Alta | — | 🔄 Implementado (rama `feat/fase2-3-base-v2-y-etapas`); pendiente la prueba en el PC de pruebas |

## Notas de ítems

### B-014: Foco actual del hilo (`current_focus`)
- **Idea (Nicolas Castillo Galeano, 2026-10-10):** el `summary` debe ser general (el caso y cómo ha ido la conversación). Aparte, conviene registrar qué se está tratando *ahora mismo*. Ejemplo: en un hilo largo sobre acidez en el embarazo, los últimos mensajes giran en torno a una comida concreta, y el foco sería "si puede comer piña y cítricos con la acidez".
- **Propuesta técnica:** un campo propio `current_focus` en el JSON del agente, validado como obligatorio y no vacío. Se reemplaza en cada turno y se muestra en la línea de depuración. Se prefiere a una frase al final del `summary` porque es verificable y mantiene limpio el resumen.
- **Por qué se difiere:** en la consola los últimos `THREAD_CONTEXT_MESSAGES` (6) mensajes ya le dan al agente el foco reciente, y en las pruebas de la HU-06 no aparecieron fallos de continuidad. Cambiar el prompt validado ahora agrega riesgo sin un beneficio visible para la demo.
- **Disparadores para retomarlo:** (1) al implementar Telegram o WhatsApp, donde los hilos son más largos y se retoman tras una pausa; (2) si en las pruebas el agente corta hilos que deberían continuar u olvida el tema reciente.
- **Impacto estimado:** esquema y validación del turno, entidad del hilo, archivo JSON, prompt v3, pruebas, criterio en la HU-06, nota en el ADR 0006, diccionario de datos.

### B-015: Síntomas como códigos cerrados
- Hoy el agente escribe `reported_symptoms` en texto libre y las mismas regex lo revisan (filtro 2, ADR 0007).
- Evolución: el catálogo define un código por signo, el JSON Schema restringe `reported_symptoms` a esos códigos y el cruce con las reglas pasa a ser exacto, sin depender de la redacción del agente.
- Se retoma si el origen `agente` muestra fallos de cobertura o falsos positivos frecuentes.
- **Evidencia (2026-10-10):** el agente describió un sangrado como "secreción rosada por la vagina" y ningún patrón lo cubría. Se corrigió ampliando los patrones, pero confirma la fragilidad del texto libre.
- **Evidencia 2 (2026-10-10):** el agente reportó "disminución de los movimientos del bebé" y la regla solo aceptaba "movimientos fetales". Misma causa.
- **Versión puente implementada (catálogo v0.3.0, prompt v5):** el prompt incluye los nombres exactos de los signos (campo `sign`) y cada regla coincide con su propio nombre normalizado. **Decisión del usuario: esta versión simple NO debe quedar como definitiva.** Sus límites son:
  1. sigue siendo texto libre: el agente puede no usar el nombre exacto o parafrasearlo;
  2. el JSON Schema no restringe los valores, así que no hay validación estructural;
  3. los nombres de los signos son largos y están pensados para personas, no como identificadores estables;
  4. un cambio de redacción del `sign` en el catálogo cambia lo que el agente debe escribir.
- **Alcance del B-015 completo (a refinar al iniciarlo):**
  - código estable por signo en el catálogo (p. ej., `code: "MOVIMIENTOS_FETALES_DISMINUIDOS"`), separado del nombre legible;
  - un campo nuevo, p. ej. `reported_signs`, con `enum` de esos códigos en el JSON Schema (salida restringida por Ollama), además de `reported_symptoms` en texto libre para auditoría;
  - cruce exacto código → regla, sin regex en el filtro 2;
  - prompt con la tabla código → descripción → ejemplos coloquiales;
  - pruebas golden con frases coloquiales evaluadas contra el modelo real (marca `live`);
  - métricas: alertas por origen y casos que solo detectó el agente;
  - posible combinación con B-017 (intención del mensaje) en el mismo contrato JSON.
- **Evidencia 3 (2026-10-12, comparación de modelos):** ocho descripciones correctas de varios modelos no activaban su regla ("vómito de todo lo que come", "fiebre en bebé de 10 días", "parálisis en la mitad del cuerpo", "soy hipertenso"…). Se ampliaron los patrones (catálogo v0.4.0, pendiente de aprobación clínica).
- **Propuesta formal:** [ADR 0012](../02-arquitectura/adr/0012-signos-reportados-como-codigos-cerrados.md) (estado Propuesto).
- **Prioridad:** Alta; se recomienda hacerlo antes de elegir el modelo (ADR 0011).

### B-017: Intención del mensaje ante una alarma (consulta vs. reporte)
- **Idea (Nicolas Castillo Galeano, 2026-10-10):** una pregunta educativa como "¿por qué se pueden dar síntomas como secreciones de agüita rosada por abajo en embarazos de 7 meses?" activa la misma alarma que un reporte real. Propuesta original: un paso previo en el que el agente clasifique si el mensaje es una consulta o un reporte de síntomas, y responder distinto en cada caso.
- **Por qué no como filtro previo que suprima la alarma:**
  1. Le daría al LLM poder para **quitar** alarmas, en contra del ADR 0004 y del ADR 0007 ("el agente solo suma alarmas"). Los errores no son simétricos: un reporte clasificado como consulta es una emergencia sin alerta.
  2. Muchas personas **reportan preguntando** ("¿es normal que me salga agüita rosada? tengo 7 meses"; "¿por qué mi bebé respira tan rápido?"). El clasificador fallaría justo en los casos de mayor riesgo, cuando la persona minimiza lo que le pasa.
  3. Agregaría la latencia del LLM a las urgencias, que hoy se responden sin consultarlo.
- **Diseño seguro propuesto (el agente cambia el *cómo*, no el *si*):**
  1. El filtro determinista se mantiene igual: la alarma se activa siempre.
  2. El agente agrega a su JSON `message_intent`: `reporte` | `consulta_general` | `ambiguo`.
  3. Con `consulta_general`, se muestra un **mensaje fijo condicional** ("🚨 Si esto le está pasando ahora a ti o a alguien, es un signo de alarma: acude de inmediato a urgencias o llama al 123") **seguido** de la explicación educativa del agente. Con `reporte` o `ambiguo`, el comportamiento actual (solo el mensaje fijo).
  4. La alerta se registra igual, con la intención anotada, para medir cuántas alertas fueron preguntas.
  5. Para no perder inmediatez, el mensaje fijo se muestra primero y la explicación después, cuando responda el agente (en consulta urgente sí se llama al LLM).
- **Si el agente se equivoca:** la persona igual recibe la instrucción de urgencia; solo cambia si además recibe una explicación.
- **Decisión clínica (no delegable):** si un mensaje con signo de alarma puede recibir una respuesta distinta por ser una pregunta. Se agregará a la solicitud de validación del equipo clínico.
- **Impacto estimado:** campo `message_intent` (esquema, validación y registro), prompt v5, mensajes fijos condicionales en el catálogo, respuesta en dos tiempos en la consola, pruebas (incluida una golden con preguntas que en realidad son reportes), un ADR o una actualización del ADR 0007, HU-03/HU-04, flujo y BPMN de gestión de alerta y R-09.
- **Mientras tanto:** el aviso de más ante una pregunta educativa se acepta como falso positivo seguro (criterio conservador, R-09).
