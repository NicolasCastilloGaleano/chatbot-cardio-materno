# Procesos

- `flujos/`: diagramas de flujo y de estados en Mermaid (se renderizan en GitHub). Son la fuente del comportamiento conversacional.
- `bpmn/`: modelos BPMN 2.0 (`.bpmn`) del proceso de teleorientación con sus actores (usuario, asistente, equipo de salud, DTS). Se editan en https://demo.bpmn.io y se exporta un `.svg` con el mismo nombre.

| Proceso | Flujo | BPMN | Estado |
|---|---|---|---|
| Atención conversacional general (incluye el turno con hilos, HU-06) | [flujo-conversacional.md](flujos/flujo-conversacional.md) | TODO: modelar en bpmn.io cuando se estabilice el flujo con consentimiento | Borrador + turno implementado |
| Turno con análisis, RAG y respuesta (HU-02) | [flujo-conversacional.md](flujos/flujo-conversacional.md) (sección "Turno implementado") | Incluido en `gestion-alerta.bpmn` (rama no urgente) | Implementado |
| Gestión de alerta por signos de alarma (HU-03/04) | [gestion-alerta.md](flujos/gestion-alerta.md) | [gestion-alerta.bpmn](bpmn/gestion-alerta.bpmn) (TODO: exportar `.svg` desde bpmn.io) | Implementado |
| Ruta de atención por municipio (HU-05) | TODO | TODO | ⏳ Depende de la DTS |
