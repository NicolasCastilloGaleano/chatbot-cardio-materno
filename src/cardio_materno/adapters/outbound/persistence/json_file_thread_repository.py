"""Repositorio de hilos en archivos JSON: un archivo por hilo (ADR 0006).

Formato de `<directorio>/<thread_id>.json`:
    {"id", "domain", "summary", "status", "created_at", "updated_at",
     "messages": [{"thread_id", "role", "content", "created_at"}],
     "alerts": [{"rule_ids", "severity", "origin", "created_at"}]}

Es una solución para el prototipo de un solo proceso (consola). Para Telegram,
con varios usuarios a la vez, se migrará a una base de datos cambiando solo este adaptador.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import (
    ChatMessage,
    ConversationThread,
    Domain,
    Role,
    ThreadStatus,
)

FILE_SUFFIX = ".json"
TMP_SUFFIX = ".tmp"
MESSAGES_KEY = "messages"
ALERTS_KEY = "alerts"


class JsonFileThreadRepository:
    """Implementación de ThreadRepository sobre archivos JSON legibles."""

    def __init__(self, directory: Path) -> None:
        """Crea el repositorio y su directorio si no existe.

        Args:
            directory: Carpeta donde se guardan los archivos de los hilos.
        """
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def save_thread(self, thread: ConversationThread) -> None:
        """Crea o actualiza el hilo conservando sus mensajes y alertas."""
        existing = self._read(thread.id) or {}
        history = {
            MESSAGES_KEY: existing.get(MESSAGES_KEY, []),
            ALERTS_KEY: existing.get(ALERTS_KEY, []),
        }
        self._write(thread.id, {**thread_to_dict(thread), **history})

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        """Devuelve el hilo o None si no existe su archivo."""
        data = self._read(thread_id)
        return thread_from_dict(data) if data else None

    def append_message(self, message: ChatMessage) -> None:
        """Agrega el mensaje al archivo de su hilo.

        Raises:
            KeyError: Si el mensaje no tiene hilo o el hilo no existe.
        """
        self._append(message.thread_id, MESSAGES_KEY, message_to_dict(message))

    def append_alert(self, thread_id: str, alert: Alert) -> None:
        """Agrega la alerta al archivo del hilo.

        Raises:
            KeyError: Si el hilo no existe.
        """
        self._append(thread_id, ALERTS_KEY, alert_to_dict(alert))

    def recent_messages(self, thread_id: str, limit: int) -> list[ChatMessage]:
        """Devuelve los últimos `limit` mensajes del hilo (vacío si no existe)."""
        data = self._read(thread_id)
        if data is None or limit <= 0:
            return []
        return [message_from_dict(item) for item in data[MESSAGES_KEY][-limit:]]

    def _append(self, thread_id: str | None, key: str, item: dict[str, Any]) -> None:
        """Agrega un elemento a una lista del archivo del hilo."""
        data = self._read(thread_id) if thread_id else None
        if data is None:
            raise KeyError(f"No existe el hilo {thread_id!r}")
        data.setdefault(key, []).append(item)
        self._write(data["id"], data)

    def _path(self, thread_id: str) -> Path:
        """Ruta del archivo del hilo."""
        return self._directory / f"{thread_id}{FILE_SUFFIX}"

    def _read(self, thread_id: str) -> dict[str, Any] | None:
        """Lee el archivo del hilo, o None si no existe."""
        path = self._path(thread_id)
        if not path.is_file():
            return None
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return data

    def _write(self, thread_id: str, data: dict[str, Any]) -> None:
        """Escribe el archivo de forma atómica (archivo temporal + reemplazo)."""
        path = self._path(thread_id)
        tmp_path = path.with_suffix(TMP_SUFFIX)
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)


def thread_to_dict(thread: ConversationThread) -> dict[str, Any]:
    """Serializa un hilo (sin mensajes)."""
    return {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def thread_from_dict(data: dict[str, Any]) -> ConversationThread:
    """Reconstruye un hilo desde su forma serializada."""
    return ConversationThread(
        id=data["id"],
        domain=Domain(data["domain"]),
        summary=data["summary"],
        status=ThreadStatus(data["status"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def message_to_dict(message: ChatMessage) -> dict[str, Any]:
    """Serializa un mensaje con el identificador de su hilo."""
    created_at = message.created_at.isoformat() if message.created_at else None
    return {
        "thread_id": message.thread_id,
        "role": str(message.role),
        "content": message.content,
        "created_at": created_at,
    }


def message_from_dict(data: dict[str, Any]) -> ChatMessage:
    """Reconstruye un mensaje desde su forma serializada."""
    created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
    return ChatMessage(Role(data["role"]), data["content"], data.get("thread_id"), created_at)


def alert_to_dict(alert: Alert) -> dict[str, Any]:
    """Serializa una alerta."""
    return {
        "rule_ids": list(alert.rule_ids),
        "severity": str(alert.severity),
        "origin": str(alert.origin),
        "created_at": alert.created_at.isoformat(),
    }
