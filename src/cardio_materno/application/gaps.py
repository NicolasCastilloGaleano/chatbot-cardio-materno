"""Vacíos de la base de conocimiento para el equipo clínico (HU-15, B-032).

Un vacío es un turno de salud, dentro del alcance, en el que la persona no recibió
orientación: la abstención ("No tengo información validada…") o el cierre honesto de la
indagación. Se reconoce por el texto fijo de la respuesta, que no depende del modo de la
indagación ni del selector, y se describe con la traza que ya guarda cada respuesta: la
consulta de búsqueda reformulada por el análisis, la mejor similitud, la categoría y los
registros que el selector descartó. Nunca usa el mensaje de la persona.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.application.grounded_reply import CLOSING_TEXT, NO_INFORMATION_TEXT
from cardio_materno.domain.trace import RecordFit, ReplyTrace, SelectionTrace

NO_CATEGORY = "Sin categoría"
RECORD_PREVIEW_CHARS = 90
PREVIEW_MARK = "…"


class GapReason(StrEnum):
    """Por qué la persona no recibió orientación."""

    NO_INFORMATION = "sin información"
    CLOSING = "cierre de la indagación"


@dataclass(frozen=True)
class Gap:
    """Un turno sin orientación.

    Attributes:
        category: Categoría de la base más cercana a la consulta.
        query: Consulta de búsqueda que reformuló el análisis.
        best_score: Mejor similitud encontrada.
        reason: Por qué no hubo orientación.
        rejected: Registros que el selector descartó, con lo que suponían.
    """

    category: str
    query: str
    best_score: float
    reason: GapReason
    rejected: tuple[str, ...] = ()


@dataclass(frozen=True)
class GapGroup:
    """Vacíos de una categoría, del más frecuente al menos frecuente."""

    category: str
    gaps: tuple[Gap, ...]

    @property
    def best_score(self) -> float:
        """Mejor similitud vista en la categoría."""
        return max(gap.best_score for gap in self.gaps)


def gap_of(reply: str, trace: ReplyTrace | None) -> Gap | None:
    """El vacío de una respuesta del asistente, o None si la persona recibió orientación.

    Args:
        reply: Texto que vio la persona.
        trace: Traza de la respuesta (sin traza no hay nada que describir).

    Returns:
        El vacío con su categoría, consulta, similitud, motivo y registros descartados.
    """
    reason = gap_reason(reply)
    if reason is None or trace is None:
        return None
    return Gap(
        category_of(trace),
        trace.search_query,
        trace.best_score or 0.0,
        reason,
        rejected_records(trace.selection),
    )


def gap_reason(reply: str) -> GapReason | None:
    """Motivo según el texto fijo de la respuesta; None si hubo orientación."""
    if NO_INFORMATION_TEXT in reply:
        return GapReason.NO_INFORMATION
    if CLOSING_TEXT in reply:
        return GapReason.CLOSING
    return None


def category_of(trace: ReplyTrace) -> str:
    """Categoría del primer candidato o, si no hay, de la primera evidencia."""
    if trace.inquiry is not None and trace.inquiry.top_category:
        return trace.inquiry.top_category
    return trace.evidence[0].category if trace.evidence else NO_CATEGORY


def rejected_records(selection: SelectionTrace | None) -> tuple[str, ...]:
    """Registros que el selector no dio por buenos, con su primera frase y lo que suponían."""
    if selection is None:
        return ()
    return tuple(
        f"«{record_preview(selection, review.label)}» ({review.fit}; supone: {review.unsaid})"
        for review in selection.reviews
        if review.fit is not RecordFit.YES
    )


def record_preview(selection: SelectionTrace, label: str) -> str:
    """Primera frase ofrecida del registro, recortada, para que el equipo lo reconozca."""
    first = next((s.text for s in selection.offered if s.id.startswith(f"{label}.")), label)
    if len(first) <= RECORD_PREVIEW_CHARS:
        return first
    return first[: RECORD_PREVIEW_CHARS - 1].rstrip() + PREVIEW_MARK


def group_gaps(gaps: Iterable[Gap]) -> tuple[GapGroup, ...]:
    """Agrupa los vacíos por categoría, de la más frecuente a la menos frecuente."""
    by_category: defaultdict[str, list[Gap]] = defaultdict(list)
    for gap in gaps:
        by_category[gap.category].append(gap)
    groups = (GapGroup(category, tuple(items)) for category, items in by_category.items())
    return tuple(sorted(groups, key=lambda group: (-len(group.gaps), group.category)))
