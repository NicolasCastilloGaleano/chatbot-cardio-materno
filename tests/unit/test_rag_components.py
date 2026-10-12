"""Pruebas de los componentes del RAG sin Ollama: BM25, índice, buscador, constructor y archivos."""

import io
import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.request import Request

import numpy as np
import pytest
from scripts.export_pilot_kb import main as export_main

from cardio_materno.adapters.outbound.llm.ollama_http import OllamaTimeoutError
from cardio_materno.adapters.outbound.rag.bm25 import Bm25Index, tokenize
from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever, fuse_rankings
from cardio_materno.adapters.outbound.rag.kb_index_builder import build_index
from cardio_materno.adapters.outbound.rag.knowledge_files import (
    KnowledgeBaseError,
    load_entries,
    load_policy,
)
from cardio_materno.adapters.outbound.rag.ollama_embedder import (
    EmbedderSettings,
    OllamaEmbedder,
    build_embed_payload,
)
from cardio_materno.adapters.outbound.rag.vector_index import (
    IndexManifest,
    VectorIndex,
    load_index,
    save_index,
)
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import EvidencePolicy, build_evidence_query
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import Focus, KnowledgeEntry, RetrievalStatus

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL = "emb-test"


def entry(entry_id: str, domain: Domain, question: str, answer: str) -> KnowledgeEntry:
    return KnowledgeEntry(entry_id, domain, "Cat", Focus.SOLVE, question, answer)


ENTRIES = [
    entry("a", Domain.MATERNAL_CHILD, "acidez en el embarazo", "comer porciones pequeñas"),
    entry("b", Domain.MATERNAL_CHILD, "lactancia materna", "ofrecer el pecho a libre demanda"),
    entry(
        "c", Domain.CARDIOVASCULAR, "presión arterial alta", "controles y registro de mediciones"
    ),
]
# Vectores de 3 dimensiones: cada registro apunta a un eje.
VECTORS = {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, 1.0]}


class KeywordEmbedder:
    """Embedder falso: proyecta el texto sobre los ejes según palabras clave."""

    model = MODEL

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.texts: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.fail:
            raise LanguageModelError("caído")
        self.texts.extend(texts)
        return [self._vector(text.lower()) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        return [
            1.0 if "acidez" in text else 0.1,
            1.0 if "lactancia" in text or "pecho" in text else 0.1,
            1.0 if "presion" in text or "presión" in text else 0.1,
        ]


def make_index(ids: Sequence[str] = ("a", "b", "c"), model: str = MODEL) -> VectorIndex:
    matrix = np.asarray([VECTORS[i] for i in ids], dtype=np.float32)
    return VectorIndex(ids, matrix, IndexManifest(model, 3, "hash", "2026-10-10", len(ids)))


def make_retriever(policy: EvidencePolicy | None = None, embedder: Any = None) -> HybridRetriever:
    policy = policy or EvidencePolicy(top_k=2, min_similarity=0.5, query_instruction="Q: ")
    return HybridRetriever(ENTRIES, make_index(), embedder or KeywordEmbedder(), policy)


# --- BM25 y fusión ------------------------------------------------------------------------------


def test_tokenize_normalizes_and_drops_stopwords_short_words_and_numbers() -> None:
    assert tokenize("Tengo ACIDEZ en el embarazo de 7 meses", 3) == ["acidez", "embarazo", "meses"]


def test_bm25_ranks_matching_documents_first_and_ignores_non_matching() -> None:
    index = Bm25Index(
        {i: tokenize(f"{e.question} {e.answer}", 3) for i, e in zip("abc", ENTRIES, strict=True)}
    )

    assert index.rank(["acidez"], 10) == ["a"]
    assert index.rank(["nada"], 10) == []


def test_reciprocal_rank_fusion_rewards_documents_in_both_rankings() -> None:
    assert fuse_rankings([["x", "y"], ["y", "z"]], rrf_k=60)[0] == "y"


# --- Índice vectorial ---------------------------------------------------------------------------


def test_vector_index_returns_cosine_similarity_within_allowed_ids() -> None:
    index = make_index()

    result = index.search([2.0, 0.0, 0.0], {"a", "b"}, limit=5)

    assert list(result) == ["a", "b"]
    assert result["a"] == pytest.approx(1.0)
    assert result["b"] == pytest.approx(0.0)


def test_index_save_and_load_round_trip(tmp_path: Path) -> None:
    manifest = IndexManifest(MODEL, 3, "hash", "2026-10-10", 3)
    save_index(tmp_path, ["a", "b", "c"], np.eye(3, dtype=np.float32), manifest)

    index = load_index(tmp_path)

    assert index.ids == ("a", "b", "c") and index.manifest == manifest


def test_missing_index_raises_knowledge_base_error(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeBaseError, match="Índice"):
        load_index(tmp_path / "no-existe")


# --- Buscador híbrido ---------------------------------------------------------------------------


def test_retriever_returns_labeled_evidence_above_threshold() -> None:
    embedder = KeywordEmbedder()

    result = make_retriever(embedder=embedder).retrieve(EvidenceQuery("tengo acidez"))

    assert result.status is RetrievalStatus.SUFFICIENT
    assert [(item.label, item.entry.id) for item in result.items] == [("E1", "a")]
    assert embedder.texts == ["Q: tengo acidez"]


def test_retriever_filters_by_domain() -> None:
    result = make_retriever().retrieve(EvidenceQuery("acidez", (Domain.CARDIOVASCULAR,)))

    assert all(item.entry.domain is Domain.CARDIOVASCULAR for item in result.items)


def test_lexical_only_match_never_qualifies_as_evidence() -> None:
    policy = EvidencePolicy(min_similarity=0.99)

    result = make_retriever(policy).retrieve(EvidenceQuery("presion acidez lactancia"))

    assert result.status is RetrievalStatus.INSUFFICIENT
    assert result.items == ()
    assert 0 < result.best_score < 0.99


def test_lexical_only_match_never_qualifies_even_with_zero_threshold() -> None:
    """Regresión 2026-10-10: con umbral 0 (sonda) un hallazgo solo por BM25 causaba KeyError."""
    index = make_index(ids=("a", "b", "c"))
    retriever = HybridRetriever(
        ENTRIES, index, KeywordEmbedder(), EvidencePolicy(min_similarity=0.0, candidate_k=1)
    )

    result = retriever.retrieve(EvidenceQuery("acidez lactancia presion"))

    assert len(result.items) == 1  # solo el candidato vectorial; los léxicos no califican


def test_retriever_reports_unavailable_when_embedder_fails() -> None:
    result = make_retriever(embedder=KeywordEmbedder(fail=True)).retrieve(EvidenceQuery("x"))

    assert result.status is RetrievalStatus.UNAVAILABLE


def test_index_built_with_other_model_or_other_entries_is_rejected() -> None:
    policy = EvidencePolicy()
    with pytest.raises(KnowledgeBaseError, match="otro|construyó"):
        HybridRetriever(ENTRIES, make_index(model="otro-modelo"), KeywordEmbedder(), policy)
    with pytest.raises(KnowledgeBaseError, match="cambió"):
        HybridRetriever(ENTRIES, make_index(ids=("a", "b")), KeywordEmbedder(), policy)


# --- Consulta de evidencia ----------------------------------------------------------------------


def test_build_evidence_query_without_search_query_skips_empty_parts() -> None:
    analysis = AnalysisTurn(ThreadAction.NEW, Domain.NONE, "", ("mareo",))

    query = build_evidence_query(analysis, "hola")

    assert query.text == "hola. mareo"
    assert query.domains == ()


def test_build_evidence_query_prefers_the_reformulated_search_query() -> None:
    analysis = AnalysisTurn(
        ThreadAction.NEW,
        Domain.CARDIOVASCULAR,
        "partido y presión alta",
        ("presión arterial alta",),
        search_query="cómo controlar la presión arterial alta",
    )

    query = build_evidence_query(analysis, "¿quién ganó el partido? ah, y tengo la presión alta")

    assert query.text == "cómo controlar la presión arterial alta"
    assert query.domains == (Domain.CARDIOVASCULAR,)


# --- Constructor del índice y embedder -----------------------------------------------------------


def test_build_index_embeds_entries_with_pilot_text_format(tmp_path: Path) -> None:
    entries_file = tmp_path / "entries.jsonl"
    entries_file.write_text("x", encoding="utf-8")
    embedder = KeywordEmbedder()
    progress: list[tuple[int, int]] = []

    manifest = build_index(
        ENTRIES, entries_file, embedder, tmp_path / "idx", lambda d, t: progress.append((d, t))
    )

    assert (
        embedder.texts[0] == "Pregunta: acidez en el embarazo \nRespuesta: comer porciones pequeñas"
    )
    assert (manifest.embed_model, manifest.count, manifest.dimensions) == (MODEL, 3, 3)
    assert progress[-1] == (3, 3)
    assert load_index(tmp_path / "idx").ids == ("a", "b", "c")


class EmbedOpener:
    """Simula `/api/embed`: falla por timeout con lotes de más de `max_batch` textos."""

    def __init__(self, max_batch: int) -> None:
        self.max_batch = max_batch
        self.batches: list[int] = []

    def __call__(self, request: Request, timeout: float) -> io.BytesIO:
        texts = json.loads(request.data)["input"]  # type: ignore[arg-type]
        self.batches.append(len(texts))
        if len(texts) > self.max_batch:
            raise TimeoutError()
        return io.BytesIO(json.dumps({"embeddings": [[1.0, 0.0]] * len(texts)}).encode())


def test_embedder_splits_batch_in_halves_on_timeout() -> None:
    opener = EmbedOpener(max_batch=1)
    embedder = OllamaEmbedder(EmbedderSettings("http://x", MODEL, 1, batch_size=4), opener)

    vectors = embedder.embed(["a", "b", "c", "d"])

    assert len(vectors) == 4
    assert opener.batches == [4, 2, 1, 1, 2, 1, 1]


def test_embedder_raises_timeout_for_single_text() -> None:
    embedder = OllamaEmbedder(EmbedderSettings("http://x", MODEL, 1, batch_size=1), EmbedOpener(0))

    with pytest.raises(OllamaTimeoutError):
        embedder.embed(["a"])


# --- Archivos de la base y exportación ---------------------------------------------------------


def test_real_knowledge_base_and_policy_load() -> None:
    entries = load_entries(PROJECT_ROOT / "knowledge" / "kb" / "entries.jsonl")
    policy = load_policy(PROJECT_ROOT / "knowledge" / "evidence_policy.json")

    assert len(entries) == 1600
    assert {e.domain for e in entries} == {Domain.MATERNAL_CHILD, Domain.CARDIOVASCULAR}
    assert {e.focus for e in entries} == {Focus.INQUIRE, Focus.SOLVE}
    assert len({e.id for e in entries}) == len(entries)
    assert policy.min_similarity == 0.55 and policy.top_k == 3


def test_invalid_entry_line_raises_error(tmp_path: Path) -> None:
    path = tmp_path / "entries.jsonl"
    path.write_text('{"id": "x", "domain": "otro"}\n', encoding="utf-8")

    with pytest.raises(KnowledgeBaseError, match="línea 1"):
        load_entries(path)


def test_export_keeps_latest_version_per_question(tmp_path: Path) -> None:
    db = tmp_path / "kb.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE knowledge_entries (id_local, dominio, categoria, enfoque, pregunta,"
            " respuesta, fecha_sincronizacion)"
        )
        connection.executemany(
            "INSERT INTO knowledge_entries VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("v1", "cardiovascular", "C", "Indagar", "¿P?", "vieja", "2026-01-01"),
                ("v2", "cardiovascular", "C", "Indagar", "¿P?", "nueva", "2026-02-01"),
            ],
        )
    output = tmp_path / "entries.jsonl"

    assert export_main(["script", str(db), str(output)]) == 0

    exported = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert exported == [
        {
            "id": "v2",
            "domain": "cardiovascular",
            "category": "C",
            "focus": "Indagar",
            "question": "¿P?",
            "answer": "nueva",
        }
    ]


def test_embed_payload_includes_keep_alive_and_num_gpu_only_when_configured() -> None:
    default = build_embed_payload(EmbedderSettings("http://x", MODEL, 1, 1), ["a"])
    on_cpu = build_embed_payload(EmbedderSettings("http://x", MODEL, 1, 1, "1h", num_gpu=0), ["a"])

    assert default == {"model": MODEL, "input": ["a"], "keep_alive": "30m"}
    assert on_cpu["keep_alive"] == "1h" and on_cpu["options"] == {"num_gpu": 0}
