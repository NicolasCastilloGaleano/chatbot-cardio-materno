"""Base de conocimiento y evidencia recuperada (HU-02, ADR 0008)."""

from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.trace import RetrievalStatus

__all__ = ["EvidenceItem", "Focus", "KnowledgeEntry", "RetrievalResult", "RetrievalStatus"]


class Focus(StrEnum):
    """Enfoque de un registro de la base."""

    INQUIRE = "Indagar"  # Qué preguntar y qué señales importan en una situación.
    SOLVE = "Solucionar"  # Orientación para una situación.


@dataclass(frozen=True)
class KnowledgeEntry:
    """Registro pregunta/respuesta de la base de conocimiento.

    Attributes:
        id: Identificador estable (hash del piloto).
        domain: Dominio de salud.
        category: Categoría temática.
        focus: Enfoque del registro.
        question: Pregunta tipo.
        answer: Respuesta validada para el prototipo.
    """

    id: str
    domain: Domain
    category: str
    focus: Focus
    question: str
    answer: str

    @property
    def embedding_text(self) -> str:
        """Texto con el que se calcula su embedding (mismo formato que el piloto)."""
        return f"Pregunta: {self.question} \nRespuesta: {self.answer}"


@dataclass(frozen=True)
class EvidenceItem:
    """Registro recuperado como evidencia para un turno.

    Attributes:
        label: Etiqueta corta que ve el agente (E1, E2…).
        entry: Registro de la base.
        score: Similitud coseno con la consulta (no es confianza clínica).
    """

    label: str
    entry: KnowledgeEntry
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    """Evidencia encontrada para una consulta.

    Attributes:
        status: Si hay evidencia suficiente, insuficiente o el buscador no está disponible.
        items: Evidencia que superó el umbral (vacío si no hay).
        best_score: Mejor similitud vista, aunque no supere el umbral (para diagnóstico).
    """

    status: RetrievalStatus
    items: tuple[EvidenceItem, ...] = ()
    best_score: float = 0.0

    @property
    def labels(self) -> tuple[str, ...]:
        """Etiquetas de la evidencia ofrecida."""
        return tuple(item.label for item in self.items)
