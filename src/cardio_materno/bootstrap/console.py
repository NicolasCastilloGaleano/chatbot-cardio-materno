"""Arranque de la consola: cada ejecución crea su propio chat en SQLite (HU-10, ADR 0016).

Mientras la consola está abierta, su chat queda bloqueado para la web. Al salir se cierra
el hilo abierto y el chat se libera para continuarlo en la interfaz web.
"""

import os
import sys
from datetime import timedelta

from cardio_materno.adapters.inbound.console.console_chat import ConsoleChat
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.application.direct_chat import DirectChat, open_console_session
from cardio_materno.bootstrap.conversation_factory import build_user_conversations
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    STARTUP_ERRORS,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    PersistenceSettings,
    load_conversation_settings,
    load_persistence_settings,
)

CHAT_LABEL_CHARS = 8
START_TEXT = "Chat de consola {label}: al salir podrás continuarlo en la interfaz web."
END_TEXT = "Chat {label} guardado. Continúalo en la interfaz web (python run_web.py)."


def build_direct_chat(database: SqliteDatabase, persistence: PersistenceSettings) -> DirectChat:
    """Chat directo con el agente y la persistencia por usuario.

    Args:
        database: Base SQLite abierta.
        persistence: Ubicación de la base e inactividad.

    Returns:
        El caso de uso de chats de consola y web.
    """
    idle = timedelta(hours=persistence.idle_timeout_hours)
    return DirectChat(SqliteUserDirectory(database), build_user_conversations(database, idle))


def main() -> int:
    """Configura y ejecuta el chat por consola.

    Returns:
        Código de salida del proceso (0 si terminó bien, 1 si hubo un error de arranque).
    """
    use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        show_debug = load_conversation_settings(os.environ, PROJECT_ROOT).show_thread_debug
        persistence = load_persistence_settings(os.environ, PROJECT_ROOT)
        database = SqliteDatabase(persistence.database_path)
        chat = build_direct_chat(database, persistence)
    except (*STARTUP_ERRORS, DatabaseVersionError) as error:
        print(f"No se pudo iniciar el asistente: {error}", file=sys.stderr)
        return EXIT_ERROR
    session = open_console_session(chat)
    label = session.user_id[:CHAT_LABEL_CHARS]
    print(START_TEXT.format(label=label))
    try:
        ConsoleChat(session, show_debug).run()
    finally:
        database.close()
    print(END_TEXT.format(label=label))
    return EXIT_OK
