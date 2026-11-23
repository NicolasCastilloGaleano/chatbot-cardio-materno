"""Borrador de respuesta para el profesional de salud (HU-16, ADR 0022).

El modelo de respuesta escribe con su propio conocimiento, porque la base no tenía
información: por eso el borrador va marcado "sin respaldo de la base" y nunca llega a la
persona sin que el profesional lo apruebe o lo edite. Recibe solo el resumen clínico del caso,
nunca los mensajes de la persona, para no enviar datos personales al modelo (AGENTS.md §4).
"""

import json
from typing import Any

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.escalation import CaseSnapshot

DRAFT_FIELD = "draft"
DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {DRAFT_FIELD: {"type": "string"}},
    "required": [DRAFT_FIELD],
}
CASE_TEMPLATE = "CASO (resumen sin datos de identificación, JSON):\n{case_json}"
MSG_EMPTY_DRAFT = "El modelo no devolvió un borrador."


class ClinicianDraftWriter:
    """Escribe el borrador de un caso con el modelo de respuesta."""

    def __init__(self, model: LanguageModel, prompt: str) -> None:
        """Crea el redactor del borrador.

        Args:
            model: Modelo que escribe (el de respuesta).
            prompt: Instrucciones (`clinician_draft_prompt_v1.md`).
        """
        self._model = model
        self._prompt = prompt

    def write(self, snapshot: CaseSnapshot) -> str:
        """Borrador para el caso.

        Args:
            snapshot: Resumen clínico del caso.

        Returns:
            El texto del borrador.

        Raises:
            LanguageModelError: Si el modelo falla o no devuelve un borrador.
        """
        messages = [
            ChatMessage(Role.SYSTEM, self._prompt),
            ChatMessage(Role.USER, CASE_TEMPLATE.format(case_json=case_json(snapshot))),
        ]
        draft = self._model.complete_json(messages, DRAFT_SCHEMA).get(DRAFT_FIELD)
        if not isinstance(draft, str) or not draft.strip():
            raise LanguageModelError(MSG_EMPTY_DRAFT)
        return draft.strip()


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
