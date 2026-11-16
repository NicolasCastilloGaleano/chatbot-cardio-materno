# knowledge

Base de conocimiento clínica para el RAG. **Solo contenido con fuente citada y validado por el equipo clínico.**

Cada documento lleva un encabezado con: fuente (OPS, MinSalud, etc.), fecha, tema (CV/MI), quién lo validó y en qué fecha. Sin datos personales.

## Contenido actual
| Archivo | Qué es | Estado |
|---|---|---|
| `kb/entries.jsonl` | Base de conocimiento del RAG (4.049 pares pregunta/respuesta; ver [kb/README.md](kb/README.md)) | Generada con IA (ChatGPT Work, con fuentes) y **validada para el prototipo** por el líder del proyecto (Miguel, 2026-10-10); validación clínica pendiente (B-019) |
| `evidence_policy.json` | Política de recuperación: umbral, top-k, instrucción de consulta (ADR 0008) | Portada del piloto |
| `care_access.json` | Catálogo de datos de acceso a la atención (ADR 0023): barreras, afiliación, cascada del colesterol, avisos y preguntas fijos | ⚠️ PROVISIONAL. Cada aviso y cada pregunta tiene su `status`; **todos están en `pendiente`** y no se muestran hasta que el equipo los apruebe |
| `public_info.json` | Indicaciones generales de emergencia que se muestran sin consentimiento (ADR 0023) | ⚠️ PROVISIONAL. Sin afirmaciones jurídicas ni nada que dependa de lo que cuente la persona |
| `kb/provenance.json` | Procedencia de cada registro de la base (ADR 0022) | Generado por `scripts/build_kb_provenance.py` |
| `alarm_rules.json` | Catálogo de reglas de alarma (ADR 0007): patrones, severidad, mensajes fijos y fuente | ⚠️ **Excepción documentada:** borrador PROVISIONAL generado con IA a partir de signos de alarma públicos (MinSalud, OPS, AIEPI), **no validado** por el equipo clínico. Solo para pruebas internas. Ver la [solicitud de validación](../docs/01-especificacion/solicitud-validacion-alarmas.md) |

Al modificar `alarm_rules.json`: actualizar `tests/conversational/alarm_phrases.json` (cada regla con ≥ 2 frases), subir `version`, registrar quién validó en `validated_by` y aplicar la matriz de impacto (`docs/README.md`).
