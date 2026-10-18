"""Importación única de los hilos JSON anteriores a un chat "Histórico" (HU-10, ADR 0016).

Los hilos de la consola y la web anteriores a la migración no tienen usuario. Se importan,
en orden de creación y cerrados, a un solo chat de canal `historico`, de solo lectura, con
sus mensajes, trazas y alertas. Volver a importar no duplica: los hilos ya importados se
omiten.
"""

from dataclasses import dataclass, replace

from cardio_materno.application.conversation_service import (
    Clock,
    IdGenerator,
    new_uuid,
    utc_now,
)
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.ports.user_directory import UserDirectory
from cardio_materno.application.ports.user_thread_store import UserThreadStore
from cardio_materno.domain.conversation import ConversationThread, ThreadStatus
from cardio_materno.domain.user import Channel, User, new_user

HISTORICAL_IDENTITY = "importacion-json"


@dataclass(frozen=True)
class ImportReport:
    """Resultado de la importación.

    Attributes:
        user_id: Chat histórico (None si no había nada que importar).
        imported: Hilos importados en esta ejecución.
        skipped: Hilos que ya estaban importados.
        messages: Mensajes importados en esta ejecución.
    """

    user_id: str | None
    imported: int
    skipped: int
    messages: int


def import_history(
    source: ThreadRepository,
    users: UserDirectory,
    threads: UserThreadStore,
    clock: Clock = utc_now,
    new_id: IdGenerator = new_uuid,
) -> ImportReport:
    """Copia los hilos de `source` al chat histórico.

    Args:
        source: Repositorio de los hilos anteriores (archivos JSON).
        users: Directorio de usuarios.
        threads: Hilos por usuario (destino).
        clock: Reloj, para crear el chat histórico la primera vez.
        new_id: Generador del identificador del chat histórico.

    Returns:
        Cuántos hilos y mensajes se importaron y cuántos hilos ya estaban.
    """
    pending = sorted(source.list_threads(), key=lambda thread: thread.created_at)
    if not pending:
        return ImportReport(None, 0, 0, 0)
    user = _historical_user(users, clock, new_id)
    target = threads.scoped(user.id)
    copied = [thread for thread in pending if target.get_thread(thread.id) is None]
    messages = sum(_copy_thread(source, target, thread) for thread in copied)
    _date_chat(users, user, pending)
    return ImportReport(user.id, len(copied), len(pending) - len(copied), messages)


def _historical_user(users: UserDirectory, clock: Clock, new_id: IdGenerator) -> User:
    """Chat histórico existente, o uno nuevo."""
    user = users.find(Channel.HISTORICAL, HISTORICAL_IDENTITY)
    if user is None:
        user = new_user(new_id(), clock())
        users.register(user, Channel.HISTORICAL, HISTORICAL_IDENTITY)
    return user


def _copy_thread(
    source: ThreadRepository, target: ThreadRepository, thread: ConversationThread
) -> int:
    """Copia un hilo cerrado con sus mensajes y alertas; devuelve cuántos mensajes copió."""
    target.save_thread(replace(thread, status=ThreadStatus.CLOSED))
    messages = source.all_messages(thread.id)
    for message in messages:
        target.append_message(message)
    for alert in source.all_alerts(thread.id):
        target.append_alert(thread.id, alert)
    return len(messages)


def _date_chat(users: UserDirectory, user: User, threads: list[ConversationThread]) -> None:
    """Fechas del chat histórico: del primer hilo a la última actualización."""
    first = min(thread.created_at for thread in threads)
    last = max(thread.updated_at for thread in threads)
    users.save(replace(user, created_at=min(first, user.created_at), last_seen_at=last))
