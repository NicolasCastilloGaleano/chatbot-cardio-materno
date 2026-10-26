"""Lectura de la base (`entries.jsonl`) y de la política de evidencia (`evidence_policy.json`)."""

import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import Focus, KnowledgeEntry


class KnowledgeBaseError(ValueError):
    """La base de conocimiento, su índice o su política no existen o son inválidos."""


def load_entries(path: Path) -> list[KnowledgeEntry]:
    """Lee `entries.jsonl` (un registro JSON por línea).

    Raises:
        KnowledgeBaseError: Si el archivo no existe o una línea es inválida.
    """
    if not path.is_file():
        raise KnowledgeBaseError(f"No existe la base de conocimiento: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [parse_entry(line, number) for number, line in enumerate(lines, start=1)]


def parse_entry(line: str, number: int) -> KnowledgeEntry:
    """Convierte una línea JSON en un KnowledgeEntry validado."""
    try:
        data = json.loads(line)
        return KnowledgeEntry(
            id=str(data["id"]),
            domain=Domain(data["domain"]),
            category=str(data["category"]),
            focus=Focus(data["focus"]),
            question=str(data["question"]),
            answer=str(data["answer"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        raise KnowledgeBaseError(f"Registro inválido en la línea {number}: {error}") from error


def file_digest(path: Path) -> str:
    """SHA-256 del archivo (detecta si la base cambió después de construir el índice)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_policy(path: Path) -> EvidencePolicy:
    """Lee la política de evidencia; las claves desconocidas se ignoran.

    Raises:
        KnowledgeBaseError: Si el archivo no existe o no es JSON válido.
    """
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise KnowledgeBaseError(f"No existe la política de evidencia: {path}") from error
    except json.JSONDecodeError as error:
        raise KnowledgeBaseError(f"La política de evidencia no es JSON válido: {error}") from error
    known = {field.name for field in fields(EvidencePolicy)}
    return EvidencePolicy(**{key: value for key, value in data.items() if key in known})
