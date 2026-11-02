# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

> **2026-11-02:** por decisión del equipo, ADR 0019 y 0021 aceptados y `EVIDENCE_SELECTION_MODE=activo` por defecto.

### Added
- **Responder e indagar (HU-13, ADR 0019, paso 1.3):** con `INQUIRY_MODE` y `EVIDENCE_SELECTION_MODE` en `activo`, si la evidencia sirve pero no alcanza, la persona recibe la respuesta verificada y una sola pregunta (`TurnMode.ANSWER_AND_INQUIRE`, `INQUIRY_MAX_QUESTIONS_WITH_ANSWER`). Cuenta como turno de indagación. Sin pregunta verificada, queda solo la respuesta. Guion `docs/08-despliegue/prueba-responder-e-indagar.md`.
