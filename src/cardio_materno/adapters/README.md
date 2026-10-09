# adapters

Implementaciones concretas, en el borde del hexágono.
- inbound/: traducen un canal externo a llamadas a casos de uso.
- outbound/: implementan los puertos de application.

**Puede importar:** application, domain y librerías externas.
**NO puede importar:** otro adaptador.
