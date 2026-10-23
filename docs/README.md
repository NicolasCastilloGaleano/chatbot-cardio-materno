# Documentación del proyecto

Documentación **viva**: se actualiza en la misma tarea que el código (AGENTS.md §6). Está organizada según los entregables de los *Lineamientos Generales PI II v4*.

## Índice
| Carpeta | Contenido | Entregable de los lineamientos |
|---|---|---|
| [00-gestion](00-gestion/) | Project Charter, backlog, Definition of Done, sprints, [pendientes de aprobación](00-gestion/pendientes-aprobacion.md), [plan de migración a la base RAG v2](00-gestion/plan-migracion-rag2.md) | §3.1 Charter, backlog; §6 artefactos ágiles |
| [01-especificacion](01-especificacion/) | Especificación ejecutable, historias de usuario, RNF, glosario, trazabilidad | §3.1 Especificación ejecutable v1 |
| [02-arquitectura](02-arquitectura/) | Documento de arquitectura (componentes, flujo de datos, despliegue) y ADR | §3.2 Documento de arquitectura |
| [03-procesos](03-procesos/) | BPMN (`.bpmn`) y diagramas de flujo (Mermaid) | Soporte de la especificación y la arquitectura |
| [04-datos](04-datos/) | Modelo de datos y diccionario de datos | §3.5 Documentación técnica |
| [05-ia](05-ia/) | Playbook de orquestación de IA, bitácora de verificación, prompts versionados | §3.2 Playbook, §3.3 Bitácora |
| [06-calidad](06-calidad/) | Estándares de código, estrategia de pruebas y [auditoría de lineamientos](06-calidad/auditoria-lineamientos.md) | §8 Calidad de código |
| [07-gobernanza](07-gobernanza/) | Riesgos de IA, sesgos, protección de datos | §3.6 Informe de gobernanza ética |
| [08-despliegue](08-despliegue/) | Instalación, despliegue y operación | §3.5 Guía de instalación |

Los informes de validación (§3.4) y el business case (§3.7) se añadirán como `09-validacion/` y `10-negocio/` cuando llegue su semana.

## Matriz de impacto documental
**Antes de cerrar una tarea, recorrer esta tabla.** Si el cambio coincide con una fila, actualizar los documentos indicados.

| Si el cambio… | Actualizar |
|---|---|
| Cualquier cambio en `src/`, `tests/` o `knowledge/` | `CHANGELOG.md` + `05-ia/bitacora-verificacion-ia.md` (**siempre**) |
| Agrega o modifica una funcionalidad visible al usuario | `01-especificacion/historias-usuario.md`, `01-especificacion/trazabilidad.md`, `00-gestion/backlog.md` |
| Cambia el flujo conversacional o los estados | `03-procesos/flujos/*.md` y el BPMN correspondiente en `03-procesos/bpmn/` |
| Cambia reglas clínicas, signos de alarma o rutas de atención (`knowledge/alarm_rules.json`) | `01-especificacion/especificacion-ejecutable.md` (§4.1), `01-especificacion/solicitud-validacion-alarmas.md`, `tests/conversational/alarm_phrases.json`, `03-procesos/` (flujo + BPMN de gestión de alerta), `07-gobernanza/riesgos-ia.md` + **validación clínica humana** |
| Agrega o modifica un componente, capa, puerto o adaptador | `02-arquitectura/arquitectura.md` |
| Toma una decisión técnica relevante (librería, proveedor, patrón) | Nuevo ADR en `02-arquitectura/adr/` |
| Cambia entidades, tablas o esquemas | `04-datos/modelo-datos.md`, `04-datos/diccionario-datos.md` |
| Cambia la base de conocimiento (`knowledge/kb/entries.jsonl`) o la política de evidencia | `knowledge/kb/README.md` (validación), reconstruir el índice, `tests/live/retrieval_probe.json`, `07-gobernanza/riesgos-ia.md` (R-10) |
| Cambia prompts del LLM o la configuración del modelo | `05-ia/prompts/` (versionado), `05-ia/playbook-orquestacion-ia.md`, `07-gobernanza/riesgos-ia.md` |
| Cambia el manejo de datos personales | `07-gobernanza/proteccion-datos.md` |
| Cambia dependencias, variables de entorno o la forma de ejecutar | `08-despliegue/instalacion.md`, `.env.example`, `README.md` |
| Agrega un tipo de prueba o cambia la estrategia | `06-calidad/estrategia-pruebas.md` |
| Introduce una convención nueva | `AGENTS.md`, `06-calidad/estandares-codigo.md` |

## Convenciones de documentos
- Markdown y diagramas en **Mermaid** (se renderizan en GitHub). El BPMN va en `.bpmn` (editable en https://demo.bpmn.io) con una exportación `.svg` al lado.
- Lo pendiente se marca con `TODO:`.
- Cada documento empieza con *Última actualización: AAAA‑MM‑DD*.
