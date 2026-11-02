"""Pruebas en vivo del selector de evidencia con evidencia fija (HU-13, paso 1.1).

La búsqueda cambia entre corridas: el 2026-11-01, en el caso del sangrado, una vez trajo un
registro de convulsión y otra no. Aquí los registros se fijan, para que el selector siempre
tenga delante lo que debe descartar. Ejecutar en el PC de pruebas:
`pytest -m live -s tests/live/test_live_selection.py`.
"""

import os
from dataclasses import dataclass

import pytest

from cardio_materno.adapters.outbound.llm.ollama_language_model import OllamaLanguageModel
from cardio_materno.adapters.outbound.rag.knowledge_files import load_entries
from cardio_materno.application.agent_turn import AnalysisTurn, ThreadAction
from cardio_materno.application.evidence import EvidencePolicy
from cardio_materno.application.evidence_selection import EvidenceSelector, shown_sentences
from cardio_materno.application.stage_timer import StageTimer
from cardio_materno.application.turn_context import TurnInput
from cardio_materno.bootstrap.main import PROJECT_ROOT, SELECTION_PROMPT_FILE
from cardio_materno.bootstrap.settings import (
    load_rag_settings,
    load_stage_settings,
    selection_model_variable,
)
from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import EvidenceItem, KnowledgeEntry
from cardio_materno.domain.trace import SelectionTrace, SelectionVerdict

pytestmark = pytest.mark.live

CONVULSION = "34ed7575f625"
BLEEDING = "0ff6daad7591"
REFLUX_WITH_COLD_SWEAT = "7135dd9ac2e6"
READING_190 = "8ebd98075dee"
DASH = "584a486ff23c"
SCORE = 0.6


@dataclass(frozen=True)
class SelectionCase:
    """Consulta con su evidencia fija y lo que no debe quedar elegido."""

    name: str
    message: str
    summary: str
    domain: Domain
    entries: tuple[str, ...]
    forbidden: tuple[str, ...]
    urgent: bool = False
    required: tuple[str, ...] = ()


CASES = [
    SelectionCase(
        "sangrado con un registro de convulsión",
        "¿qué hago mientras llego?",
        "Embarazada con sangrado vaginal. Pregunta qué hacer mientras llega a urgencias.",
        Domain.MATERNAL_CHILD,
        (CONVULSION, BLEEDING),
        ("protege la cabeza", "golpearla", "sujetes", "introduzcas"),
        urgent=True,
        required=("traslado",),
    ),
    SelectionCase(
        "ardor con un registro de sudor frío",
        "tengo ardor en el pecho después de comer",
        "La persona reporta ardor en el pecho después de comer.",
        Domain.CARDIOVASCULAR,
        (REFLUX_WITH_COLD_SWEAT,),
        ("sudor frío", "este cambio"),
    ),
    SelectionCase(
        "presión alta sin cifras con un registro de 190/125",
        "tengo la presión alta, ¿qué debo hacer?",
        "La persona tiene la presión alta y pregunta qué debe hacer.",
        Domain.CARDIOVASCULAR,
        (READING_190,),
        ("marcadamente elevada",),
    ),
]


@pytest.fixture(scope="module")
def selector(evidence_policy: EvidencePolicy) -> EvidenceSelector:
    """Selector con el modelo y el prompt reales."""
    settings = load_stage_settings(os.environ, selection_model_variable(os.environ))
    model = OllamaLanguageModel(settings)
    model.verify_ready()
    prompt = SELECTION_PROMPT_FILE.read_text(encoding="utf-8").strip()
    return EvidenceSelector(model, prompt, evidence_policy.selection_max_sentences)


@pytest.fixture(scope="module")
def entries() -> list[KnowledgeEntry]:
    """Base de conocimiento real."""
    return load_entries(load_rag_settings(os.environ, PROJECT_ROOT).entries_file)


def evidence(entries: list[KnowledgeEntry], prefixes: tuple[str, ...]) -> list[EvidenceItem]:
    """Registros pedidos por el inicio de su id, etiquetados E1, E2…"""
    found = [next(e for e in entries if e.id.startswith(prefix)) for prefix in prefixes]
    return [EvidenceItem(f"E{n}", entry, SCORE) for n, entry in enumerate(found, start=1)]


def run(
    selector: EvidenceSelector, entries: list[KnowledgeEntry], case: SelectionCase
) -> SelectionTrace:
    """Corre el selector con la evidencia del caso y muestra lo que eligió."""
    analysis = AnalysisTurn(ThreadAction.CONTINUE, case.domain, case.summary)
    turn = TurnInput(case.message, urgent_reminder=case.urgent)
    trace = selector.select(analysis, turn, evidence(entries, case.entries), StageTimer())
    assert trace is not None and trace.verdict is not None, f"falló: {trace and trace.failure}"
    reviews = [(review.label, str(review.fit), review.unsaid) for review in trace.reviews]
    print(f"{case.message} → {trace.verdict} {reviews}: {shown_sentences(trace)}")
    return trace


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_selector_leaves_out_what_does_not_apply(
    selector: EvidenceSelector, entries: list[KnowledgeEntry], case: SelectionCase
) -> None:
    trace = run(selector, entries, case)

    shown = " ".join(shown_sentences(trace)).lower()
    assert not [word for word in case.forbidden if word in shown]
    assert not [word for word in case.required if word not in shown]


def test_selector_answers_a_direct_question_about_food(
    selector: EvidenceSelector, entries: list[KnowledgeEntry]
) -> None:
    case = SelectionCase(
        "comida con el registro de DASH",
        "¿qué puedo comer si tengo la presión alta?",
        "La persona pregunta qué puede comer si tiene la presión alta.",
        Domain.CARDIOVASCULAR,
        (DASH,),
        (),
    )

    trace = run(selector, entries, case)

    assert trace.verdict is not SelectionVerdict.NO_ANSWER
    assert "DASH" in " ".join(shown_sentences(trace))
