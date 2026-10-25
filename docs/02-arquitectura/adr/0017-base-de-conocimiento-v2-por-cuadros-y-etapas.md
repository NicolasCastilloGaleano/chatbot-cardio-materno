# ADR 0017: Base de conocimiento v2 por cuadros y etapas

- **Estado:** Propuesto (pendiente de aprobación del equipo). La carga de la base v2 en el asistente (MIG-07) depende además de las puertas P1 y P7 del [plan de migración](../../00-gestion/plan-migracion-rag2.md)
- **Fecha:** 2026-10-25
- **Decisores:** equipo del proyecto (pendiente). La IA propone; el equipo decide (AGENTS.md §5)
- **Relacionado:** ADR 0008 (RAG y dos llamadas), ADR 0010 (respuesta verificada), B-019, plan de migración (MIG-05, MIG-06 y MIG-07)

## Contexto
El equipo entregó una base nueva (`RAG_2.xlsx`): 2.304 registros organizados en **192 cuadros** (motivos de consulta), cada uno con **12 registros, uno por etapa** de la conversación (indagar en tres niveles, orientar, remitir y acompañar). Trae columnas que la base v1 no tiene: `Motivo`, `Etapa`, `Ruta`, `Lectura clínica`, `Datos a extraer`, `Señales de escalamiento`, `Ruta base del cuadro`, `Fuente`, `Validado por` y `Fecha validación` (análisis completo en el §2 del plan de migración).

El código solo admitía los enfoques `Indagar` y `Solucionar` y seis campos por registro, así que la base v2 no podía cargarse. Además, el Excel no trae identificadores y el flujo de la base v1 (`scripts/export_pilot_kb.py`) lee la SQLite del piloto, no un Excel.

## Decisión
1. **Modelo** (`domain/knowledge.py`):
   - `Focus` admite `Indagar`, `Orientar`, `Remitir` y `Acompañar`. `Solucionar` se conserva solo para la base v1 y se retira al cargar la v2 (MIG-07).
   - Nuevas enumeraciones `Stage` (12 etapas) y `Route` (5 rutas), y tablas fijas `STAGE_FOCUS` y `STAGE_ROUTE`: cada etapa tiene un único enfoque y una única ruta.
   - `KnowledgeEntry` agrega `motive`, `stage`, `route` y los campos de validación `source`, `validated_by` y `validated_at` (B-019). Al crearse verifica que sea un registro v1 (sin etapa) o un registro v2 coherente con su etapa; si no, lanza `KnowledgeConsistencyError`.
   - Los datos comunes del cuadro van en una entidad aparte, `CaseProfile`. Así la **lectura clínica**, que es lenguaje diagnóstico, nunca forma parte de la evidencia que ve el agente ni de lo que se muestra a la persona.
2. **Archivos:** `knowledge/kb/entries.jsonl` (un registro por línea; los campos v2 solo aparecen en registros con etapa) y `knowledge/kb/cuadros.jsonl` (un cuadro por línea).
3. **Identificador estable:** `dominio:motivo:etapa` (p. ej., `materno_infantil:colico_lactante:T1_discriminantes`). Es único y legible, y no cambia si se corrige el texto.
4. **Compatibilidad del índice:** como el id no cambia al editar un texto, comparar los ids ya no basta. Al arrancar se compara también el hash del archivo con `entries_sha256` del manifiesto del índice (`hybrid_retriever.check_entries_file`).
5. **Conversor** `scripts/convert_rag_xlsx.py` (con `scripts/xlsx_reader.py`), **solo con la biblioteca estándar**: lee las dos hojas, valida columnas, celdas obligatorias, coherencia enfoque/etapa/ruta, 12 etapas por cuadro y datos del cuadro iguales en sus filas, y escribe los dos archivos. Si hay un error, no escribe nada. Advierte si faltan los datos de validación.
6. El Excel sigue siendo la **hoja maestra del equipo** y no se versiona; se versionan los JSONL que genera el conversor.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| `openpyxl` para leer el Excel | Lector completo y probado | Dependencia nueva (aunque sea solo de desarrollo); el formato que se necesita es simple |
| Guardar los datos del cuadro repetidos en cada registro | Un solo archivo | 12 copias por cuadro; la lectura clínica quedaría junto a la evidencia y podría llegar al agente |
| Id por hash del texto (como el piloto) | No hay que definir un formato | Cambia cada vez que se corrige el texto y pierde la trazabilidad con la traza de las respuestas |
| Reemplazar ya la base v1 | Un solo formato | Exige reconstruir el índice y recalibrar en el PC de pruebas, y la base v2 aún no está validada (P1) |

## Consecuencias
- ✅ La base v2 se puede convertir y cargar sin dependencias nuevas, y la base v1 sigue funcionando sin cambios.
- ✅ Los errores de la hoja se detectan antes de escribir, con su hoja y su fila.
- ✅ Editar un texto de la base obliga a reconstruir el índice (antes pasaba inadvertido si los ids no cambiaban).
- ⚠️ Mientras convivan, el código acepta las dos versiones de la base. MIG-07 debe retirar `Solucionar` y la rama v1.
- ⚠️ Cargar la base v2 no cambia todavía cómo se busca: aprovechar las etapas (estado del caso y recuperación por etapa) es la fase 3 del plan.
- ⏳ Pendiente: aprobación de este ADR, decisión sobre la validación de la base (P1) y sobre reemplazar la base v1 (P7), y luego MIG-07 en el PC de pruebas.
