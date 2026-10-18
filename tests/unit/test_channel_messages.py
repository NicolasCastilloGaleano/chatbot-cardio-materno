"""Pruebas de la división de respuestas largas (HU-09)."""

from cardio_materno.application.channel_messages import split_message


def test_short_text_is_a_single_part() -> None:
    assert split_message("  Hola, ¿cómo estás?  ", 50) == ["Hola, ¿cómo estás?"]


def test_long_text_is_split_without_cutting_words() -> None:
    text = "uno dos tres cuatro cinco seis siete"

    parts = split_message(text, 10)

    assert all(len(part) <= 10 for part in parts)
    assert " ".join(parts) == text


def test_paragraphs_are_kept_inside_a_part_when_they_fit() -> None:
    assert split_message("Primero.\n\nSegundo.", 100) == ["Primero.\n\nSegundo."]


def test_a_word_longer_than_the_limit_is_cut() -> None:
    assert split_message("abcdefghij", 4) == ["abcd", "efgh", "ij"]


def test_empty_text_has_no_parts() -> None:
    assert split_message("   ", 10) == []
