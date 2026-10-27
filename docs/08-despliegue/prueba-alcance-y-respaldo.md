# Guion de verificación: correcciones de alcance y respaldo (B-025)

*Última actualización: 2026-10-26*

Rama `fix/alcance-y-respaldo`. Cubre los escenarios nuevos de HU-02 y HU-07 del 2026-10-26. Se ejecuta en el PC de pruebas **después** de verificar la HU-10 en `main`, para no mezclar causas si algo falla.

## 1. Preparación
1. `.env` con la base v1: `KB_ENTRIES_FILE=knowledge/kb/entries.jsonl` y `KB_INDEX_DIR=data/kb_index`.
2. **Línea base en `main`.** Ejecutar `git checkout main` y luego `pytest -m live -s`. En la salida de `test_live_grounding.py`, anotar cuántas respuestas terminan en:
   - frases verificadas;
   - `literal`;
   - `abstención`.
3. **En la rama.** Ejecutar `git checkout fix/alcance-y-respaldo` y luego `pytest -m live -s`, y anotar los mismos conteos.

| Resultado (2026-10-26, PC de pruebas) | `main` | Rama |
|---|---|---|
| Frases verificadas | 2 de 4 (4/4 y 3/3) | 2 de 4 (4/4 y 3/3) |
| Texto literal | 1 de 4 (qué comer con acidez) | 1 de 4 (la misma) |
| Abstención | 1 de 4 (insulina) | 1 de 4, ahora termina pidiendo detalles |
| Sonda de recuperación | top-3 16/16 · top-1 13 · útil con 0,50 15/16 | igual |
| `pytest -m live` (aprobadas/total) | 26/26 (15:05) | 26/26 (14:52) |

**Lectura:** quitar la excepción de remisión (corrección 5) no aumentó los textos literales en la sonda, y los resultados de alcance, análisis y alarmas no cambiaron. La muestra de respaldo es pequeña (4 preguntas), así que el guion manual sigue siendo necesario.

**Criterio:** si el texto literal sube mucho (lo decide el equipo), se revierte solo el commit de la corrección 5 ("las frases de remisión ya no se eximen…").

## 2. Guion manual (consola con `SHOW_THREAD_DEBUG=true`, o interfaz web)

| # | Mensajes | Esperado |
|---|---|---|
| 1 | "mi bebé tiene fiebre" → (el asistente pregunta) → "sí, desde ayer" | El segundo mensaje se atiende en el mismo hilo, nunca con el mensaje fijo de alcance (HU-07) |
| 2 | En ese mismo hilo: "¿quién ganó el partido?" y luego "¿y qué más hago?" | El primero recibe el mensaje fijo, que termina con "¿Tienes alguna duda o molestia…?", y **no se guarda**. El segundo sigue el hilo |
| 3 | "¿qué opinas del fútbol?" (sin hilo) | Mensaje fijo con la pregunta final; no se guarda |
| 4 | "tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?" | Abstención que termina pidiendo "qué sientes, desde cuándo y a quién le pasa"; no se llama al modelo de respuesta |
| 5 | Con `RAG_ENABLED=false` (o sin índice), cualquier consulta de salud | "En este momento no puedo consultar la información…", sin pedir detalles |
| 6 | "estoy embarazada y siento que el corazón me palpita muy rápido" | Si la búsqueda en materno-infantil no basta, la depuración muestra "· ampliada a los dos dominios" y la respuesta cita un registro cardiovascular |
| 7 | "tengo acidez en el embarazo" | Si la respuesta termina en texto literal, es el registro de acidez, no uno de preeclampsia |
| 8 | "estoy sangrando mucho y tengo 30 semanas" | La alarma se comporta igual que en `main` (mensaje fijo de urgencia) |

### Resultado del guion manual (2026-10-26, PC de pruebas, interfaz web)
| # | Resultado |
|---|---|
| 1 y 2 | **No evaluables.** "mi bebé tiene fiebre" activó RN-MI-13 (fiebre en recién nacido) por el filtro 2, sin que la persona diera la edad. Además, "sí, desde ayer" y "¿quién ganó el partido?" repitieron la misma alarma, porque el análisis acumula los síntomas del hilo. Es un problema que ya existía en `main`, no de B-025 |
| 3 | No ejecutado |
| 4 | ✅ Abstención que termina pidiendo detalles |
| 5 | No ejecutado |
| 6 | ✅ Probable: hilo materno-infantil con respuesta desde un registro cardiovascular de palpitaciones (la búsqueda ampliada); falta confirmar `domain_fallback` en la traza |
| 7 | **No evaluable.** En el hilo de las palpitaciones, "tengo acidez en el embarazo" activó RN-CV-01 (dolor u opresión en el pecho) |
| 8 | No ejecutado |

**Decisión del usuario:** se da por verificada sin regresiones y se fusiona a `main`. Los hallazgos de alarmas, el exceso de códigos del filtro 2 y las alarmas que se repiten en cada turno del hilo, quedan como trabajo previo a la HU-11. También se observó que un hilo nuevo arrastró en su resumen el tema del hilo anterior (error del análisis, a vigilar).

## 3. Resultado
Anotar los hallazgos en `docs/05-ia/bitacora-verificacion-ia.md`. Si todo pasa, se fusiona a `main` con la aprobación del usuario y B-025 queda verificado.
