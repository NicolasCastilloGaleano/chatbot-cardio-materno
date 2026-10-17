"""Vigila que los archivos de texto del proyecto no tengan tildes dañadas por doble codificación.

El texto UTF-8 leído como cp1252/latin-1 y guardado de nuevo convierte cada vocal con tilde
en dos caracteres ("A" con tilde seguida de un símbolo). Pasó con archivos generados por otra
herramienta de IA (2026-10-17) y llegó hasta textos visibles para el usuario.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKED_DIRS = ("src", "tests", "scripts", "docs", "knowledge")
CHECKED_SUFFIXES = {".py", ".md", ".json", ".js", ".html", ".css", ".bpmn", ".txt"}
# "Ã" o "Â" seguidos de un carácter de continuación UTF-8 mal decodificado (U+0080–U+00BF).
DOUBLE_ENCODED = re.compile("[ÃÂ][\u0080-¿]")


def project_text_files() -> list[Path]:
    """Archivos de texto versionables del proyecto (sin entornos ni cachés)."""
    files: list[Path] = []
    for folder in CHECKED_DIRS:
        files.extend(
            path
            for path in (PROJECT_ROOT / folder).rglob("*")
            if path.suffix in CHECKED_SUFFIXES and "__pycache__" not in path.parts
        )
    return files


def test_no_double_encoded_text_in_project_files() -> None:
    damaged = [
        f"{path.relative_to(PROJECT_ROOT)}:{number}"
        for path in project_text_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if DOUBLE_ENCODED.search(line)
    ]

    assert damaged == []
