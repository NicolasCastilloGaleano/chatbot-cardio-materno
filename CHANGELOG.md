# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

> **2026-11-02:** por decisión del equipo, ADR 0019 y 0021 aceptados y `EVIDENCE_SELECTION_MODE=activo` por defecto.

### Added
- **Informe de vacíos para el equipo clínico (HU-15, B-032):** `scripts/report_gaps.py` lista los turnos de salud sin orientación (abstención o cierre de la indagación), agrupados por categoría, con la consulta de búsqueda, la mejor similitud y los registros que el selector descartó. Sin datos personales; lee la base en solo lectura.
- **Selector con temperatura 0 (ADR 0019):** el selector de evidencia usa temperatura 0 por defecto (`OLLAMA_SELECTION_TEMPERATURE`), aunque use el modelo del análisis. Con 0,3, el caso del sangrado en urgencia pasó 3 de 5 veces; con 0, 5 de 5.
- **Corrección, pregunta repetida (HU-13, paso 1.3):** el turno de indagación descarta las preguntas que repiten las de la última respuesta del hilo; si todas las repiten, vuelve a hacer solo la primera, porque la pregunta fija pedía lo que la persona ya había contado.
- **Corrección, abstención ante una pregunta de información:** ya no pide síntomas (`NO_INFORMATION_TEXT`); los demás casos siguen pidiendo detalles.
- **Responder e indagar (HU-13, ADR 0019, paso 1.3):** con `INQUIRY_MODE` y `EVIDENCE_SELECTION_MODE` en `activo`, si la evidencia sirve pero no alcanza, la persona recibe la respuesta verificada y una sola pregunta (`TurnMode.ANSWER_AND_INQUIRE`, `INQUIRY_MAX_QUESTIONS_WITH_ANSWER`). Cuenta como turno de indagación. Sin pregunta verificada, queda solo la respuesta. Guion `docs/08-despliegue/prueba-responder-e-indagar.md`.
