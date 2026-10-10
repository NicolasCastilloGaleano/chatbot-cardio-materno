# application

**Responsabilidad:** casos de uso (p. ej., manejar el mensaje entrante), máquina de estados conversacional y PUERTOS (interfaces con typing.Protocol en ports/) que el núcleo necesita del exterior.

Implementado: `ConversationService` (hilos, alarmas, dos llamadas y evidencia), `agent_turn.py` (contratos de análisis y respuesta), `evidence.py`, `turn_context.py`, `alarm_policy.py`, `stage_timer.py` y los puertos `LanguageModel`, `ThreadRepository`, `KnowledgeRetriever` y `Embedder`.
Previstos: AlertNotifier, MessageChannel.

**Puede importar:** domain.
**NO puede importar:** adapters, bootstrap ni librerías de infraestructura.
