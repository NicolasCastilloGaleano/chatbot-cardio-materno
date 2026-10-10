# adapter outbound: llm

Implementa el puerto `LanguageModel` con Ollama local (ADR 0005): `ollama_language_model.py` (`/api/chat` con JSON Schema) y `ollama_http.py` (cliente HTTP compartido con los embeddings). Se usa en dos llamadas: análisis y respuesta (ADR 0008). Nunca recibe PII. Los prompts están en `src/cardio_materno/prompts/`.
