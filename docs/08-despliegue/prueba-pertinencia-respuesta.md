# Guion de verificación: pertinencia de la respuesta (B-028, ADR 0010)

*Última actualización: 2026-10-27*

Rama `fix/pertinencia-respuesta`. Cubre los escenarios de la HU-02 del 2026-10-27:
- la respuesta cita solo lo que aplica al caso (prompt de respuesta v4);
- el texto literal muestra solo las frases pertinentes del registro, siempre con los avisos de atención.

Usar la interfaz web (sección "Verificación del respaldo" de la auditoría, con "Frases del registro mostradas") o la consola con `SHOW_THREAD_DEBUG=true`, que muestra `[respaldo: … · texto literal del registro (N/M frases)]`.

## 1. Pruebas en vivo, comparadas con `main`
1. En `main`: ejecutar `pytest -m live -s tests/live/test_live_grounding.py` y anotar, por pregunta, el tipo de respuesta (frases verificadas, literal o abstención) y cuántas frases tiene. La prueba nueva de alimentación y la presión no existe en `main`: se compara solo en la rama.
2. En la rama: repetir y anotar lo mismo, además de las citas y, en los literales, "N/M frases del registro".
3. Ejecutar `pytest -m live -s` completo en la rama, para confirmar que no hay regresiones en el análisis, el alcance, el filtro 2 ni la sonda.

| Resultado (PC de pruebas) | `main` | Rama |
|---|---|---|
| Frases verificadas | | |
| Texto literal (frases mostradas/total) | | |
| Abstención | | |
| Frases por respuesta verificada | | |
| `pytest -m live` completo | | |

## 2. Guion manual
| # | Mensajes (en el mismo chat) | Esperado |
|---|---|---|
| 1 | "¿qué alimentos ayudan a controlar la presión arterial?" | Respuesta solo sobre alimentación (DASH, sodio…), sin frases sobre medicamentos, líquidos u otros temas. El número de frases puede ser menor que 5 |
| 2 | Chat nuevo: "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | Urgencia completa y luego el recordatorio (B-027). Si la respuesta sale como literal, ya no aparecen las frases sobre las relaciones ni las que no comparten términos con el caso; se ven "N/M frases" en la auditoría |
| 3 | Chat nuevo: "tengo acidez en el embarazo, ¿qué puedo comer?" | Si sale como literal, solo las frases de la acidez y de la alimentación; los avisos de atención inmediata se mantienen |
| 4 | Chat nuevo: "tengo la presión alta" → "¿qué puedo comer?" | El aviso prioritario y la respuesta; la segunda respuesta habla de alimentación, sin la molestia en el pecho que la persona no mencionó |
| 5 | Cualquier respuesta con texto literal | La auditoría muestra "Frases del registro mostradas N/M". Si una frase importante quedó oculta, anotarla con el mensaje: sirve para calibrar `GROUNDING_LITERAL_MIN_OVERLAP` o los marcadores de aviso |

Anotar los resultados en `docs/05-ia/bitacora-verificacion-ia.md`.
