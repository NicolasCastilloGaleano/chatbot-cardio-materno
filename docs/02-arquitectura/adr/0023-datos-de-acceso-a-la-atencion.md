# ADR 0023: Datos de acceso a la atención como códigos cerrados que nunca deciden la ruta

- **Estado:** Propuesto e implementado para revisión (2026-11-16), **apagado por defecto**. Lo ratifica el equipo (AGENTS.md §5)
- **Fecha:** 2026-11-16
- **Decisores:** líder del proyecto y equipo clínico; los textos jurídicos, quien el equipo designe; el uso para investigación, quien responda por la protección de datos
- **Origen:** propuesta del equipo «HU-16 · ADR 0022: acceso a la atención» (2026-11-12, sobre el commit `fc6eb21`), a partir del manuscrito sobre determinantes sociales y colesterol
- **Historia:** HU-18 · **Backlog:** B-042
- **Depende de:** ADR 0004, 0012 y 0022

## Identificadores
La propuesta original usaba identificadores que ya estaban ocupados cuando se integró. Se conserva la historia existente y la propuesta se renumera:

| En la propuesta | Ya era | Queda como |
|---|---|---|
| ADR 0022 | Vista ciudadana, consentimiento y procedencia | **ADR 0023** |
| HU-16 | Vista ciudadana de la conversación | **HU-18** |
| B-035 | Ampliación de la base de conocimiento | **B-042** |
| Esquema SQLite v3 | libre (el esquema vigente era el v2) | **v3**, con una columna más (`research_at`) |
| Prompt de análisis v9 | libre | v9 |

## Contexto
El asistente remite siempre igual ("pide cita en tu EPS"), aunque la persona diga que no tiene EPS, que no le dan la cita o que no le entregan el medicamento. El manuscrito del equipo describe además la cascada del colesterol (medición, diagnóstico, tratamiento, control) como el lugar donde se pierde el efecto clínico. Es una comparación descriptiva: no demuestra efectos individuales.

Desde que se escribió la propuesta cambiaron tres cosas: la base pasó de 1.600 a 4.049 registros e incluye categorías de acceso y derechos con fuente (`CV-S1`, `MI-S1`); existe una barrera de consentimiento y una minimización de datos (ADR 0022); y hay una vista ciudadana que distingue de dónde sale cada respuesta.

## Decisión
1. **Códigos cerrados en un catálogo como datos** (`knowledge/care_access.json`): seis barreras (administrativas, geográfica, económica, de medicamentos y de cuidado), tres de afiliación y ocho de la cascada. Las barreras se detectan con patrones sobre el texto de la persona; el análisis (prompt v9) puede marcar además `access_facts` con un `enum`.
2. **Nunca deciden nada del turno.** Se evalúan al final (`ConversationService._with_care_access`), con la alarma, el alcance, la evidencia y el hilo ya resueltos. La variante del aviso (consulta o urgencias) se **lee** de lo decidido. Una batería de invariancia lo comprueba en ocho escenarios.
3. **Solo cuenta lo declarado.** Un paso de la cascada que nadie mencionó queda *desconocido*: tomar tratamiento no prueba un diagnóstico ni una medición. Declaraciones opuestas dejan el paso *contradictorio* y no producen aviso. Lo que detecta un patrón se registra como dicho por la persona; lo que solo marcó el modelo, como **interpretación**. Un código de la cascada se descarta si la persona no habló del colesterol.
4. **La cascada no es un formulario.** No se pregunta la medición. Como mucho hay **una** pregunta de contexto por hilo, solo si sigue a un "sí" que la persona contó en este mensaje, no pidió un dato concreto, la respuesta no trae otra pregunta y no hay urgencia. Una barrera dicha en un mensaje anterior no vuelve a generar su aviso.
5. **Textos versionados con estado propio.** Cada aviso tiene naturaleza (`administrativo` o `clinico`), sustento y `status`. **Solo un texto `aprobado` se muestra**, aunque `CARE_ACCESS_MODE` sea `activo`. Hoy todos están en `pendiente`: activar el modo no muestra nada a nadie.
6. **Tres finalidades, tres autorizaciones.**
   - *Atender* (consentimiento de la HU-01): los mensajes se guardan para la conversación.
   - *Operar* la regla: los códigos se usan dentro del turno y no se guardan. Solo queda registrado un aviso que sí se mostró, porque su texto ya está en la respuesta.
   - *Investigar* (`users.research_consent`, esquema v3): autorización aparte, opcional y revocable. Solo con ella se guardan los códigos en la traza y la persona entra en el informe. El modo `observar` tiene la misma restricción.
7. **Informe agregado por persona** (`scripts/export_care_access.py`): cuenta personas y no hilos, por el mes de cada mensaje y solo meses cerrados. Omite los meses con menos de 10 personas, lista siempre todos los indicadores y publica "<5" para los conteos de 0 a 4, suprime un conteo que deja fuera a menos de 5 personas del mes y redondea el resto a múltiplos de 5. Estos controles **reducen** el riesgo; no garantizan anonimato (ver «Revisión del 2026-11-16»). Lleva una advertencia fija: **no es una estimación de Caldas**.
8. **Emergencias sin consentimiento.** `knowledge/public_info.json` y `GET /api/public/emergency` entregan indicaciones generales (línea 123, urgencias) sin sesión, sin aceptación y sin recibir ningún dato. La vista ciudadana las abre desde la cabecera en cualquier momento.

## Qué se corrigió de la propuesta
| En la propuesta | Problema | Ahora |
|---|---|---|
| Tratamiento ⇒ diagnóstico y medición | Atribuye a la persona un dato clínico que no dijo | Estados declarados, desconocidos y contradictorios |
| "Gana el último código del catálogo" | Resuelve una contradicción de forma arbitraria | La contradicción se registra y no avisa |
| Pregunta el siguiente paso en cada turno | Convierte la consulta en un cuestionario | Una pregunta de contexto por hilo, ligada a lo que la persona contó |
| Códigos siempre en la traza | Datos sensibles codificados sin finalidad ni autorización | Solo con autorización para informes |
| "Un caso por hilo" | Cuenta varias veces a la misma persona | Una persona por mes |
| Suprimir conteos de 1 a 4 | Deducible por diferencias y por exportaciones repetidas | Umbral de población, redondeo y meses cerrados |
| "Son datos de Caldas" | No es una muestra | Advertencia fija en el informe |
| `activo` muestra todo el catálogo | Publica textos jurídicos sin revisar | Estado de aprobación por texto |
| Código desconocido en `access_facts` | Podía hacer fallar un turno | Se ignora: estos datos nunca rompen el turno |
| Aviso dentro del texto de la respuesta | Se confunde con la evidencia | Encabezado fijo y tarjeta aparte en la interfaz |

## Lo que este ADR no decide
- **La aprobación de cada texto** (clínica para la cascada, jurídica para los demás). La norma de entrega de medicamentos está marcada "verificar vigencia".
- **El texto de la autorización para informes** y si la finalidad "mejorar los servicios de salud" es suficiente; hoy solo la ofrece la vista ciudadana, no WhatsApp.
- **Detectar una urgencia individual antes del consentimiento.** Sigue sin hacerse: antes de aceptar no se procesa ningún mensaje. Es una decisión institucional.
- **Borrar los códigos ya guardados** de quien retira la autorización: deja de contar en el informe y no se guardan más, pero los anteriores siguen en sus trazas hasta que exista la política de retención.
- **Si los avisos administrativos duplican la base.** Las categorías `CV-S1` y `MI-S1` ya orientan sobre afiliación y urgencias con fuente; el equipo puede preferir esa vía y dejar los avisos fijos solo para las urgencias, donde no se consulta la base.

## Consecuencias
- Con `apagado` no cambia nada: mismo prompt (v8), mismo esquema y la misma traza guardada.
- Con `observar` o `activo` el prompt de análisis pasa de 14.683 a 18.283 caracteres (+3.600, cerca de 900 a 1.200 tokens) y el esquema, de 1.371 a 1.842. **No se ha medido con Ollama** si eso afecta la detección de alarmas del filtro 2.
- **Riesgo de ventana de contexto.** El análisis usa 6.144 tokens por defecto y con 4.096 ya se cortaba en hilos largos (2026-10-27). El v9 solo ocupa entre 4.600 y 6.100 tokens según el tokenizador, así que en un hilo largo Ollama puede descartar historial sin avisar. Antes de salir de `apagado` hay que medir el tamaño real (`max_prompt_tokens` del comparador) y, si hace falta, subir `OLLAMA_ANALYSIS_NUM_CTX` **para las dos variantes**.
- El catálogo, el prompt v9 y la migración v3 son aditivos; la migración solo agrega dos columnas con valor por defecto.

## Revisión del 2026-11-16 (verificación integral, sin Ollama)
Fallos encontrados y corregidos, cada uno con su prueba de regresión:

| Fallo | Corrección |
|---|---|
| Rechazar el consentimiento dejaba vigente la autorización para informes: la persona seguía en el informe | El rechazo retira también esa autorización (`domain/consent.py`) y la exportación excluye a quien rechazó |
| La vista ciudadana no permitía cambiar ninguna decisión después de la bienvenida | Diálogo «Mis datos»: cambiar la autorización para informes o retirar la aceptación |
| El informe usaba el mes de creación del hilo: un mes cerrado podía recibir mensajes del mes siguiente | Usa el mes de cada mensaje |
| Una fila solo existía si alguien había declarado ese dato (su presencia ya lo revelaba) | Salen siempre todos los indicadores; 0 a 4 es "<5" |
| Un dato compartido por casi todo el mes se publicaba (p. ej., "10" de 10) | Se suprime si deja fuera a menos de 5 personas |
| El texto del informe afirmaba que el redondeo impedía distinguir a una persona entre dos exportaciones | Es falso en el borde del redondeo (13 → 15, 12 → 10): se documenta y queda una prueba que lo muestra |

**Lo que el informe todavía no resuelve** (decisión de quien responda por la protección de datos):
- Quien retira su autorización desaparece también de los meses ya cerrados. Dos exportaciones del mismo mes, antes y después, pueden diferir en los indicadores de esa persona. Regla operativa mientras tanto: **cada mes cerrado se publica una sola vez**.
- Con un mes de pocas personas conocidas entre sí (una sesión de validación de 10 a 15 personas), "<5" en un indicador raro sigue diciendo algo del grupo.
- El informe solo publica totales por indicador, nunca cruces entre indicadores; agregar cruces exigiría revisar todo de nuevo.
- Los patrones de barreras son conservadores: de seis frases coloquiales sintéticas reconocieron cuatro ("no me dan la cita" con otras palabras y "vivo en una vereda muy lejos" no). No se ajustaron a esas frases para no sobreajustar; lo que no capta un patrón depende del análisis v9, sin medir.

## Verificación
Automática (2026-11-16): 951 pruebas (845 antes), ruff y mypy --strict. Invariancia en ocho escenarios (urgencia por filtro 1 y por código, alarma prioritaria, evidencia, abstención, fuera de alcance, saludo y tema nuevo) en los modos `observar`, `activo` con textos aprobados y `activo` con textos pendientes. Recorrido visual con agente guionizado y datos sintéticos. Verificación integral del 2026-11-16: 1.041 pruebas; 774 de las 790 pruebas de `main` pasan sin cambios contra el código de la rama (las 16 restantes fallan solo por la firma de `create_app`, cambiada a propósito). **Pendiente:** todo lo que requiere Ollama. El procedimiento está en [estrategia de pruebas](../../06-calidad/estrategia-pruebas.md#comparación-del-prompt-de-análisis-v8-y-v9): las 40 pruebas en vivo con cada prompt y `scripts/compare_analysis_prompts.py` (122 casos sintéticos, con ruido del modelo y casos discordantes).
