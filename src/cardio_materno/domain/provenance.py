"""Procedencia de los registros de la base de conocimiento: lote, revisión y fuentes.

Permite decir de qué fuente sale una respuesta y qué revisión tiene el registro que la
respalda. El estado de revisión es el que registró el equipo para cada lote; ninguno
equivale a validación clínica, que sigue pendiente para toda la base (B-019).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

UNKNOWN_REVIEW = "sin_registro"
UNKNOWN_REVIEW_LABEL = "Sin registro de procedencia"


@dataclass(frozen=True)
class SourceRef:
    """Fuente del catálogo (`docs/04-datos/fuentes-base-conocimiento.md`).

    Attributes:
        id: Identificador en el catálogo (p. ej., `OPS-HEARTS`).
        entity: Entidad que la publica.
        title: Título del documento.
        version: Versión o fecha de consulta.
        url: Dirección pública.
    """

    id: str
    entity: str
    title: str
    version: str
    url: str


@dataclass(frozen=True)
class EntryProvenance:
    """De dónde viene un registro.

    Attributes:
        batch: Lote en el que entró a la base ("" si no hay registro).
        batch_label: Nombre legible del lote.
        review: Estado de revisión del lote (p. ej., `validada_para_prototipo`).
        review_label: Estado de revisión en una frase.
        sources: Fuentes que citó el borrador del registro (vacío si no trae fuente propia).
    """

    batch: str = ""
    batch_label: str = ""
    review: str = UNKNOWN_REVIEW
    review_label: str = UNKNOWN_REVIEW_LABEL
    sources: tuple[SourceRef, ...] = ()


@dataclass(frozen=True)
class Provenance:
    """Procedencia de toda la base.

    Attributes:
        records: Procedencia de los registros que no pertenecen al lote por defecto.
        default: Procedencia de los demás registros.
    """

    records: Mapping[str, EntryProvenance] = field(default_factory=dict)
    default: EntryProvenance = EntryProvenance()

    def of(self, entry_id: str) -> EntryProvenance:
        """Procedencia de un registro (la del lote por defecto si no tiene una propia)."""
        return self.records.get(entry_id, self.default)
