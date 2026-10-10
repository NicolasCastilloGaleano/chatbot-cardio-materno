# application

**Responsabilidad:** casos de uso (p. ej., manejar el mensaje entrante), máquina de estados conversacional y PUERTOS (interfaces con typing.Protocol en ports/) que el núcleo necesita del exterior.

Implementado: `ConversationService` (hilos, HU-06), `agent_turn.py` (contrato JSON del agente) y los puertos `LanguageModel` y `ThreadRepository`.
Previstos: KnowledgeRetriever, AlertNotifier, MessageChannel.

**Puede importar:** domain.
**NO puede importar:** adapters, bootstrap ni librerías de infraestructura.
