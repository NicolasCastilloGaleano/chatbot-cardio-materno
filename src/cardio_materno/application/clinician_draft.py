"""Nota y borrador de respuesta para el profesional de salud (HU-16, ADR 0022).

El modelo de respuesta escribe con su propio conocimiento, porque la base no tenía
información: por eso el borrador va marcado "sin respaldo de la base" y nunca llega a la
persona sin que el profesional lo apruebe o lo edite. La nota (posibles explicaciones, qué
preguntar y qué descartar) es solo para el profesional y nunca se envía (prompt v2,
2026-11-23). Recibe solo el resumen clínico del caso, nunca los mensajes de la persona, para no
enviar datos personales al modelo (AGENTS.md §4).
"""

import json
from dataclasses import dataclass
from typing import Any

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.escalation import CaseSnapshot

DRAFT_FIELD = "draft"
NOTE_FIELD = "note"
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {NOTE_FIELD: {"type": "string"}, DRAFT_FIELD: {"type": "string"}},
    "required": [NOTE_FIELD, DRAFT_FIELD],
}
CASE_TEMPLATE = "CASO (resumen sin datos de identificación, JSON):\n{case_json}"
MSG_EMPTY_DRAFT = "El modelo no devolvió un borrador."


@dataclass(frozen=True)
class ClinicianDraft:
    """Lo que escribe el modelo para un caso.

    Attributes:
        reply: Borrador para la persona; el profesional lo aprueba o lo edita.
        note: Nota solo para el profesional ("" si el modelo no la escribió).
    """

    reply: str
    note: str = ""


class ClinicianDraftWriter:
    """Escribe el borrador de un caso con el modelo de respuesta."""

    def __init__(self, model: LanguageModel, prompt: str) -> None:
        """Crea el redactor del borrador.

        Args:
            model: Modelo que escribe (el de respuesta).
            prompt: Instrucciones (`clinician_draft_prompt_v2.md`).
        """
        self._model = model
        self._prompt = prompt

    def write(self, snapshot: CaseSnapshot) -> ClinicianDraft:
        """Nota y borrador para el caso.

        Args:
            snapshot: Resumen clínico del caso.

        Returns:
            El borrador para la persona y la nota para el profesional.

        Raises:
            LanguageModelError: Si el modelo falla o no devuelve un borrador.
        """
        messages = [
            ChatMessage(Role.SYSTEM, self._prompt),
            ChatMessage(Role.USER, CASE_TEMPLATE.format(case_json=case_json(snapshot))),
        ]
        data = self._model.complete_json(messages, DRAFT_SCHEMA)
        draft, note = data.get(DRAFT_FIELD), data.get(NOTE_FIELD)
        if not isinstance(draft, str) or not draft.strip():
            raise LanguageModelError(MSG_EMPTY_DRAFT)
        return ClinicianDraft(draft.strip(), note.strip() if isinstance(note, str) else "")


def case_json(snapshot: CaseSnapshot) -> str:
    """El resumen clínico en JSON para el modelo, sin datos de identificación."""
    return json.dumps(
        {
            "dominio": str(snapshot.domain),
            "resumen": snapshot.summary,
            "sintomas": list(snapshot.symptoms),
            "signos": list(snapshot.signs),
            "consulta": snapshot.query,
            "motivo": snapshot.reason,
        },
        ensure_ascii=False,
    )
