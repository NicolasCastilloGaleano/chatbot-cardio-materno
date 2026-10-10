# Matriz de trazabilidad

*Última actualización: 2026-10-10*

Une los requisitos con su implementación y su verificación. Se actualiza cada vez que se crea o modifica una HU, una regla o una prueba.

| HU / Regla | Criterio de aceptación | Módulo / archivo | Prueba | Estado |
|---|---|---|---|---|
| HU-00 | Conversación básica (con historial) | `application/conversation_service.py` (antes `chat_service.py`), `adapters/outbound/llm/ollama_language_model.py` | `test_conversation_service.py`, `test_ollama_language_model.py` + prueba manual en el PC de pruebas | ✅ |
| HU-00 | Salir de la consola | `adapters/inbound/console/console_chat.py` | `tests/unit/test_console_chat.py` | ✅ (automática) |
| HU-00 | Ollama no disponible o modelo no instalado | `OllamaLanguageModel.verify_ready`, `bootstrap/main.py` | `test_ollama_language_model.py` (conexión, modelo faltante) | ✅ (automática) |
| HU-00 | Error durante la conversación | `console_chat.py`, `ollama_language_model.py` | `test_console_chat.py`, `test_ollama_language_model.py` (timeout, HTTP) | ✅ (automática) |
| HU-06 | El primer mensaje crea un hilo | `application/conversation_service.py`, `domain/conversation.py` | `test_conversation_service.py::test_first_message_opens_thread_and_stores_messages_with_thread_id` | ✅ (automática) |
| HU-06 | Un mensaje relacionado continúa el hilo | `conversation_service.py` | `test_continue_keeps_thread_and_updates_summary` | ✅ (automática) |
| HU-06 | Un cambio de tema cierra el hilo y abre otro | `conversation_service.py` | `test_new_topic_closes_current_thread_and_opens_another` | ✅ (automática) |
| HU-06 | Contexto acotado (JSON del hilo + N mensajes) | `conversation_service.py::_build_context` | `test_context_is_bounded_to_thread_json_and_last_n_messages` | ✅ (automática) |
| HU-06 | Salir cierra el hilo activo | `console_chat.py`, `ConversationService.end_session` | `test_console_chat.py::test_exit_closes_active_thread` | ✅ (automática) |
| HU-06 | Respuesta inválida o error del modelo | `application/agent_turn.py`, `conversation_service.py` | `test_agent_turn.py`, `test_model_failure_saves_nothing_and_keeps_thread` | ✅ (automática) |
| HU-06 | Calidad real de la decisión de hilo y del resumen | prompt v2 | Guion manual en el PC de pruebas (2026-10-10) | ✅ |
| HU-01 / RN-01 | Primer contacto → aviso + consentimiento | TODO | TODO | ⏳ |
| HU-03 / RN-02 | Signo de alarma → urgencias primero | TODO | TODO | ⏳ |
