"""Pruebas del modelo de la base v2 y de sus archivos (MIG-05, ADR 0016)."""

import json
from pathlib import Path

import numpy as np
import pytest

from cardio_materno.adapters.outbound.rag.hybrid_retriever import check_entries_file
from cardio_materno.adapters.outbound.rag.knowledge_files import (
    KnowledgeBaseError,
    case_profile_to_dict,
    entry_to_dict,
    file_digest,
    load_case_profiles,
    load_entries,
    parse_entry,
    write_jsonl,
)
from cardio_materno.adapters.outbound.rag.vector_index import IndexManifest, VectorIndex
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import (
    STAGE_FOCUS,
    STAGE_ROUTE,
    CaseProfile,
    Focus,
    KnowledgeConsistencyError,
    KnowledgeEntry,
    Route,
    Stage,
    missing_stages,
)

MOTIVE = "colico_lactante"


def v2_entry(
    stage: Stage, motive: str = MOTIVE, changes: dict[str, object] | None = None
) -> KnowledgeEntry:
    values: dict[str, object] = {
        "id": f"materno_infantil:{motive}:{stage}",
        "domain": Domain.MATERNAL_CHILD,
        "category": "Infantil — digestivo",
        "focus": STAGE_FOCUS[stage],
        "question": "mi bb llora todas las tardes",
        "answer": "¿Está llorando en este momento?",
        "motive": motive,
        "stage": stage,
        "route": STAGE_ROUTE[stage],
    }
    return KnowledgeEntry(**(values | (changes or {})))  # type: ignore[arg-type]


def profile(base_route: Route = Route.SELF_CARE) -> CaseProfile:
    return CaseProfile(
        MOTIVE,
        Domain.MATERNAL_CHILD,
        "Infantil — digestivo",
        "Sugiere cólico del lactante.",
        ("edad en meses", "horario del llanto"),
        ("Vómito verde",),
        base_route,
    )


# --- Modelo (domain) ---------------------------------------------------------------------------


def test_every_stage_has_one_focus_and_one_route() -> None:
    assert set(STAGE_FOCUS) == set(Stage) == set(STAGE_ROUTE)
    assert Focus.SOLVE not in STAGE_FOCUS.values()


@pytest.mark.parametrize("stage", list(Stage))
def test_consistent_v2_entry_is_accepted(stage: Stage) -> None:
    assert v2_entry(stage).stage is stage


@pytest.mark.parametrize(
    "changes",
    [
        {"focus": Focus.GUIDE},  # T1 es Indagar.
        {"route": Route.EMERGENCY},  # T1 es indagación.
        {"motive": " "},
    ],
)
def test_inconsistent_v2_entry_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(KnowledgeConsistencyError):
        v2_entry(Stage.DISCRIMINATORS, changes=changes)


def test_v1_entry_cannot_mix_v2_fields() -> None:
    base = {"domain": Domain.CARDIOVASCULAR, "category": "C", "question": "q", "answer": "a"}

    assert KnowledgeEntry("v1", focus=Focus.SOLVE, **base).stage is None  # type: ignore[arg-type]
    with pytest.raises(KnowledgeConsistencyError, match="etapa"):
        KnowledgeEntry("x", focus=Focus.GUIDE, **base)  # type: ignore[arg-type]
    with pytest.raises(KnowledgeConsistencyError, match="etapa"):
        KnowledgeEntry("y", focus=Focus.SOLVE, route=Route.SELF_CARE, **base)  # type: ignore[arg-type]


def test_case_base_route_must_be_self_care_priority_or_emergency() -> None:
    assert profile(Route.EMERGENCY).base_route is Route.EMERGENCY
    with pytest.raises(KnowledgeConsistencyError, match="ruta base"):
        profile(Route.INQUIRY)


def test_missing_stages_lists_only_incomplete_cases() -> None:
    complete = [v2_entry(stage, "completo") for stage in Stage]
    partial = [v2_entry(stage) for stage in Stage if stage is not Stage.EMOTIONAL_SUPPORT]

    assert missing_stages([*complete, *partial]) == {MOTIVE: (Stage.EMOTIONAL_SUPPORT,)}


# --- Archivos (adaptador) ----------------------------------------------------------------------


def test_v2_entry_round_trips_through_json(tmp_path: Path) -> None:
    entry = v2_entry(
        Stage.EMERGENCY_TRANSFER, changes={"source": "Guía MSPS", "validated_by": "Equipo"}
    )
    path = tmp_path / "entries.jsonl"

    write_jsonl([entry_to_dict(entry)], path)

    assert load_entries(path) == [entry]
    assert "validated_at" not in json.loads(path.read_text(encoding="utf-8"))
    assert b"\r\n" not in path.read_bytes()


def test_v1_entry_is_written_without_v2_fields() -> None:
    entry = KnowledgeEntry("v1", Domain.CARDIOVASCULAR, "C", Focus.SOLVE, "q", "a")

    assert set(entry_to_dict(entry)) == {"id", "domain", "category", "focus", "question", "answer"}


def test_inconsistent_v2_line_is_reported_with_its_line_number() -> None:
    data = entry_to_dict(v2_entry(Stage.DISCRIMINATORS)) | {"focus": "Remitir"}

    with pytest.raises(KnowledgeBaseError, match="línea 7"):
        parse_entry(json.dumps(data), 7)


def test_case_profiles_round_trip_and_missing_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "cuadros.jsonl"
    write_jsonl([case_profile_to_dict(profile())], path)

    assert load_case_profiles(path) == [profile()]
    with pytest.raises(KnowledgeBaseError, match="cuadros"):
        load_case_profiles(tmp_path / "no-existe.jsonl")


def test_index_built_from_another_version_of_the_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "entries.jsonl"
    path.write_text("contenido original\n", encoding="utf-8")
    manifest = IndexManifest("modelo", 1, file_digest(path), "2026-10-22", 1)
    index = VectorIndex(["a"], np.ones((1, 1), dtype=np.float32), manifest)

    check_entries_file(index, path)
    path.write_text("contenido editado\n", encoding="utf-8")

    with pytest.raises(KnowledgeBaseError, match="cambió"):
        check_entries_file(index, path)
