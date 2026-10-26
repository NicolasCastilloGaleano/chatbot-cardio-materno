# ADR 0008: RAG con índice propio y separación análisis/respuesta en dos llamadas

- **Estado:** Aceptado
- **Fecha:** 2026-10-10
- **Decisores:** Nicolas Castillo Galeano (equipo de desarrollo). El contenido de la base fue aceptado como validado para el prototipo por **Miguel, líder del proyecto** (TODO: apellido).
- **Relacionado:** ADR 0004 (reglas deterministas), ADR 0006 (hilos), ADR 0007 (alarmas con doble filtro).

## Contexto
- El agente orientaba solo con su conocimiento general (actividad 2.2 sin respaldo).
- El piloto anterior (`piloto-agente-nanomaterno-cardiovascular`) tenía:
  - una base de **1.600 pares pregunta/respuesta** (2 dominios × 8 categorías × 100, enfoques *Indagar* y *Solucionar*), generada con IA (ChatGPT Work, con búsqueda de fuentes);
  - un buscador híbrido calibrado: vectores + BM25 + RRF + umbral 0,55 + instrucción Qwen3.
- **Preocupación del usuario:** si la evidencia entra en la misma llamada que extrae `reported_symptoms`, puede **contaminar** el filtro 2 (falsos positivos con síntomas tomados de la evidencia) o **minimizar** síntomas (falsos negativos).

## Decisión
1. **Contenido versionado:** la base se exporta una vez a `knowledge/kb/entries.jsonl` (`scripts/export_pilot_kb.py`) y queda en git, revisable.
2. **Índice propio derivado, no versionado:** `data/kb_index/` contiene `embeddings.npy`, `ids.json` y `manifest.json` (modelo, dimensión y hash de la base). Se construye con `run_build_kb_index.py` en el PC de pruebas (GPU) con `qwen3-embedding:8b` y el mismo texto de embedding del piloto, para conservar la calibración. Si el modelo o la base no coinciden con el manifiesto, el RAG no se activa y se avisa cómo reconstruirlo.
3. **Buscador híbrido** portado del piloto en funciones pequeñas:
   - similitud coseno con **numpy** + BM25 en memoria + RRF;
   - **solo la similitud vectorial certifica**: un registro encontrado únicamente por términos no califica;
   - umbral y `top_k` en `knowledge/evidence_policy.json`.
4. **Dos llamadas al agente:**
   - **Análisis (sin evidencia):** hilo, dominio, resumen y `reported_symptoms` → filtro 2.
   - **Respuesta (con evidencia):** solo si no hubo urgencia; texto + `evidence_ids`.

   La evidencia **nunca** llega al análisis, así no puede alterar el filtro de seguridad. Las urgencias detectadas por el filtro 2 ya no buscan evidencia ni redactan una respuesta para descartarla.
5. **Solo evidencia para afirmaciones de salud** (*actualizado por el [ADR 0010](0010-respuesta-verificada-y-abstencion-determinista.md): la abstención ya no depende del prompt y cada frase se verifica de forma determinista*):
   - el prompt de respuesta exige usar únicamente la EVIDENCIA y citar sus etiquetas;
   - el JSON Schema restringe `evidence_ids` a las etiquetas ofrecidas (`enum`) y la aplicación lo valida;
   - sin evidencia, el agente lo dice y remite al personal de salud;
   - si hubo evidencia y no se citó, queda la marca `uncited_reply`.
6. **Trazabilidad:** cada respuesta guarda en el hilo una `trace` con síntomas, evidencia ofrecida (id, etiqueta, puntaje, categoría), citas, estado de la búsqueda y **tiempos por etapa**.
   *Actualización (2026-10-11, B-021):* la consulta de búsqueda es el `search_query` que reformula el análisis, sin el contexto ajeno del mensaje; si viene vacío, se usa mensaje + resumen + síntomas. El análisis sigue sin recibir evidencia.
7. **Modelos por etapa:** `OLLAMA_ANALYSIS_MODEL` y `OLLAMA_REPLY_MODEL` (vacío = `OLLAMA_MODEL`).
8. **Dependencias de ejecución:** se agrega `numpy` (`requirements.txt`). Termina la regla de "cero dependencias" del ADR 0005. En Ubuntu 24.04 hay que usar un entorno virtual (PEP 668).

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Copiar `data/kb` (ChromaDB) del piloto | No recalcula embeddings | Dependencia pesada (chromadb), atada a la versión 1.5.9; contenido no versionado |
| Una sola llamada con evidencia + regla en el prompt | Menos latencia | Sin garantía estructural contra la contaminación del filtro 2 |
| Evidencia preferente (el LLM completa si falta) | Más respuestas útiles | Riesgo de inventar; incoherente con la Res. 2654 y el ADR 0004 |
| Similitud en Python puro (sin numpy) | Cero dependencias | ~1–3 s por consulta con vectores de 4.096 dimensiones |

## Consecuencias
- ✅ Respuestas respaldadas y auditables (qué registro se usó y con qué puntaje), sin contaminación del filtro 2 y con el contenido revisable en git.
- ✅ La búsqueda usa el resumen y los síntomas del análisis, así que es más precisa que con el mensaje solo.
- ⚠️ **Dos llamadas al modelo de 24B por turno:** más latencia, que se mide en `[tiempos …]` y se mitiga con modelos por etapa.
- ⚠️ **La verificación léxica de que cada frase esté en la evidencia todavía no existe** (B-018, riesgo R-10). Hoy "solo evidencia" se garantiza por prompt + citas restringidas.
- ⚠️ El contenido fue generado con IA. Su validación para el prototipo es una decisión del líder del proyecto; para usuarios reales se requiere la validación clínica (B-019: columnas Fuente/Validado por/Fecha).
- ⚠️ El resumen del hilo incorpora cada respuesta un turno después (ver la nota del ADR 0006).
- El umbral 0,55 viene calibrado del piloto; se verifica con la sonda en vivo (`pytest -m live`).

## Actualización 2026-10-10: latencia medida
En el PC de pruebas cada turno tardó unos 60 s (análisis 13–23 s, RAG 7,2 s, respuesta 28–38 s). Hipótesis: el LLM de 24B y el embedder de 8B no caben juntos en 8 GB de VRAM y se recargan en cada turno. Se agregan ajustes configurables, sin cambiar el comportamiento por defecto a ciegas:
- `OLLAMA_KEEP_ALIVE` (30m) en todas las solicitudes;
- `OLLAMA_EMBED_NUM_GPU` (`0` = embedder en CPU).

El diagnóstico está en `docs/08-despliegue/operacion.md`. Además, los mensajes fuera de alcance y conversacionales ya no buscan evidencia (ADR 0009).

## Actualización 2026-10-26: búsqueda ampliada a los dos dominios
- **Motivo:** la búsqueda se limita al dominio que decide el análisis. Si el análisis se equivoca (p. ej., palpitaciones de una gestante marcadas como materno-infantil), la persona recibe la abstención aunque la base tenga un registro adecuado en el otro dominio.
- **Decisión:** si la búsqueda en el dominio del análisis es insuficiente, se repite una vez en los dos dominios, con el mismo texto y el mismo umbral (`ConversationService._search`). Solo se usa ese resultado si es suficiente. No se repite cuando la primera búsqueda ya encontró evidencia, cuando el dominio era "ninguno" ni cuando el buscador no está disponible.
- **Auditoría:** la traza guarda `domain_fallback`, que se muestra en la interfaz web y en la depuración de la consola.
- **Costo:** `HybridRetriever` reutiliza el embedding de la última consulta, así que la segunda búsqueda no vuelve a llamar al modelo de embeddings. Solo ocurre en los turnos que hoy terminan en abstención.
