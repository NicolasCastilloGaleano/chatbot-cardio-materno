"""API de la vista ciudadana: la conversación propia de una persona, sin datos de auditoría.

Expone solo lo que la persona necesita: su consentimiento (HU-01), sus mensajes y, por cada
respuesta, si es un aviso de alarma y en qué fuentes se apoya. Nunca entrega trazas,
síntomas interpretados, puntajes ni chats de otras personas: eso es de la vista del equipo.
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from cardio_materno.adapters.inbound.api.serializers import (
    Knowledge,
    citizen_message_to_dict,
    citizen_turn_to_dict,
    emergency_to_dict,
)
from cardio_materno.application.citizen_chat import CitizenChat
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.errors import (
    ChatNotFoundError,
    ChatReadOnlyError,
    ConsentRequiredError,
    LanguageModelError,
)
from cardio_materno.application.ports.chat_audit import ChatAudit

logger = logging.getLogger(__name__)
SESSION_NOT_FOUND = "No encontramos esta conversación. Empieza una nueva."
CONSENT_REQUIRED = "Para continuar necesitamos que aceptes el uso de tus mensajes."
SESSION_BUSY = "Esta conversación está abierta en otro lugar. Intenta más tarde."
MODEL_UNAVAILABLE = (
    "No pude preparar una respuesta en este momento. Intenta de nuevo en unos minutos. "
    "Si es una emergencia, llama al 123 o acude a urgencias."
)
MODEL_ERROR_LOG = "Fallo del modelo en la vista ciudadana (etapa: %s): %s"
UNKNOWN_STAGE = "desconocida"
EMERGENCY_UNAVAILABLE = "Información no disponible. Si es una emergencia, llama al 123."
MAX_MESSAGES = 200
MAX_TEXT_CHARS = 2000


class ConsentRequest(BaseModel):
    """Decisión de la persona sobre el uso de sus mensajes.

    Attributes:
        accepted: True si acepta; False si rechaza.
    """

    accepted: bool


class CitizenMessageRequest(BaseModel):
    """Mensaje que escribe la persona.

    Attributes:
        text: Texto del mensaje.
    """

    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


def add_citizen_routes(
    app: FastAPI, citizen: CitizenChat, audit: ChatAudit, knowledge: Knowledge
) -> None:
    """Registra las rutas de la vista ciudadana bajo `/api/me` y la información pública."""
    _add_public_routes(app, knowledge)
    _add_session_routes(app, citizen)
    _add_conversation_routes(app, citizen, audit, knowledge)


def _add_public_routes(app: FastAPI, knowledge: Knowledge) -> None:
    """Registra lo que se puede leer sin conversación, sin consentimiento y sin enviar datos."""

    @app.get("/api/public/emergency")
    def emergency() -> dict[str, Any]:
        """Indicaciones generales para buscar atención urgente. No recibe ni guarda nada."""
        if knowledge.emergency is None:
            raise HTTPException(status_code=404, detail=EMERGENCY_UNAVAILABLE)
        return emergency_to_dict(knowledge.emergency)


def _add_session_routes(app: FastAPI, citizen: CitizenChat) -> None:
    """Registra la creación de la conversación y el consentimiento."""

    @app.post("/api/me/sessions", status_code=201)
    def start_session() -> dict[str, Any]:
        """Abre una conversación nueva para quien visita la página."""
        return session_to_dict(citizen, citizen.start())

    @app.get("/api/me/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        """Estado de la conversación guardada en el navegador de la persona."""
        return _guarded(lambda: session_to_dict(citizen, session_id))

    @app.post("/api/me/sessions/{session_id}/consent")
    def decide_consent(session_id: str, request: ConsentRequest) -> dict[str, Any]:
        """Registra la aceptación o el rechazo del consentimiento."""
        _guarded(lambda: citizen.decide_consent(session_id, request.accepted))
        return session_to_dict(citizen, session_id)

    @app.post("/api/me/sessions/{session_id}/research")
    def decide_research(session_id: str, request: ConsentRequest) -> dict[str, Any]:
        """Registra la autorización opcional para informes agregados (o su retiro)."""
        _guarded(lambda: citizen.decide_research(session_id, request.accepted))
        return session_to_dict(citizen, session_id)


def _add_conversation_routes(
    app: FastAPI, citizen: CitizenChat, audit: ChatAudit, knowledge: Knowledge
) -> None:
    """Registra la lectura y el envío de mensajes de la propia conversación."""

    @app.get("/api/me/sessions/{session_id}/messages")
    def messages(session_id: str, after: int = Query(0, ge=0)) -> dict[str, Any]:
        """Mensajes guardados de la conversación, posteriores a `after`."""
        _guarded(lambda: citizen.consent_status(session_id))
        page = audit.messages_after(session_id, after, MAX_MESSAGES)
        return {"messages": [citizen_message_to_dict(e, knowledge) for e in page.entries]}

    @app.post("/api/me/sessions/{session_id}/messages")
    def send(session_id: str, request: CitizenMessageRequest) -> dict[str, Any]:
        """Procesa el mensaje y devuelve la respuesta en el formato de la persona."""
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Escribe tu mensaje.")
        turn: TurnResult = _guarded(lambda: citizen.send(session_id, text))
        return citizen_turn_to_dict(turn, knowledge)


def session_to_dict(citizen: CitizenChat, session_id: str) -> dict[str, Any]:
    """Identificador de la conversación, consentimiento y autorización para informes."""
    return {
        "session": session_id,
        "consent": str(citizen.consent_status(session_id)),
        "consent_required": citizen.policy.consent_required,
        "research": str(citizen.research_status(session_id)),
        "research_text": citizen.policy.research_text,
    }


def _guarded[T](action: Callable[[], T]) -> T:
    """Ejecuta una acción del caso de uso y traduce sus errores a respuestas HTTP.

    Raises:
        HTTPException: 404 si la conversación no existe, 403 si falta el consentimiento,
            409 si está abierta en una consola, 502 si falla el modelo.
    """
    try:
        return action()
    except ChatNotFoundError as error:
        raise HTTPException(status_code=404, detail=SESSION_NOT_FOUND) from error
    except ConsentRequiredError as error:
        raise HTTPException(status_code=403, detail=CONSENT_REQUIRED) from error
    except ChatReadOnlyError as error:
        raise HTTPException(status_code=409, detail=SESSION_BUSY) from error
    except LanguageModelError as error:
        logger.warning(MODEL_ERROR_LOG, error.stage or UNKNOWN_STAGE, error)
        raise HTTPException(status_code=502, detail=MODEL_UNAVAILABLE) from error
