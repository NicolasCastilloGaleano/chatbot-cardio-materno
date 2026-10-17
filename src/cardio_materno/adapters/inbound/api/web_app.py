"""Aplicación web local para conversar y auditar las trazas del agente."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cardio_materno.application.conversation_service import ConversationService, TurnResult
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ChatMessage, ConversationThread
from cardio_materno.domain.knowledge import KnowledgeEntry
from cardio_materno.domain.trace import EvidenceRef, GroundingCheck, ReplyTrace

STATIC_DIR = Path(__file__).with_name("static")
APP_TITLE = "Chat cardio-materno: demostración y auditoría"
ERROR_MODEL_MESSAGE = "No se pudo generar la respuesta. Puedes intentarlo de nuevo."
MISSING_ENTRY_TEXT = "Registro no disponible"


class SendMessageRequest(BaseModel):
    """Mensaje enviado desde la interfaz."""

    text: str = Field(min_length=1, max_length=4000)


def create_app(
    service: ConversationService,
    repository: ThreadRepository,
    entries: list[KnowledgeEntry],
) -> FastAPI:
    """Construye la aplicación HTTP con sus dependencias inyectadas.

    Args:
        service: Caso de uso conversacional de una sesión.
        repository: Repositorio de solo lectura para consultar el historial.
        entries: Registros de conocimiento usados para ampliar la evidencia de auditoría.

    Returns:
        Aplicación FastAPI lista para servir en loopback.
    """
    app = FastAPI(title=APP_TITLE, docs_url=None, redoc_url=None)
    entry_index = {entry.id: entry for entry in entries}
    _add_page_routes(app)
    _add_message_routes(app, service, entry_index)
    _add_history_routes(app, repository, entry_index)
    return app


def _add_page_routes(app: FastAPI) -> None:
    """Registra la página y los archivos estáticos locales."""

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        """Entrega el cliente web."""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/static/{asset_name}", include_in_schema=False)
    def static_asset(asset_name: str) -> FileResponse:
        """Entrega archivos estáticos limitados al directorio de la interfaz."""
        asset = (STATIC_DIR / asset_name).resolve()
        if asset.parent != STATIC_DIR.resolve() or not asset.is_file():
            raise HTTPException(status_code=404, detail="Recurso no encontrado")
        return FileResponse(asset)


def _add_message_routes(
    app: FastAPI, service: ConversationService, entries: dict[str, KnowledgeEntry]
) -> None:
    """Registra los endpoints para enviar mensajes y cerrar la sesión activa."""

    @app.post("/api/messages")
    def send_message(request: SendMessageRequest) -> dict[str, Any]:
        """Procesa un mensaje y devuelve respuesta y datos de auditoría."""
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="El mensaje no puede estar vacío")
        try:
            result = service.send(text)
        except LanguageModelError as error:
            raise HTTPException(status_code=502, detail=ERROR_MODEL_MESSAGE) from error
        return turn_to_dict(result, entries)

    @app.post("/api/session/end")
    def end_session() -> dict[str, str]:
        """Cierra el hilo activo antes de iniciar una sesión nueva desde la interfaz."""
        service.end_session()
        return {"status": "cerrada"}


def _add_history_routes(
    app: FastAPI, repository: ThreadRepository, entries: dict[str, KnowledgeEntry]
) -> None:
    """Registra endpoints de consulta de hilos persistidos."""

    @app.get("/api/threads")
    def list_threads() -> list[dict[str, Any]]:
        """Lista hilos guardados para su consulta de solo lectura."""
        return [thread_to_dict(thread) for thread in repository.list_threads()]

    @app.get("/api/threads/{thread_id}")
    def get_thread(thread_id: str) -> dict[str, Any]:
        """Devuelve un hilo y sus mensajes completos con las trazas ampliadas."""
        thread = repository.get_thread(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Hilo no encontrado")
        messages = [
            message_to_dict(message, entries) for message in repository.all_messages(thread_id)
        ]
        return {"thread": thread_to_dict(thread), "messages": messages}


def turn_to_dict(result: TurnResult, entries: dict[str, KnowledgeEntry]) -> dict[str, Any]:
    """Convierte el turno y las alertas al contrato HTTP del cliente.

    Args:
        result: Turno procesado por el caso de uso.
        entries: Registros usados para completar el texto de evidencia.

    Returns:
        Datos JSON de la respuesta, el hilo, las alertas y la traza.
    """
    return {
        "reply": result.reply,
        "thread": thread_to_dict(result.thread) if result.thread else None,
        "is_new_thread": result.is_new_thread,
        "out_of_scope": result.out_of_scope,
        "alerts": [alert_to_dict(alert) for alert in result.alerts],
        "trace": trace_to_dict(result.trace, entries) if result.trace else None,
    }


def thread_to_dict(thread: ConversationThread) -> dict[str, str]:
    """Serializa los datos visibles de un hilo.

    Args:
        thread: Hilo que se expondrá a la interfaz.

    Returns:
        Identificador, resumen, dominio, estado y fechas en formato JSON.
    """
    return {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def message_to_dict(message: ChatMessage, entries: dict[str, KnowledgeEntry]) -> dict[str, Any]:
    """Serializa un mensaje y su traza, si existe.

    Args:
        message: Mensaje persistido.
        entries: Registros usados para completar el texto de evidencia.

    Returns:
        Mensaje con el rol, contenido, fecha y traza opcional.
    """
    return {
        "role": str(message.role),
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "trace": trace_to_dict(message.trace, entries) if message.trace else None,
    }


def trace_to_dict(trace: ReplyTrace, entries: dict[str, KnowledgeEntry]) -> dict[str, Any]:
    """Serializa la traza y resuelve la evidencia recuperada.

    Args:
        trace: Traza persistida del turno.
        entries: Registros de conocimiento indexados por identificador.

    Returns:
        Datos de auditoría con evidencia, citas, verificación y tiempos.
    """
    return {
        "reported_symptoms": list(trace.reported_symptoms),
        "reported_signs": list(trace.reported_signs),
        "unstated_symptoms": list(trace.unstated_symptoms),
        "search_query": trace.search_query,
        "scope": trace.scope,
        "scope_reason": trace.scope_reason,
        "retrieval_status": str(trace.retrieval_status) if trace.retrieval_status else None,
        "best_score": trace.best_score,
        "evidence": [evidence_to_dict(ref, entries) for ref in trace.evidence],
        "cited_evidence": list(trace.cited_evidence),
        "uncited": trace.uncited,
        "grounding": grounding_to_dict(trace.grounding) if trace.grounding else None,
        "timings": [{"stage": t.stage, "seconds": t.seconds} for t in trace.timings],
    }


def evidence_to_dict(ref: EvidenceRef, entries: dict[str, KnowledgeEntry]) -> dict[str, Any]:
    """Serializa una referencia de evidencia con la pregunta y la respuesta del registro.

    Args:
        ref: Referencia guardada en la traza (etiqueta, id, puntaje, categoría).
        entries: Registros de conocimiento indexados por identificador.

    Returns:
        La referencia con el texto del registro, o un aviso si ya no está en la base.
    """
    entry = entries.get(ref.entry_id)
    return {
        "label": ref.label,
        "entry_id": ref.entry_id,
        "score": ref.score,
        "category": ref.category,
        "question": entry.question if entry else MISSING_ENTRY_TEXT,
        "answer": entry.answer if entry else "",
    }


def grounding_to_dict(check: GroundingCheck) -> dict[str, Any]:
    """Serializa la verificación del respaldo de la respuesta (ADR 0010).

    Args:
        check: Resultado de la verificación guardado en la traza.

    Returns:
        Frases mostradas, total, uso del texto literal y frases descartadas.
    """
    return {
        "supported": check.supported,
        "total": check.total,
        "literal": check.literal,
        "dropped": list(check.dropped),
    }


def alert_to_dict(alert: Alert) -> dict[str, Any]:
    """Serializa una alerta determinista.

    Args:
        alert: Alerta registrada por las reglas del dominio.

    Returns:
        Regla, gravedad, origen y fecha de la alerta.
    """
    return {
        "rule_ids": list(alert.rule_ids),
        "severity": str(alert.severity),
        "origin": str(alert.origin),
        "created_at": alert.created_at.isoformat(),
    }
