# Especificación ejecutable v0 (borrador)

*Última actualización: 2026-10-09*

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
| RN-02 | Si se detecta un signo de alarma, se muestra de inmediato la indicación de acudir a urgencias o la línea correspondiente, antes de cualquier otra respuesta | TODO | TODO |
| RN-03 | El asistente nunca emite diagnósticos ni recomienda medicamentos o dosis | Res. 2654/2019 | TODO |
| RN-MI-xx | Signos de alarma materno‑infantiles (p. ej., en el embarazo: cefalea intensa, visión borrosa, sangrado, convulsiones; en el recién nacido: TODO) | TODO: guía MinSalud/OPS | TODO |
| RN-CV-xx | Signos de alarma cardiovasculares (p. ej., dolor torácico, signos de ACV) y orientación según HEARTS OPS | TODO: OPS HEARTS | TODO |
| RN-RUTA-xx | Ruta de atención según el municipio, el tipo de alarma y el régimen de salud | TODO: DTS Caldas | TODO |

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
