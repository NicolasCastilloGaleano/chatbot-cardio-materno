# Especificación ejecutable v0 (borrador)

*Última actualización: 2026-10-10*

> **Fuente de verdad del proyecto** (enfoque spec‑driven). El código y las pruebas se derivan de aquí. Los criterios de aceptación se escriben en Gherkin para poder convertirlos en pruebas automatizadas.

## 1. Problema
Ver [Project Charter](../00-gestion/project-charter.md#problema).

## 2. Stakeholders
| Stakeholder | Interés |
|---|---|
| Gestantes, madres y cuidadores de menores de 5 años | Orientación confiable y oportuna, en su propio lenguaje |
| Personas con riesgo cardiovascular (HTA, diabetes, etc.) | Reconocer signos de alarma y saber a dónde acudir |
| Líderes comunitarios y mediadores interculturales | Herramienta de apoyo para su comunidad |
| Dirección Territorial de Salud de Caldas | Insumos para la política pública y métricas |
| Equipo clínico investigador | Que el contenido sea correcto y seguro |

## 3. Alcance
Ver [Project Charter § Alcance](../00-gestion/project-charter.md#alcance).

## 4. Reglas de negocio y clínicas
> ⚠️ Las reglas clínicas las define y valida el **equipo clínico**. La IA no las propone como definitivas.

| ID | Regla | Fuente | Validada por |
|---|---|---|---|
| RN-01 | Toda conversación inicia con el aviso de teleorientación y la solicitud de consentimiento de tratamiento de datos | Res. 2654/2019, Ley 1581/2012 | TODO |
| RN-02 | Si se detecta un signo de alarma, se muestra un **mensaje fijo** (no generado por el LLM). En una urgencia inmediata, solo ese mensaje; en una consulta prioritaria, el mensaje fijo antes de la orientación. Doble filtro: texto del usuario + `reported_symptoms` del agente (ADR 0007) | ADR 0004, ADR 0007 | Equipo de desarrollo (comportamiento); TODO: equipo clínico (contenido) |
| RN-04 | Toda afirmación de salud de la respuesta proviene de la base de conocimiento y cita su evidencia; sin evidencia, el asistente lo dice y remite al personal de salud | ADR 0008 | Decisión del equipo (2026-10-10) |
| RN-05 | El asistente solo atiende salud cardiovascular y materno-infantil. Se descarta un mensaje solo si **todo** es ajeno (los temas mencionados como contexto no lo descartan); ante la duda, se atiende; las alarmas tienen prioridad; los mensajes descartados no se registran | ADR 0009 | Nicolas Castillo Galeano (2026-10-10) |
| RN-03 | El asistente nunca emite diagnósticos ni recomienda medicamentos o dosis | Res. 2654/2019 | TODO |
| RN-MI-xx / RN-CV-xx | Signos de alarma: ver el catálogo `knowledge/alarm_rules.json` y la tabla 4.1 | Borrador basado en MinSalud, OPS y AIEPI | ❌ **PROVISIONAL**: [solicitud de validación](solicitud-validacion-alarmas.md) |
| RN-RUTA-xx | Ruta de atención según el municipio, el tipo de alarma y el régimen de salud | TODO: DTS Caldas | TODO |

### 4.1 Catálogo de signos de alarma (v0.4.0, PROVISIONAL)
Fuente de verdad: `knowledge/alarm_rules.json` (patrones, mensajes fijos y fuentes). Cada regla se activa con sus patrones **o** con su propio nombre (columna "Signo"), que el agente usa en `reported_symptoms` (ADR 0007, puente hacia B-015; la propuesta de códigos cerrados está en el ADR 0012). Frases de referencia: `tests/conversational/alarm_phrases.json`. La v0.4.0 (2026-10-12) solo amplía patrones de RN-MI-02/03/10/12/13/14 y RN-CV-03/06; no cambia signos, severidades ni mensajes.

| ID | Signo (población) | Severidad | Validación |
|---|---|---|---|
| RN-MI-01 | Sangrado vaginal en el embarazo o el posparto (gestante/posparto) | urgencia_inmediata | PROVISIONAL |
| RN-MI-02 | Dolor de cabeza intenso o alteraciones visuales en el embarazo (gestante/posparto) | urgencia_inmediata | PROVISIONAL |
| RN-MI-03 | Convulsiones (gestante/posparto/niños) | urgencia_inmediata | PROVISIONAL |
| RN-MI-04 | Hinchazón de cara, manos o pies de aparición reciente en el embarazo (gestante/posparto) | urgencia_inmediata | PROVISIONAL |
| RN-MI-05 | Salida de líquido por la vagina (ruptura de membranas) (gestante) | urgencia_inmediata | PROVISIONAL |
| RN-MI-06 | Disminución o ausencia de movimientos fetales (gestante) | urgencia_inmediata | PROVISIONAL |
| RN-MI-07 | Fiebre en el embarazo o el posparto (gestante/posparto) | urgencia_inmediata | PROVISIONAL |
| RN-MI-08 | Contracciones o dolor tipo parto antes de las 37 semanas (gestante) | urgencia_inmediata | PROVISIONAL |
| RN-MI-09 | No puede comer, beber o tomar el pecho (recién nacido/menor de 5 años) | urgencia_inmediata | PROVISIONAL |
| RN-MI-10 | Vomita todo lo que come o bebe (menor de 5 años) | urgencia_inmediata | PROVISIONAL |
| RN-MI-11 | Letárgico, muy decaído o no despierta (recién nacido/menor de 5 años) | urgencia_inmediata | PROVISIONAL |
| RN-MI-12 | Respira rápido o con dificultad (recién nacido/menor de 5 años) | urgencia_inmediata | PROVISIONAL |
| RN-MI-13 | Fiebre o temperatura baja en el recién nacido (recién nacido) | urgencia_inmediata | PROVISIONAL |
| RN-MI-14 | Piel o labios muy amarillos o morados (recién nacido/menor de 5 años) | urgencia_inmediata | PROVISIONAL |
| RN-CV-01 | Dolor u opresión en el pecho (adulto) | urgencia_inmediata | PROVISIONAL |
| RN-CV-02 | Dificultad para respirar (adulto) | urgencia_inmediata | PROVISIONAL |
| RN-CV-03 | Signos de accidente cerebrovascular (cara caída, debilidad de un lado, habla alterada, cefalea súbita) (adulto) | urgencia_inmediata | PROVISIONAL |
| RN-CV-04 | Desmayo o pérdida del conocimiento (adulto) | urgencia_inmediata | PROVISIONAL |
| RN-CV-05 | Presión arterial muy alta (≥ 180) o presión alta con síntomas (adulto) | urgencia_inmediata | PROVISIONAL |
| RN-CV-06 | Presión arterial alta sin síntomas de alarma (adulto) | consulta_prioritaria | PROVISIONAL |

## 5. Criterios de aceptación (ejemplo de formato)
```gherkin
Escenario: Gestante reporta un signo de alarma
  Dado que la usuaria aceptó el consentimiento y eligió el tema "embarazo"
  Cuando escribe "tengo un dolor de cabeza muy fuerte y veo lucecitas"
  Entonces el sistema clasifica la situación como ALARMA
  Y responde primero con la indicación de acudir a urgencias
  Y registra una alerta anonimizada
```

## 6. Requisitos no funcionales
Ver [requisitos-no-funcionales.md](requisitos-no-funcionales.md).

## 7. Preguntas abiertas
- TODO: listado definitivo de signos de alarma por población (equipo clínico).
- TODO: rutas de atención por municipio (DTS Caldas).
- TODO: proveedor de LLM y restricciones de datos (ADR pendiente).
- TODO: ¿se requiere seguimiento proactivo (recordatorios de controles prenatales)?
