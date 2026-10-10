# Estándares de código

*Última actualización: 2026-10-09*

Resumen obligatorio en [AGENTS.md §3](../../AGENTS.md). Aquí está el detalle.

## Diseño
- **SRP:** cada función hace una sola cosa. Si su nombre necesita "y", hay que dividirla.
- **Tamaño:** ≤ 25 sentencias, ≤ 5 parámetros, complejidad ciclomática ≤ 7 y ≤ 6 ramas. Lo verifica ruff (`C90`, `PLR`).
- **Profundidad:** máximo 2 niveles de anidación; se prefieren *early returns*.
- **Puertos:** se definen con `typing.Protocol` en `application/ports/`.
- **Inmutabilidad:** las entidades de valor del dominio son `@dataclass(frozen=True)`.
- **Inyección de dependencias** por constructor; el armado se hace solo en `bootstrap/`.

## Documentación en el código
Docstrings estilo **Google** en español:
```python
def detect_alarm_signs(symptoms: list[Symptom]) -> list[AlarmSign]:
    """Detecta los signos de alarma presentes en una lista de síntomas.

    Args:
        symptoms: Síntomas estructurados extraídos del mensaje del usuario.

    Returns:
        Signos de alarma detectados, ordenados por severidad (vacío si no hay).
    """
```
- Los comentarios explican el **porqué**, no el qué.
- Toda regla clínica referencia su ID (`RN-MI-01`) y su fuente.

## Nombres
- Identificadores en inglés y `snake_case` (funciones y variables), `PascalCase` (clases), `UPPER_CASE` (constantes).
- Los textos al usuario, en español y en plantillas (nunca *hardcoded* en la lógica).

## Errores y logging
- Excepciones de dominio propias (`DomainError` y sus subclases). Nunca `except:` ni `except Exception: pass`.
- Logging estructurado (clave‑valor o JSON), **sin PII**.

## Herramientas
`ruff check`, `ruff format`, `mypy --strict` (sobre `src` y `tests`) y `pytest`. La configuración está en `pyproject.toml` y se ejecuta en la CI (`.github/workflows/ci.yml`).

## Constructores con muchas dependencias
Si un constructor supera los 5 parámetros, se agrupan los de configuración en una `@dataclass(frozen=True)` (p. ej., `ConversationConfig`). No se usa `# noqa: PLR0913`.
