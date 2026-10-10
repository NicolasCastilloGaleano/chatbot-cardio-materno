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
| HU-03 / RN-02 / RN-MI-xx | Urgencia en el mensaje del usuario → solo el mensaje fijo, sin LLM | `domain/alarms.py`, `application/alarm_policy.py`, `conversation_service.py::send` | `test_conversation_service.py::test_urgent_user_message_skips_agent_and_opens_alarm_thread` | ✅ (automática) |
| HU-03 / RN-MI-xx | Alarma detectada en los síntomas reportados por el agente | `conversation_service.py::_post_filter` | `test_agent_reported_symptom_triggers_urgent_alarm_and_discards_reply` | ✅ (automática) |
| HU-03 / RN-MI-01 | Descripción coloquial de un sangrado (regresión del 2026-10-10) | `knowledge/alarm_rules.json` v0.2.0 | `tests/conversational/alarm_phrases.json` (RN-MI-01) | ✅ (automática) |
| HU-03 / RN-MI-06 | Redacción alternativa del agente ("movimientos del bebé", regresión 2 del 2026-10-10) | catálogo v0.3.0 | `alarm_phrases.json` (RN-MI-06) | ✅ (automática) |
| HU-03 / HU-04 | Cada regla se activa con su nombre canónico (puente B-015) | `AlarmRule.matches`, `render_system_prompt`, prompt v5 | `test_rule_triggers_with_its_own_sign_name_as_the_agent_would_report_it`, `test_render_system_prompt_inserts_unique_sign_names` | ✅ (automática) |
| HU-03 | Los síntomas reportados por el agente quedan registrados | `conversation_service.py::_record_turn`, `json_file_thread_repository.py`, `console_chat.py::format_symptoms_debug` | `test_reported_symptoms_are_stored_in_assistant_message_and_result`, `test_reported_symptoms_round_trip_only_for_assistant_messages`, `test_debug_shows_symptoms_reported_by_agent` | ✅ (automática) |
| HU-03 | Los consejos del agente no generan alarmas | `_post_filter` (solo `reported_symptoms`) | `test_advice_in_reply_or_summary_does_not_trigger_alarm` | ✅ (automática) |
| HU-04 / RN-CV-01 | Urgencia cardiovascular | catálogo + `conversation_service.py` | `tests/conversational/test_alarm_phrases.py` (RN-CV-01) | ✅ (automática) |
| HU-04 / RN-CV-06 | Consulta prioritaria: mensaje fijo + orientación | `alarm_policy.py::compose_reply` | `test_priority_user_message_shows_fixed_notice_then_agent_reply` | ✅ (automática) |
| HU-04 | La alarma prioritaria se muestra aunque falle el modelo | `conversation_service.py::send` | `test_priority_alarm_survives_agent_failure` | ✅ (automática) |
| HU-04 | El agente eleva la severidad, nunca la reduce | `_agent_turn`, `compose_reply` | `test_agent_can_escalate_priority_to_urgent`, `test_rule_detected_by_both_filters_is_recorded_once_as_user` | ✅ (automática) |
| RN-MI-01 … RN-CV-06 | Cada regla activa sus frases de referencia y no las cotidianas | `knowledge/alarm_rules.json` | `tests/conversational/test_alarm_phrases.py` | ✅ (automática); ❌ validación clínica |
| HU-03 / HU-04 | Comportamiento con el modelo real | prompt v5 + catálogo v0.3.0 | Guion en el PC de pruebas (2026-10-10): urgencias por filtro 1 sin consultar al LLM; prioritaria con mensaje fijo + agente; tres frases coloquiales detectadas por el filtro 2 (origen `agente`); una pregunta educativa que nombra 8 signos sin alerta | ✅ |
