# Matriz de trazabilidad

*Última actualización: 2026-10-10*

Une los requisitos con su implementación y su verificación. Se actualiza cada vez que se crea o modifica una HU, una regla o una prueba.

| HU / Regla | Criterio de aceptación | Módulo / archivo | Prueba | Estado |
|---|---|---|---|---|
| HU-00 | Conversación básica (con historial) | `application/chat_service.py`, `adapters/outbound/llm/ollama_language_model.py` | `tests/unit/test_chat_service.py`, `test_ollama_language_model.py` + prueba manual en el PC de pruebas | 🔄 |
| HU-00 | Salir de la consola | `adapters/inbound/console/console_chat.py` | `tests/unit/test_console_chat.py` | ✅ (automática) |
| HU-00 | Ollama no disponible o modelo no instalado | `OllamaLanguageModel.verify_ready`, `bootstrap/main.py` | `test_ollama_language_model.py` (conexión, modelo faltante) | ✅ (automática) |
| HU-00 | Error durante la conversación | `console_chat.py`, `ollama_language_model.py` | `test_console_chat.py`, `test_ollama_language_model.py` (timeout, HTTP) | ✅ (automática) |
| HU-01 / RN-01 | Primer contacto → aviso + consentimiento | TODO | TODO | ⏳ |
| HU-03 / RN-02 | Signo de alarma → urgencias primero | TODO | TODO | ⏳ |
