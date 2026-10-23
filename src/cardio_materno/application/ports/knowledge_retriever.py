"""Puerto de recuperación de evidencia (RAG)."""

from dataclasses import dataclass
from typing import Protocol

from cardio_materno.domain.conversation import Domain
from cardio_materno.domain.knowledge import RetrievalResult, Stage


@dataclass(frozen=True)
class EvidenceQuery:
    """Consulta de evidencia.

    Attributes:
        text: Texto de búsqueda (mensaje, resumen del hilo y síntomas).
        domains: Dominios donde buscar (vacío = todos).
        motives: Cuadros de la base v2 donde buscar (vacío = todos).
        stages: Etapas de la base v2 donde buscar (vacío = todas).
        anchored: True si el cuadro ya está identificado (ADR 0017): la similitud solo
            ordena las etapas permitidas y no se exige el umbral de la política.
    """

    text: str
    domains: tuple[Domain, ...] = ()
    motives: tuple[str, ...] = ()
    stages: tuple[Stage, ...] = ()
    anchored: bool = False


class KnowledgeRetriever(Protocol):
    """Busca en la base de conocimiento la evidencia que respalda una respuesta."""

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        """Devuelve la evidencia que supera el umbral de la política.

        Nunca lanza excepciones: si el buscador falla, devuelve estado UNAVAILABLE.
        """
        ...
