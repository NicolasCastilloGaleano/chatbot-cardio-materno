"""Sonda de cobertura de las categorías nuevas de la base (B-035, B-036).

Requiere Ollama con el modelo de embeddings y el índice construido (`run_build_kb_index.py`).
Ejecutar: `pytest -m live -s` (con -s se ve el reporte por categoría).
"""

import json
import os
from collections import defaultdict
from dataclasses import replace
from typing import Any

import pytest

from cardio_materno.adapters.outbound.rag.knowledge_files import load_entries
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.bootstrap.main import PROJECT_ROOT
from cardio_materno.bootstrap.settings import load_rag_settings
from cardio_materno.domain.conversation import Domain
from tests.live.conftest import LIVE_DIR, make_retriever

pytestmark = pytest.mark.live

CASES: list[dict[str, Any]] = json.loads(
    (LIVE_DIR / "coverage_probe.json").read_text(encoding="utf-8")
)["cases"]
TOP_K = 3
MIN_HIT_SHARE = 0.8  # meta: 80 % de los casos con su categoría en el top-3


def category_code(category: str) -> str:
    """Código de una categoría nueva (`CV-N1 — …` → `CV-N1`)."""
    return category.split(" ", 1)[0]


def present_codes() -> set[str]:
    """Códigos de categoría que ya existen en la base cargada."""
    settings = load_rag_settings(os.environ, PROJECT_ROOT)
    return {category_code(entry.category) for entry in load_entries(settings.entries_file)}


def test_new_categories_are_retrieved_for_general_questions(
    evidence_policy: EvidencePolicy,
) -> None:
    retriever = make_retriever(replace(evidence_policy, min_similarity=0.0, top_k=TOP_K))
    codes = present_codes()
    results: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for case in (c for c in CASES if c["code"] in codes):
        found = retriever.retrieve(EvidenceQuery(case["query"], (Domain(case["domain"]),)))
        scores = [i.score for i in found.items if category_code(i.entry.category) == case["code"]]
        useful = any(score >= evidence_policy.min_similarity for score in scores)
        results[case["code"]].append((bool(scores), useful))
        print(f"{'✅' if scores else '❌'} {case['code']} {case['query']}")
    for code, outcome in sorted(results.items()):
        n_hits, n_useful = sum(h for h, _ in outcome), sum(u for _, u in outcome)
        print(
            f"{code}: top-3 {n_hits}/{len(outcome)} · útil con el umbral {n_useful}/{len(outcome)}"
        )
    missing = sorted({c["code"] for c in CASES} - codes)
    print(f"Categorías aún sin registros: {', '.join(missing) or 'ninguna'}")
    total = [hit for outcome in results.values() for hit, _ in outcome]
    assert total and sum(total) / len(total) >= MIN_HIT_SHARE
