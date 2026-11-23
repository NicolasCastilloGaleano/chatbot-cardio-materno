"""Apartado del profesional de salud en la interfaz local (HU-16, ADR 0022).

Toda ruta de la API exige el encabezado `X-Clinician-Key` con la clave del `.env`
(`CLINICIAN_ACCESS_KEY`), comparada en tiempo constante. Sin clave configurada, el apartado no
se registra y sus rutas no existen. La interfaz sigue solo en la propia máquina (ADR 0013).
"""

import hmac
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cardio_materno.adapters.inbound.api.serializers import CHANNEL_LABELS
from cardio_materno.application.clinician_review import ClinicianReview
from cardio_materno.application.errors import (
    CaseChannelNotSupportedError,
    CaseConflictError,
    CaseNotFoundError,
    DraftNotReadyError,
)
from cardio_materno.application.ports.case_inbox import InboxCase
from cardio_materno.application.ports.chat_audit import ChatAudit
from cardio_materno.domain.escalation import CaseSnapshot

KEY_HEADER = "X-Clinician-Key"
MSG_BAD_KEY = "Clave de profesional no válida."
MSG_NOT_FOUND = "Caso no encontrado."
MSG_NO_DRAFT = "Primero genera el borrador, o escribe la respuesta con Modificar."
CONVERSATION_LIMIT = 50
MAX_REPLY_CHARS = 4000


class ModifyRequest(BaseModel):
    """Respuesta o mensaje escrito por el profesional.

    Attributes:
        text: Texto que recibirá la persona.
    """

    text: str = Field(min_length=1, max_length=MAX_REPLY_CHARS)


def add_clinician_routes(
    app: FastAPI, review: ClinicianReview, audit: ChatAudit, access_key: str, page: Path
) -> None:
    """Registra la página `/medico` y la API del profesional.

    Args:
        app: Aplicación FastAPI.
        review: Casos del profesional.
        audit: Lectura de los chats, para mostrar la conversación del caso.
        access_key: Clave del profesional (no vacía).
        page: Ruta del archivo `medico.html`.
    """
    guard = Depends(key_checker(access_key))

    @app.get("/medico", include_in_schema=False)
    def clinician_page() -> FileResponse:
        """Entrega la página del profesional (la API exige la clave)."""
        return FileResponse(page, headers={"Cache-Control": "no-cache"})

    add_case_routes(app, review, audit, guard)
    add_reply_routes(app, review, guard)
    add_contact_routes(app, review, guard)


def add_case_routes(app: FastAPI, review: ClinicianReview, audit: ChatAudit, guard: Any) -> None:
    """Registra la lista de casos abiertos y el detalle de un caso.

    Args:
        app: Aplicación FastAPI.
        review: Casos del profesional.
        audit: Lectura de los chats, para mostrar la conversación del caso.
        guard: Dependencia que exige la clave del profesional.
    """

    @app.get("/api/clinician/cases", dependencies=[guard])
    def list_cases() -> list[dict[str, Any]]:
        """Casos abiertos, del más antiguo al más nuevo."""
        return [case_view(review, found) for found in review.pending_cases()]

    @app.get("/api/clinician/cases/{case_id}", dependencies=[guard])
    def get_case(case_id: str) -> dict[str, Any]:
        """Un caso con la conversación de la persona."""
        found = run_case_action(lambda: review.case(case_id))
        view = case_view(review, found)
        return {**view, "messages": conversation(audit, found.user_id)}


def add_reply_routes(app: FastAPI, review: ClinicianReview, guard: Any) -> None:
    """Registra el borrador y las respuestas que resuelven el caso (aprobar o modificar).

    Args:
        app: Aplicación FastAPI.
        review: Casos del profesional.
        guard: Dependencia que exige la clave del profesional.
    """

    @app.post("/api/clinician/cases/{case_id}/draft", dependencies=[guard])
    def prepare_draft(case_id: str) -> dict[str, Any]:
        """Genera el borrador marcado "sin respaldo de la base" (o lo devuelve si ya existe)."""
        return case_view(review, run_case_action(lambda: review.prepare_draft(case_id)))

    @app.post("/api/clinician/cases/{case_id}/approve", dependencies=[guard])
    def approve(case_id: str) -> dict[str, Any]:
        """Envía el borrador tal cual."""
        return case_view(review, run_case_action(lambda: review.approve(case_id)))

    @app.post("/api/clinician/cases/{case_id}/modify", dependencies=[guard])
    def modify(case_id: str, body: ModifyRequest) -> dict[str, Any]:
        """Envía el texto del profesional."""
        return case_view(review, run_case_action(lambda: review.modify(case_id, body.text)))


def add_contact_routes(app: FastAPI, review: ClinicianReview, guard: Any) -> None:
    """Registra las rutas del contacto directo (fase 3 de la HU-16).

    Args:
        app: Aplicación FastAPI.
        review: Casos del profesional.
        guard: Dependencia que exige la clave del profesional.
    """

    @app.post("/api/clinician/cases/{case_id}/contact", dependencies=[guard])
    def start_contact(case_id: str) -> dict[str, Any]:
        """Abre el contacto directo: los mensajes de la persona llegan al profesional."""
        return case_view(review, run_case_action(lambda: review.start_contact(case_id)))

    @app.post("/api/clinician/cases/{case_id}/messages", dependencies=[guard])
    def send_message(case_id: str, body: ModifyRequest) -> dict[str, Any]:
        """Envía un mensaje del profesional durante el contacto."""
        return case_view(review, run_case_action(lambda: review.send_message(case_id, body.text)))

    @app.post("/api/clinician/cases/{case_id}/close", dependencies=[guard])
    def end_contact(case_id: str) -> dict[str, Any]:
        """Cierra el contacto: el asistente vuelve a responder."""
        return case_view(review, run_case_action(lambda: review.end_contact(case_id)))


def key_checker(access_key: str) -> Callable[[str], None]:
    """Dependencia que rechaza las solicitudes sin la clave del profesional."""

    def check(key: Annotated[str, Header(alias=KEY_HEADER)] = "") -> None:
        if not hmac.compare_digest(key.encode("utf-8"), access_key.encode("utf-8")):
            raise HTTPException(status_code=401, detail=MSG_BAD_KEY)

    return check


def run_case_action(action: Callable[[], InboxCase]) -> InboxCase:
    """Ejecuta una acción del caso y traduce sus errores a respuestas HTTP."""
    try:
        result = action()
    except CaseNotFoundError as error:
        raise HTTPException(status_code=404, detail=MSG_NOT_FOUND) from error
    except DraftNotReadyError as error:
        raise HTTPException(status_code=409, detail=MSG_NO_DRAFT) from error
    except (CaseConflictError, CaseChannelNotSupportedError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return result


def case_view(review: ClinicianReview, found: InboxCase) -> dict[str, Any]:
    """Caso para el profesional, con si hoy se le puede escribir a la persona."""
    return case_to_dict(found, review.deliverable(found))


def case_to_dict(found: InboxCase, deliverable: bool) -> dict[str, Any]:
    """Caso para el profesional: estado, plazos, canal, resumen y borrador."""
    case = found.case
    return {
        "id": case.id,
        "status": str(case.status),
        "channel": str(found.channel),
        "channel_label": CHANNEL_LABELS.get(found.channel, str(found.channel)),
        "deliverable": deliverable,
        "gap_count": case.gap_count,
        "created_at": case.created_at.isoformat(),
        "expires_at": case.expires_at.isoformat(),
        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
        "snapshot": snapshot_to_dict(case.snapshot),
        "draft": case.draft,
        "draft_status": str(case.draft_status),
        "draft_note": case.draft_note,
    }


def snapshot_to_dict(snapshot: CaseSnapshot) -> dict[str, Any]:
    """Resumen clínico del caso, sin datos de identificación."""
    return {
        "domain": str(snapshot.domain),
        "summary": snapshot.summary,
        "symptoms": list(snapshot.symptoms),
        "signs": list(snapshot.signs),
        "query": snapshot.query,
        "reason": snapshot.reason,
        "category": snapshot.category,
        "best_score": snapshot.best_score,
    }


def conversation(audit: ChatAudit, user_id: str) -> list[dict[str, Any]]:
    """Últimos mensajes del chat de la persona, del más antiguo al más reciente."""
    page = audit.message_page(user_id, None, CONVERSATION_LIMIT)
    return [
        {
            "role": str(entry.message.role),
            "content": entry.message.content,
            "created_at": entry.message.created_at.isoformat()
            if entry.message.created_at
            else None,
        }
        for entry in page.entries
    ]
