"""Pruebas de la clasificación de vacíos de la base (HU-15, B-032)."""

from cardio_materno.application.gaps import (
    NO_CATEGORY,
    Gap,
    GapReason,
    gap_of,
    group_gaps,
    rejected_records,
)
from cardio_materno.application.grounded_reply import (
    ABSTENTION_TEXT,
    CLOSING_TEXT,
    NO_INFORMATION_TEXT,
    UNAVAILABLE_TEXT,
)
from cardio_materno.domain.trace import (
    EvidenceRef,
    InquiryTrace,
    OfferedSentence,
    RecordFit,
    RecordReview,
    ReplyTrace,
    SelectionTrace,
    SelectionVerdict,
    TurnMode,
)

HIGH = "Esa presión es marcadamente elevada y requiere contacto inmediato."
INQUIRY = InquiryTrace(TurnMode.ABSTAIN, best_score=0.52, top_category="Presión arterial")
SELECTION = SelectionTrace(
    offered=(
        OfferedSentence("E1.1", HIGH),
        OfferedSentence("E1.2", "Comunica los valores."),
        OfferedSentence("E2.1", "DASH es un patrón alimentario."),
    ),
    verdict=SelectionVerdict.NO_ANSWER,
    reviews=(
        RecordReview("E1", RecordFit.NO, "cifra de 190/125"),
        RecordReview("E2", RecordFit.YES),
    ),
)
TRACE = ReplyTrace(
    search_query="qué alimentos ayudan a controlar la presión",
    best_score=0.52,
    inquiry=INQUIRY,
    selection=SELECTION,
)


def test_an_abstention_is_a_gap_with_its_query_score_and_category() -> None:
    gap = gap_of(NO_INFORMATION_TEXT, TRACE)

    assert gap == Gap(
        "Presión arterial",
        "qué alimentos ayudan a controlar la presión",
        0.52,
        GapReason.NO_INFORMATION,
        (f"«{HIGH}» (no; supone: cifra de 190/125)",),
    )


def test_the_abstention_that_asks_for_details_and_the_closing_are_gaps() -> None:
    assert gap_of(ABSTENTION_TEXT, TRACE) is not None
    closing = gap_of(f"Recordatorio. {CLOSING_TEXT}", TRACE)

    assert closing is not None and closing.reason is GapReason.CLOSING


def test_an_answer_an_unavailable_search_or_a_turn_without_trace_are_not_gaps() -> None:
    assert gap_of("DASH es un patrón alimentario.", TRACE) is None
    assert gap_of(UNAVAILABLE_TEXT, TRACE) is None
    assert gap_of(NO_INFORMATION_TEXT, None) is None


def test_the_category_falls_back_to_the_evidence_and_then_to_none() -> None:
    with_evidence = ReplyTrace(evidence=(EvidenceRef("E1", "k1", 0.5, "Acidez"),))
    gap = gap_of(NO_INFORMATION_TEXT, with_evidence)
    empty = gap_of(NO_INFORMATION_TEXT, ReplyTrace())

    assert gap is not None and gap.category == "Acidez"
    assert empty is not None and empty.category == NO_CATEGORY and empty.best_score == 0.0


def test_a_long_record_is_shortened_and_accepted_records_are_left_out() -> None:
    selection = SelectionTrace(
        offered=(OfferedSentence("E1.1", "Frase " * 30),),
        reviews=(RecordReview("E1", RecordFit.PARTLY, "otra persona"),),
    )

    (record,) = rejected_records(selection)

    assert record.endswith("(en_parte; supone: otra persona)") and "…" in record
    assert rejected_records(None) == ()


def test_groups_go_from_the_most_frequent_category() -> None:
    gaps = [
        Gap("Acidez", "a", 0.4, GapReason.NO_INFORMATION),
        Gap("Presión", "b", 0.5, GapReason.NO_INFORMATION),
        Gap("Presión", "c", 0.6, GapReason.CLOSING),
    ]

    groups = group_gaps(gaps)

    assert [g.category for g in groups] == ["Presión", "Acidez"]
    assert groups[0].best_score == 0.6
