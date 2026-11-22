"""Puerto de la bandeja de casos del profesional de salud (HU-16, ADR 0022).

A diferencia de `CaseRepository`, que ve solo los casos de una persona, la bandeja ve los
casos de todas: la usa el apartado del médico. Los cambios de estado son optimistas
(`update_if`), porque la web y WhatsApp corren en procesos distintos sobre la misma base.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from cardio_materno.domain.escalation import CaseStatus, ClinicalCase
from cardio_materno.domain.user import Channel


@dataclass(frozen=True)
class InboxCase:
    """Un caso con lo necesario para atenderlo.

    Attributes:
        case: El caso.
        user_id: Persona del caso (seudónimo; nunca el teléfono).
        channel: Canal del chat de la persona, para saber cómo entregar la respuesta.
    """

    case: ClinicalCase
    user_id: str
    channel: Channel


class CaseInbox(Protocol):
    """Casos de todas las personas, para el profesional."""

    def list_open(self) -> list[InboxCase]:
        """Casos abiertos de los que la persona recibió el aviso, del más antiguo al más nuevo."""
        ...

    def get(self, case_id: str) -> InboxCase | None:
        """Un caso por su id, o None si no existe."""
        ...

    def update_if(self, case: ClinicalCase, expected: CaseStatus) -> bool:
        """Guarda el caso solo si su estado sigue siendo `expected`; False si alguien lo cambió."""
        ...

    def expire_due(self, now: datetime) -> int:
        """Vence los casos abiertos cuyo plazo pasó; devuelve cuántos venció."""
        ...
