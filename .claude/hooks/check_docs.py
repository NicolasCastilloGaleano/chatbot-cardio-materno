"""Hook `Stop` de Claude Code: verifica que la documentación acompañe a los cambios.

Si hay cambios sin commit en carpetas de código (src/, tests/, knowledge/) y no se
actualizaron los documentos obligatorios, el hook bloquea el cierre de la tarea
(exit code 2) e indica a Claude qué debe actualizar según la matriz de impacto.

Ver AGENTS.md §6 y docs/README.md (Matriz de impacto documental).
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_PREFIXES = ("src/", "tests/", "knowledge/")
REQUIRED_DOCS = ("CHANGELOG.md", "docs/05-ia/bitacora-verificacion-ia.md")
EXIT_OK = 0
EXIT_BLOCK = 2
STATUS_PREFIX_LEN = 3  # Formato porcelain: "XY ruta"

# Recordatorios contextuales: prefijo de ruta cambiada -> documentos a revisar.
CONTEXT_HINTS = {
    "src/cardio_materno/domain/": "reglas clínicas → especificacion-ejecutable.md, flujos, riesgos-ia.md",
    "src/cardio_materno/application/": "casos de uso/estados → historias-usuario.md, flujos, BPMN, trazabilidad.md",
    "src/cardio_materno/adapters/": "componentes → 02-arquitectura/arquitectura.md (¿nuevo ADR?)",
    "knowledge/": "base de conocimiento → validar fuente y registrar la validación clínica",
}


def read_hook_input() -> dict:
    """Lee el JSON que Claude Code envía por stdin.

    Returns:
        Diccionario con la entrada del hook, o vacío si no hay entrada válida.
    """
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def list_changed_paths() -> set[str]:
    """Obtiene las rutas modificadas, nuevas o eliminadas respecto a HEAD.

    Returns:
        Conjunto de rutas relativas a la raíz del repositorio (con separador '/').
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = result.stdout.splitlines()
    return {line[STATUS_PREFIX_LEN:].strip().strip('"') for line in lines if line.strip()}


def has_code_changes(paths: set[str]) -> bool:
    """Indica si alguna ruta pertenece a una carpeta de código."""
    return any(path.startswith(CODE_PREFIXES) for path in paths)


def find_missing_docs(paths: set[str]) -> list[str]:
    """Devuelve los documentos obligatorios que no fueron modificados."""
    return [doc for doc in REQUIRED_DOCS if doc not in paths]


def build_hints(paths: set[str]) -> list[str]:
    """Genera recordatorios según las áreas del código que cambiaron."""
    return [
        hint
        for prefix, hint in CONTEXT_HINTS.items()
        if any(path.startswith(prefix) for path in paths)
    ]


def build_block_message(missing: list[str], hints: list[str]) -> str:
    """Construye el mensaje que se muestra a Claude cuando se bloquea el cierre."""
    lines = ["Protocolo de cierre incompleto (AGENTS.md §6). Faltan por actualizar:"]
    lines += [f"  - {doc}" for doc in missing]
    if hints:
        lines.append("Revisa además, según la matriz de impacto (docs/README.md):")
        lines += [f"  - {hint}" for hint in hints]
    lines.append("Actualiza los documentos (o usa /cerrar-tarea) antes de terminar.")
    return "\n".join(lines)


def main() -> int:
    """Punto de entrada del hook.

    Returns:
        0 si se permite terminar; 2 si se bloquea por documentación faltante.
    """
    hook_input = read_hook_input()
    if hook_input.get("stop_hook_active"):
        return EXIT_OK  # Evita bucles: ya se bloqueó una vez en este ciclo.
    paths = list_changed_paths()
    if not has_code_changes(paths):
        return EXIT_OK
    missing = find_missing_docs(paths)
    if not missing:
        return EXIT_OK
    sys.stderr.reconfigure(encoding="utf-8")  # Windows usa cp1252 por defecto.
    print(build_block_message(missing, build_hints(paths)), file=sys.stderr)
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
