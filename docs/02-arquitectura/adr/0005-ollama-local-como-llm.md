# ADR 0005: Ollama local como proveedor del LLM (prototipo)

- **Estado:** Aceptado
- **Fecha:** 2026-10-10
- **Decisores:** equipo de desarrollo (Nicolas Castillo Galeano)

## Contexto
El prototipo necesita un modelo de lenguaje para conversar (HU-00, actividad 2.2). El equipo ya trabajó con Ollama en el piloto anterior. Además, hay un PC de pruebas con capacidad para ejecutar modelos locales. En este proyecto se manejan datos de salud, que son sensibles según la Ley 1581/2012.

## Decisión
- Usar **Ollama local** (en el PC de pruebas), con el modelo **`mistral-small3.1:24b`** por defecto. Es configurable con `OLLAMA_MODEL`.
- El adaptador `OllamaLanguageModel` usa la API HTTP (`/api/chat` sin streaming y `/api/tags` para verificar el modelo al arrancar) **solo con la librería estándar** (`urllib`). Así el chat no tiene dependencias de ejecución.
- La configuración vive en `.env`: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_TEMPERATURE` y `OLLAMA_NUM_CTX`.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| API en la nube (OpenAI, Anthropic, Gemini) | Modelos más capaces; no requiere hardware | Los datos salen del equipo; costos; exige anonimización estricta desde el día 1 |
| SDK oficial `ollama` de Python | API más cómoda | Agrega una dependencia de instalación en el PC de pruebas |
| Modelo pequeño (`ministral-3:3b`, el del piloto) | Más rápido | Menor calidad de respuesta en español |

## Consecuencias
- ✅ Los datos no salen del equipo, no hay costo por uso y se puede cambiar de modelo editando `.env`.
- ⚠️ El rendimiento depende del hardware del PC de pruebas. Un modelo de 24B puede tardar; se mitiga con `OLLAMA_TIMEOUT_SECONDS`.
- ⚠️ Para el despliegue en Telegram o WhatsApp habrá que decidir dónde corre Ollama (servidor con GPU), en un ADR futuro.
- El puerto `LanguageModel` permite cambiar a otro proveedor sin tocar el núcleo (ADR 0001).
