"""Interfaz web local de auditoría multicanal y chat directo (HU-08, HU-10, ADR 0013 y 0016).

Audita los chats de todos los canales (uno por persona) y permite seguir conversando en los
de consola y web. WhatsApp, Telegram y el histórico son de solo lectura: el servidor rechaza
los envíos a esos chats, no solo la interfaz.
"""

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cardio_materno.adapters.inbound.api.serializers import (
    CHANNEL_LABELS,
    LOCK_TEXTS,
    Entries,
    chat_to_dict,
    entry_to_dict,
    turn_to_dict,
)
from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.direct_chat import DirectChat
from cardio_materno.application.errors import (
    ChatNotFoundError,
    ChatReadOnlyError,
    LanguageModelError,
)
from cardio_materno.application.ports.chat_audit import ChatAudit, ChatPage, ChatSummary
from cardio_materno.domain.knowledge import KnowledgeEntry
from cardio_materno.domain.user import Channel, ChatLock, chat_lock

STATIC_DIR = Path(__file__).with_name("static")
APP_TITLE = "Chat cardio-materno: auditoría multicanal"
ERROR_MODEL_MESSAGE = "No se pudo generar la respuesta. Puedes intentarlo de nuevo."
CHAT_NOT_FOUND = "Chat no encontrado"
CHAT_BUSY = "Ya se está procesando un mensaje en este chat. Espera la respuesta."
NOT_LIVE = "El chat no está en uso en una consola."
EMPTY_TEXT = "El mensaje no puede estar vacío"
MAX_LIMIT = 200
DEFAULT_CHAT_LIMIT = 50


@dataclass(frozen=True)
class WebOptions:
    """Opciones de la interfaz.

    Attributes:
        page_size: Mensajes por página al abrir un chat o subir con el scroll.
        poll_seconds: Cada cuánto la interfaz busca mensajes nuevos.
    """

    page_size: int
    poll_seconds: float


class SendMessageRequest(BaseModel):
    """Mensaje enviado desde la interfaz.

    Attributes:
        text: Texto del mensaje.
        after: Último `seq` que tiene la interfaz, para devolver solo lo nuevo.
    """

    text: str = Field(min_length=1, max_length=4000)
    after: int = Field(default=0, ge=0)


class ChatLocks:
    """Un turno a la vez por chat dentro de este proceso."""

    def __init__(self) -> None:
        """Crea el registro de candados."""
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def try_acquire(self, user_id: str) -> bool:
        """Toma el candado del chat sin esperar; False si otro turno lo tiene."""
        with self._guard:
            lock = self._locks.setdefault(user_id, threading.Lock())
        return lock.acquire(blocking=False)

    def release(self, user_id: str) -> None:
        """Libera el candado del chat."""
        self._locks[user_id].release()


def create_app(
    chats: DirectChat, audit: ChatAudit, entries: list[KnowledgeEntry], options: WebOptions
) -> FastAPI:
    """Construye la aplicación HTTP con sus dependencias inyectadas.

    Args:
        chats: Chats directos de consola y web (crear, escribir, liberar).
        audit: Lectura de los chats de todos los canales.
        entries: Registros de conocimiento para ampliar la evidencia de la auditoría.
        options: Tamaño de página y frecuencia de actualización.

    Returns:
        Aplicación FastAPI lista para servir en loopback.
    """
    app = FastAPI(title=APP_TITLE, docs_url=None, redoc_url=None, openapi_url=None)
    entry_index = {entry.id: entry for entry in entries}
    _add_page_routes(app)
    _add_chat_routes(app, chats, audit, options)
    _add_message_routes(app, chats, audit, entry_index, options)
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


def _add_chat_routes(
    app: FastAPI, chats: DirectChat, audit: ChatAudit, options: WebOptions
) -> None:
    """Registra la configuración, la lista de chats, el chat nuevo y la liberación."""

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        """Tamaño de página, frecuencia de actualización y canales para los filtros."""
        channels = [{"id": str(c), "label": label} for c, label in CHANNEL_LABELS.items()]
        return {
            "page_size": options.page_size,
            "poll_seconds": options.poll_seconds,
            "channels": channels,
        }

    @app.get("/api/chats")
    def list_chats(
        channel: str | None = None,
        limit: int = Query(DEFAULT_CHAT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ) -> list[dict[str, Any]]:
        """Chats del más reciente al más antiguo, opcionalmente de un canal."""
        selected = parse_channel(channel)
        return [chat_to_dict(chat) for chat in audit.list_chats(selected, limit, offset)]

    @app.post("/api/chats", status_code=201)
    def new_chat() -> dict[str, Any]:
        """Nueva sesión: crea un chat web vacío."""
        return chat_to_dict(require_chat(audit, chats.start(Channel.WEB)))

    @app.get("/api/chats/{user_id}")
    def get_chat(user_id: str) -> dict[str, Any]:
        """Resumen de un chat y si se puede escribir en él."""
        return chat_to_dict(require_chat(audit, user_id))

    @app.post("/api/chats/{user_id}/release")
    def release(user_id: str) -> dict[str, Any]:
        """Libera un chat de consola que quedó marcado tras un cierre abrupto."""
        chat = require_chat(audit, user_id)
        if chat_lock(chat.channel, chat.live_session_at) is not ChatLock.LIVE_CONSOLE:
            raise HTTPException(status_code=409, detail=NOT_LIVE)
        chats.release_console(user_id)
        return chat_to_dict(require_chat(audit, user_id))


def _add_message_routes(
    app: FastAPI, chats: DirectChat, audit: ChatAudit, entries: Entries, options: WebOptions
) -> None:
    """Registra la lectura por páginas y el envío de mensajes."""
    locks = ChatLocks()

    @app.get("/api/chats/{user_id}/messages")
    def messages(
        user_id: str,
        before: int | None = Query(None, ge=1),
        after: int | None = Query(None, ge=0),
        limit: int | None = Query(None, ge=1, le=MAX_LIMIT),
    ) -> dict[str, Any]:
        """Página de mensajes: la más reciente, la anterior a `before` o lo nuevo tras `after`."""
        chat = require_chat(audit, user_id)
        size = limit or options.page_size
        page = (
            audit.messages_after(user_id, after, MAX_LIMIT)
            if after is not None
            else audit.message_page(user_id, before, size)
        )
        return page_to_dict(chat, page, audit.pending_inbound(user_id), entries)

    @app.post("/api/chats/{user_id}/messages")
    def send(user_id: str, request: SendMessageRequest) -> dict[str, Any]:
        """Procesa un mensaje en un chat de consola o web y devuelve lo nuevo del chat."""
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail=EMPTY_TEXT)
        target = require_chat(audit, user_id)
        if not locks.try_acquire(user_id):
            raise HTTPException(status_code=409, detail=CHAT_BUSY)
        try:
            turn = run_turn(chats, target, text)
        finally:
            locks.release(user_id)
        page = audit.messages_after(user_id, request.after, MAX_LIMIT)
        chat = require_chat(audit, user_id)
        return {"turn": turn_to_dict(turn, entries), **page_to_dict(chat, page, 0, entries)}


def run_turn(chats: DirectChat, chat: ChatSummary, text: str) -> TurnResult:
    """Envía el mensaje y traduce los errores del caso de uso a respuestas HTTP.

    Raises:
        HTTPException: 404 si el chat no existe, 403 si es de solo lectura o está en uso en
            una consola, 502 si falla el modelo.
    """
    try:
        return chats.send(chat.user_id, text)
    except ChatNotFoundError as error:
        raise HTTPException(status_code=404, detail=CHAT_NOT_FOUND) from error
    except ChatReadOnlyError as error:
        label = CHANNEL_LABELS[chat.channel]
        detail = LOCK_TEXTS[ChatLock(error.reason)].format(channel=label)
        raise HTTPException(status_code=403, detail=detail) from error
    except LanguageModelError as error:
        raise HTTPException(status_code=502, detail=ERROR_MODEL_MESSAGE) from error


def page_to_dict(
    chat: ChatSummary, page: ChatPage, pending: int, entries: Entries
) -> dict[str, Any]:
    """Página de mensajes con el estado actual del chat.

    Args:
        chat: Resumen del chat (puede haber cambiado, p. ej., al cerrarse la consola).
        page: Mensajes leídos.
        pending: Mensajes del canal aún en proceso.
        entries: Registros para completar la evidencia.

    Returns:
        `chat`, `messages`, `next_before` y `pending`.
    """
    return {
        "chat": chat_to_dict(chat),
        "messages": [entry_to_dict(entry, entries) for entry in page.entries],
        "next_before": page.next_before,
        "pending": pending,
    }


def require_chat(audit: ChatAudit, user_id: str) -> ChatSummary:
    """Resumen del chat.

    Raises:
        HTTPException: 404 si no existe.
    """
    chat = audit.get_chat(user_id)
    if chat is None:
        raise HTTPException(status_code=404, detail=CHAT_NOT_FOUND)
    return chat


def parse_channel(value: str | None) -> Channel | None:
    """Canal del filtro, o None para todos.

    Raises:
        HTTPException: 422 si el canal no existe.
    """
    if not value:
        return None
    try:
        return Channel(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Canal desconocido: {value}") from error
