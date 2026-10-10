"""Carga mínima de archivos `.env` con la librería estándar."""

import os
from pathlib import Path

COMMENT_PREFIX = "#"
SEPARATOR = "="
QUOTES = "\"'"


def load_env_file(path: Path) -> None:
    """Carga las variables de un archivo `.env` en `os.environ`.

    Las variables que ya existen en el entorno tienen prioridad y no se sobrescriben.
    Si el archivo no existe, no hace nada.

    Args:
        path: Ruta del archivo `.env`.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = parse_env_line(line)
        if entry is not None:
            os.environ.setdefault(*entry)


def parse_env_line(line: str) -> tuple[str, str] | None:
    """Convierte una línea `CLAVE=valor` en una tupla (clave, valor).

    Args:
        line: Línea del archivo.

    Returns:
        La tupla, o None si la línea está vacía, es un comentario o no tiene "=".
    """
    stripped = line.strip()
    if not stripped or stripped.startswith(COMMENT_PREFIX) or SEPARATOR not in stripped:
        return None
    key, value = stripped.split(SEPARATOR, 1)
    return key.strip(), value.strip().strip(QUOTES)
