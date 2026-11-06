"""Pruebas de la detección de preguntas repetidas (HU-13, paso 1.3)."""

from cardio_materno.domain.grounding import GroundingPolicy, repeats_question, stem_overlap

POLICY = GroundingPolicy()


def test_the_same_question_reworded_slightly_is_a_repeat() -> None:
    asked = ["¿El ardor sube hacia la garganta y viene con sabor ácido?"]

    assert repeats_question("¿El ardor te sube hacia la garganta con sabor ácido?", asked, POLICY)


def test_a_different_question_is_not_a_repeat() -> None:
    asked = ["¿El ardor sube hacia la garganta?"]

    assert not repeats_question("¿Desde cuándo tienes el ardor?", asked, POLICY)
    assert not repeats_question("¿El ardor sube hacia la garganta?", [], POLICY)


def test_stem_overlap_is_jaccard() -> None:
    assert stem_overlap(frozenset({"a", "b"}), frozenset({"b", "c"})) == 1 / 3
    assert stem_overlap(frozenset(), frozenset()) == 1.0
