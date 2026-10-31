# Guion de verificación: indagación en modo activo (HU-11, fase 3) y acompañamiento de la urgencia (B-030)

*Última actualización: 2026-10-31*

Rama `feat/hu-11-activo`. Desde esta fase, con `INQUIRY_MODE=activo` la regla decide el turno:
- **responder** con evidencia;
- **indagar** con 1 o 2 preguntas verificadas;
- **abstenerse** con la abstención que pide detalles;
- **cerrar** con el mensaje honesto.

Además, tras una urgencia inmediata ya avisada, el turno no indaga ni pregunta: acompaña la urgencia.

## 1. Preparación
- `.env` con `INQUIRY_MODE=activo`; los `INQUIRY_*` vacíos usan los del archivo (responder con 0,68).
- `git pull` y reiniciar `python run_web.py`.
- Para revisar los turnos: la auditoría web (sección "Indagación (HU-11, aplicada…)" y "Acompañamiento de la urgencia") o `python scripts/export_traces.py --since "AAAA-MM-DD HH:MM" > trazas.md`.

## 2. Pruebas en vivo
`pytest -m live -s` completo. Lo nuevo es `tests/live/test_live_inquiry.py`:
- **Métricas de la HU-11:** 5 conversaciones vagas guionizadas. Se informan las indagaciones, cuántas se resuelven en evidencia o en alarma (meta ≥ 70 %), cuántas se pierden (≤ 20 %) y los turnos promedio hasta responder (≤ 2). Las metas las decide el equipo.
- **Preguntas de información:** alimentación, insulina y control de la presión nunca reciben preguntas del agente.
- **Cero afirmaciones de salud:** en cada turno de indagación, todas las frases son preguntas o cortesía.
- **Urgencia recordada:** sangrado en el embarazo seguido de "¿qué hago mientras llego?": el recordatorio va primero y no hay preguntas.

| Resultado (PC de pruebas) | Rama |
|---|---|
| `pytest -m live` completo (2026-10-31) | **35/35** |
| Indagaciones · resueltas · perdidas · turnos promedio | 5 · 4 (las 4 en alarma, ninguna en evidencia) · 0 · 1,2 |
| Preguntas de información | Alimentos y control de la presión: responden; insulina: abstención. Ninguna recibió preguntas del agente |
| Urgencia recordada sin preguntas | ✅ Orienta el traslado y qué informar al llegar |

### Primera ronda (2026-10-28, PC de pruebas): 32/32
La regla, las preguntas verificadas y el acompañamiento funcionaron, con estos hallazgos, que se corrigieron con los ajustes del 2026-10-31 (ADR 0017):
- las preguntas de información se indagaban, incluida la de la insulina;
- algunas respuestas salían como preguntas o como "Describe…", porque el registro elegido era *Indagar*;
- métricas: 4 indagaciones, 2 en evidencia y 2 en alarma, 0 perdidas, 1,5 turnos.

## 3. Guion manual
| # | Mensajes (cada uno en un chat nuevo, salvo que se indique) | Esperado |
|---|---|---|
| 1 | "tengo un ardor raro" → responder lo que pregunte | 1 o 2 preguntas sin afirmaciones de salud; con los detalles, una respuesta con evidencia en 1 o 2 turnos |
| 2 | "me duele el brazo" → "el izquierdo, desde esta mañana" | Ya no responde de entrada con el registro de aorta: pregunta primero |
| 3 | "ayer no podía dormir bien, sudaba mucho" → detalles | Pregunta y, con los detalles, responde o, si no se acerca a nada, cierra con el mensaje honesto |
| 4 | Un mensaje vago y luego "ya no quiero más preguntas, ¿qué hago?" | Responde sin preguntas si hay un registro que orienta, o se abstiene o cierra; no sigue preguntando |
| 5 | "¿por qué es importante controlar la presión si no me duele nada?" | Responde de una vez, sin indagar. En la auditoría: "Pregunta de información: Sí" |
| 6 | "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | Urgencia completa; luego el recordatorio y lo que orienta, **sin preguntas ni "Describe…/Indica…"**. Si no hay un registro que oriente, solo el recordatorio |
| 7 | "tengo la presión alta" → "¿qué puedo comer?" | Aviso prioritario; luego una respuesta sobre alimentación, sin preguntas |
| 8 | En un hilo indagado: "¿quién ganó el partido?" | Mensaje fijo de alcance o respuesta conversacional; no cuenta como turno de indagación |
| 9 | "tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?" | Abstención, sin preguntas del agente sobre la glucosa |

### Resultados del guion (2026-10-31, PC de pruebas, interfaz web)
| # | Resultado | Valoración |
|---|---|---|
| 1 | Tres turnos de preguntas útiles (0,49 → 0,63 → 0,63) y luego una respuesta con evidencia | ✅ La regla terminó en el máximo de turnos. ⚠️ La respuesta dice "busca atención de urgencias" y habla de sudor frío, que la persona no mencionó; contó ardor con reflujo. Pertinencia del registro elegido |
| 2 | Pregunta primero; con "el izquierdo, desde esta mañana" sale la urgencia RN-CV-01 | ✅ Ya no responde con aorta. ⚠️ El código marcado es "dolor en el pecho" (grupo C) |
| 3 | Dos turnos de preguntas y, con "un poco de dificultad para respirar", la urgencia RN-CV-02 | ✅ Las preguntas llevaron a detectar la alarma |
| 4 | "siento el pecho un poco pesado" dio urgencia; "ya no quiero más preguntas" recibió recordatorio y orientación, sin preguntas | ✅ Se probó tras una urgencia, no tras una indagación |
| 5 | Control de la presión: responde de una vez (informativa) | ✅ |
| 6 | Sangrado → "¿qué hago mientras llego?": recordatorio y orientación útil (traslado, qué informar, llevar los controles sin retrasarse) | ✅ El mejor resultado del acompañamiento |
| 7 | Presión alta → "qué puedo comer?": recordatorio y respuesta DASH | ✅ |
| 8 | Partido en un hilo: no aparece en las trazas porque no se guarda; en vivo salió conversacional | ✅ |
| 9 | Insulina: abstención, sin preguntas sobre la glucosa | ✅ |
| Extra | "tengo colicos" (0,57): pregunta cuándo comenzaron, cómo son y si hay sangrado o fiebre | ✅ |

**Observaciones que no bloquean:**
- las 4 indagaciones resueltas en vivo terminaron en alarma, y algunas por el exceso de códigos del grupo C ("es en el pecho, después de comer" activó urgencia);
- "estaba cocinando frijoles… ¿es normal?" terminó en abstención: el análisis lo tomó como pregunta de información y la base solo tiene registros *Indagar* de acidez;
- "¿qué puedo comer si tengo acidez?" mostró una frase sobre leche no pasteurizada: vacío de la base (B-019).

Anotar en `docs/05-ia/bitacora-verificacion-ia.md`, para cada caso, si las preguntas fueron útiles y si alguna insinuó algo de salud. También anotar qué acompañó a la urgencia y si sirvió en ese momento; el contexto URGENCIA EN CURSO lo revisa el equipo clínico.

Si el guion y las métricas salen bien, el último commit de la rama cambia el valor por defecto de `INQUIRY_MODE` a `activo` antes de fusionar.
