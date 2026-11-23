"""Lectura de `provenance.json`, la procedencia de los registros de la base."""

import json
from pathlib import Path
from typing import Any

from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError
from cardio_materno.domain.provenance import EntryProvenance, Provenance, SourceRef

PROVENANCE_FILE_NAME = "provenance.json"


def provenance_path(entries_file: Path) -> Path:
    """Ubicación del archivo de procedencia: junto a la base."""
    return entries_file.with_name(PROVENANCE_FILE_NAME)


def load_provenance(path: Path) -> Provenance:
    """Lee la procedencia; si el archivo no existe, ninguna respuesta afirma una fuente.

    Raises:
        KnowledgeBaseError: Si el archivo existe pero no tiene el formato esperado.
    """
    if not path.is_file():
        return Provenance()
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return _parse(data)
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise KnowledgeBaseError(f"Archivo de procedencia inválido ({path}): {error}") from error


def _parse(data: dict[str, Any]) -> Provenance:
    """Convierte el JSON en la procedencia de cada registro."""
    catalog = {
        source_id: SourceRef(source_id, s["entity"], s["title"], s["version"], s["url"])
        for source_id, s in data["sources"].items()
    }
    batches: dict[str, dict[str, str]] = data["batches"]
    records = {
        entry_id: _entry(record["batch"], batches, record["sources"], catalog)
        for entry_id, record in data["entries"].items()
    }
    return Provenance(records, _entry(data["default_batch"], batches, [], catalog))


def _entry(
    batch: str,
    batches: dict[str, dict[str, str]],
    source_ids: list[str],
    catalog: dict[str, SourceRef],
) -> EntryProvenance:
    """Procedencia de un registro a partir de su lote y sus fuentes."""
    info = batches[batch]
    sources = tuple(catalog[source_id] for source_id in source_ids)
    return EntryProvenance(batch, info["label"], info["review"], info["review_label"], sources)
