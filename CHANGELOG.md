# Changelog

Todos los cambios relevantes del proyecto se registran aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado: [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added
- HU-00: chat libre por consola con Ollama local (`python run_console.py`). Incluye historial en memoria, prompt de sistema v1, verificación del modelo al arrancar y mensajes de error claros en español.
- Puerto `LanguageModel`, caso de uso `ChatService`, adaptadores `OllamaLanguageModel` y `ConsoleChat`, y configuración desde `.env`.
- 29 pruebas unitarias (sin Ollama); `requirements-dev.txt` con pytest, ruff y mypy.
- ADR 0005 (Ollama local como LLM) y riesgo R-07 (prototipo sin reglas de alarma).
- Estructura inicial del repositorio con arquitectura hexagonal (carpetas vacías y un README por capa).
- `AGENTS.md` y `CLAUDE.md` con las reglas de trabajo, los estándares de código y el protocolo de cierre de tarea.
- Documentación base en `docs/`: charter, especificación, arquitectura, ADR 0001–0004, playbook y bitácora de IA, calidad, gobernanza y despliegue.
- Hook `Stop` de Claude Code (`.claude/hooks/check_docs.py`) y comando `/cerrar-tarea` para garantizar que la documentación se actualice.
- Plantilla de Pull Request con la checklist de la Definition of Done.
