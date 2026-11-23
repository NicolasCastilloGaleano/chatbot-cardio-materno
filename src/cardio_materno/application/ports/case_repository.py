"""Puerto de los casos escalados a un profesional de salud (HU-16, ADR 0022).

Como los hilos (ADR 0015), cada persona recibe un repositorio acotado a sus casos: el servicio
de conversación nunca ve los casos de otra persona.
"""

from typing import Protocol

from cardio_materno.domain.escalation import ClinicalCase


class CaseRepository(Protocol):
    """Casos de una persona."""

    def open_case(self) -> ClinicalCase | None:
        """Devuelve el caso abierto de la persona (como máximo hay uno), o None."""
        ...

    def save(self, case: ClinicalCase) -> None:
        """Crea un caso o actualiza sus brechas, su resumen o su vencimiento.

        No cambia el estado ni el borrador (son del profesional): si el estado guardado ya no
        es el del caso recibido, no hace nada.
        """
        ...


class CaseStore(Protocol):
    """Acceso a los casos de cada persona."""

    def scoped(self, user_id: str) -> CaseRepository:
        """Repositorio que solo lee y escribe los casos de esa persona."""
        ...
