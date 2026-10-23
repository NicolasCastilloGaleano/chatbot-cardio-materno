"""Archivos de la base: registros (`entries.jsonl`), cuadros (`cuadros.jsonl`) y política.

Los registros de la base v1 tienen `{id, domain, category, focus, question, answer}`. Los de
la base v2 (ADR 0016) agregan `motive`, `stage`, `route` y los campos de validación
(`source`, `validated_by`, `validated_at`). Los cuadros de la base v2 van en otro archivo para
que su lectura clínica nunca llegue a la evidencia que ve el agente.
"""

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import fields
from pathlib import Path
from typing import Any

from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import CaseProfile, Focus, KnowledgeEntry, Route, Stage

# Campos de validación clínica por registro (B-019): en el JSON se omiten si están vacíos.
VALIDATION_FIELDS = ("source", "validated_by", "validated_at")


class KnowledgeBaseError(ValueError):
    """La base de conocimiento, su índice o su política no existen o son inválidos."""


def load_entries(path: Path) -> list[KnowledgeEntry]:
    """Lee `entries.jsonl` (un registro JSON por línea).

    Raises:
        KnowledgeBaseError: Si el archivo no existe o una línea es inválida.
    """
    return _load_lines(path, parse_entry, "la base de conocimiento")


def load_case_profiles(path: Path) -> list[CaseProfile]:
    """Lee `cuadros.jsonl` (un cuadro de la base v2 por línea).

    Raises:
        KnowledgeBaseError: Si el archivo no existe o una línea es inválida.
    """
    return _load_lines(path, parse_case_profile, "el archivo de cuadros")


def _load_lines[T](path: Path, parse: Callable[[str, int], T], what: str) -> list[T]:
    """Lee un archivo JSONL y convierte cada línea no vacía con `parse`."""
    if not path.is_file():
        raise KnowledgeBaseError(f"No existe {what}: {path}")
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [parse(line, number) for number, line in enumerate(lines, start=1)]


def parse_entry(line: str, number: int) -> KnowledgeEntry:
    """Convierte una línea JSON en un KnowledgeEntry validado (base v1 o v2).

    Raises:
        KnowledgeBaseError: Si falta un campo, un valor no es válido o el registro no es
            coherente con su etapa.
    """
    try:
        data = json.loads(line)
        return KnowledgeEntry(
            id=str(data["id"]),
            domain=Domain(data["domain"]),
            category=str(data["category"]),
            focus=Focus(data["focus"]),
            question=str(data["question"]),
            answer=str(data["answer"]),
            motive=str(data.get("motive", "")),
            stage=_optional(Stage, data.get("stage")),
            route=_optional(Route, data.get("route")),
            source=str(data.get("source", "")),
            validated_by=str(data.get("validated_by", "")),
            validated_at=str(data.get("validated_at", "")),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        raise KnowledgeBaseError(f"Registro inválido en la línea {number}: {error}") from error


def parse_case_profile(line: str, number: int) -> CaseProfile:
    """Convierte una línea JSON en un CaseProfile validado.

    Raises:
        KnowledgeBaseError: Si falta un campo o un valor no es válido.
    """
    try:
        data = json.loads(line)
        return CaseProfile(
            motive=str(data["motive"]),
            domain=Domain(data["domain"]),
            category=str(data["category"]),
            clinical_reading=str(data["clinical_reading"]),
            data_to_collect=tuple(str(item) for item in data["data_to_collect"]),
            escalation_signs=tuple(str(item) for item in data["escalation_signs"]),
            base_route=Route(data["base_route"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise KnowledgeBaseError(f"Cuadro inválido en la línea {number}: {error}") from error


def _optional[E: (Stage, Route)](kind: type[E], value: object) -> E | None:
    """Valor de una enumeración opcional (None si no viene o viene vacío)."""
    return None if value in (None, "") else kind(str(value))


def entry_to_dict(entry: KnowledgeEntry) -> dict[str, str]:
    """Registro como diccionario JSON, en el mismo formato que lee `parse_entry`.

    Los campos de la base v2 solo aparecen si el registro tiene etapa, y los de validación
    solo si tienen valor.
    """
    data = {
        "id": entry.id,
        "domain": str(entry.domain),
        "category": entry.category,
        "focus": str(entry.focus),
        "question": entry.question,
        "answer": entry.answer,
    }
    if entry.stage is not None and entry.route is not None:
        data |= {"motive": entry.motive, "stage": str(entry.stage), "route": str(entry.route)}
    return data | {name: getattr(entry, name) for name in VALIDATION_FIELDS if getattr(entry, name)}


def case_profile_to_dict(profile: CaseProfile) -> dict[str, Any]:
    """Cuadro como diccionario JSON, en el mismo formato que lee `parse_case_profile`."""
    return {
        "motive": profile.motive,
        "domain": str(profile.domain),
        "category": profile.category,
        "clinical_reading": profile.clinical_reading,
        "data_to_collect": list(profile.data_to_collect),
        "escalation_signs": list(profile.escalation_signs),
        "base_route": str(profile.base_route),
    }


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    """Escribe un objeto JSON por línea, en UTF-8 y con saltos de línea LF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


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
