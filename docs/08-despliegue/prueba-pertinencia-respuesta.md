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

| Resultado (2026-10-27, PC de pruebas) | `main` | Rama |
|---|---|---|
| Frases verificadas | 2 de 4 (presión 3/3, frijoles 3/3) | 3 de 5 (presión 2/2, frijoles 3/3, alimentos y presión 2/2) |
| Texto literal (frases mostradas/total) | 1 de 4: acidez, registro completo (5 frases) | 1 de 5: acidez, **3/5 frases**; se ocultaron "¿Hay sabor ácido…?" y "Estos datos ayudan a distinguir…" y se mantuvo el aviso de atención inmediata |
| Abstención | 1 de 4 (insulina) | 1 de 5 (insulina) |
| Frases por respuesta verificada | 3 y 3 | 2, 3 y 2 |
| `pytest -m live` completo | — | **27/27** (análisis, respaldo, sonda top-3 16/16 · top-1 13 · útil 15/16, filtro 2, alcance 12/12) |

## 2. Guion manual
| # | Mensajes (en el mismo chat) | Esperado |
|---|---|---|
| 1 | "¿qué alimentos ayudan a controlar la presión arterial?" | Respuesta solo sobre alimentación (DASH, sodio…), sin frases sobre medicamentos, líquidos u otros temas. El número de frases puede ser menor que 5 |
| 2 | Chat nuevo: "estoy embarazada y estoy sangrando" → "¿qué hago mientras llego?" | Urgencia completa y luego el recordatorio (B-027). Si la respuesta sale como literal, ya no aparecen las frases sobre las relaciones ni las que no comparten términos con el caso; se ven "N/M frases" en la auditoría |
| 3 | Chat nuevo: "tengo acidez en el embarazo, ¿qué puedo comer?" | Si sale como literal, solo las frases de la acidez y de la alimentación; los avisos de atención inmediata se mantienen |
| 4 | Chat nuevo: "tengo la presión alta" → "¿qué puedo comer?" | El aviso prioritario y la respuesta; la segunda respuesta habla de alimentación, sin la molestia en el pecho que la persona no mencionó |
| 5 | Revisión de cualquier respuesta con texto literal (no es un mensaje nuevo: se revisa, p. ej., la del caso 3) | La auditoría muestra "Frases del registro mostradas N/M". Si una frase importante quedó oculta, anotarla con el mensaje: sirve para calibrar `GROUNDING_LITERAL_MIN_OVERLAP` o los marcadores de aviso |

### Resultados del guion (2026-10-27, PC de pruebas, interfaz web)
| # | Resultado | Valoración |
|---|---|---|
| 1 | Dos frases sobre el sodio (embutidos, caldos, versiones sin sal); la primera es una pregunta de un registro *Indagar* sin "¿" | ✅ Pertinente y breve. ⚠️ Pobre: no aparece el patrón DASH, que sí está en la base (lo trajo el caso 4). Depende de la recuperación |
| 2 | Urgencia completa; luego el recordatorio y una respuesta verificada sobre de dónde sale la sangre, la cantidad y las semanas | ✅ Ya no pregunta por las relaciones. ⚠️ Sigue sin responder "qué hago mientras llego": la base no tiene ese contenido |
| 3 | Literal con 3/5 frases: ardor, semanas y productos, y el aviso de atención inmediata | ✅ El literal es más corto y conserva el aviso. ⚠️ El registro es *Indagar*: la base no tiene "qué comer con acidez" (vacío conocido, B-019) |
| 4 | Aviso prioritario y una respuesta que vuelve a hablar de molestia en el pecho; luego el recordatorio y una respuesta DASH y sodio | ✅ La segunda respuesta es pertinente. ⚠️ La primera sigue con frases del pecho que la persona no mencionó, y la segunda termina con "Evita copiar recomendaciones de pacientes con insuficiencia cardíaca", que no aplica. El prompt v4 mejora poco la elección del modelo |
| 5 | Revisado en el caso 3: 3/5, sin perder el aviso. Lo oculto ("¿Hay sabor ácido, vómitos o dificultad para alimentarte?") era útil a medias | ✅ Sin pérdidas importantes |

**Conclusión:** B-028 no daña (27/27 en vivo, la misma abstención, alarmas sin cambios) y el literal mejora de forma medible. El prompt v4 da respuestas más cortas, pero el modelo de respuesta (qwen3:8b) sigue usando a veces frases que no aplican. La mayor parte de lo que falta es de recuperación y de cobertura de la base, que atacan la HU-11 (caracterizar antes de responder) y B-019.

Anotar los resultados en `docs/05-ia/bitacora-verificacion-ia.md`.
