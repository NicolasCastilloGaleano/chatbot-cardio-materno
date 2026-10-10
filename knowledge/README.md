# knowledge

Base de conocimiento clínica para el RAG. **Solo contenido con fuente citada y validado por el equipo clínico.**

Cada documento lleva un encabezado con: fuente (OPS, MinSalud, etc.), fecha, tema (CV/MI), quién lo validó y en qué fecha. Sin datos personales.

## Contenido actual
| Archivo | Qué es | Estado |
|---|---|---|
| `alarm_rules.json` | Catálogo de reglas de alarma (ADR 0007): patrones, severidad, mensajes fijos y fuente | ⚠️ **Excepción documentada:** borrador PROVISIONAL generado con IA a partir de signos de alarma públicos (MinSalud, OPS, AIEPI), **no validado** por el equipo clínico. Solo para pruebas internas. Ver la [solicitud de validación](../docs/01-especificacion/solicitud-validacion-alarmas.md) |

Al modificar `alarm_rules.json`: actualizar `tests/conversational/alarm_phrases.json` (cada regla con ≥ 2 frases), subir `version`, registrar quién validó en `validated_by` y aplicar la matriz de impacto (`docs/README.md`).
