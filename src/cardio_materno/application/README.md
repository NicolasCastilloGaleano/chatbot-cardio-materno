# application

**Responsabilidad:** casos de uso (p. ej., manejar el mensaje entrante), máquina de estados conversacional y PUERTOS (interfaces con typing.Protocol en ports/) que el núcleo necesita del exterior: LanguageModel, KnowledgeRetriever, ConversationRepository, AlertNotifier, MessageChannel.

**Puede importar:** domain.
**NO puede importar:** adapters, bootstrap ni librerías de infraestructura.
