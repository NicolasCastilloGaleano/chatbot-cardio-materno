"""Importa una vez los hilos JSON anteriores al chat "Histórico" de SQLite (HU-10, ADR 0016)."""

import os
import sys

from cardio_materno.adapters.outbound.persistence.json_file_thread_repository import (
    JsonFileThreadRepository,
)
from cardio_materno.adapters.outbound.persistence.sqlite_database import (
    DatabaseVersionError,
    SqliteDatabase,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_directory import (
    SqliteUserDirectory,
)
from cardio_materno.adapters.outbound.persistence.sqlite_user_thread_store import (
    SqliteUserThreadStore,
)
from cardio_materno.application.import_history import import_history
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import (
    ENV_FILE,
    EXIT_ERROR,
    EXIT_OK,
    PROJECT_ROOT,
    use_utf8_streams,
)
from cardio_materno.bootstrap.settings import (
    ConfigurationError,
    load_conversation_settings,
    load_persistence_settings,
)


def main() -> int:
    """Lee `THREADS_DIR` y copia sus hilos a `DATABASE_PATH`.

    Returns:
        Código de salida del proceso.
    """
    use_utf8_streams()
    try:
        load_env_file(ENV_FILE)
        threads_dir = load_conversation_settings(os.environ, PROJECT_ROOT).threads_dir
        database = SqliteDatabase(load_persistence_settings(os.environ, PROJECT_ROOT).database_path)
    except (ConfigurationError, DatabaseVersionError) as error:
        print(f"No se pudo importar el histórico: {error}", file=sys.stderr)
        return EXIT_ERROR
    try:
        report = import_history(
            JsonFileThreadRepository(threads_dir),
            SqliteUserDirectory(database),
            SqliteUserThreadStore(database),
        )
    finally:
        database.close()
    if report.user_id is None:
        print(f"No hay hilos JSON para importar en {threads_dir}.")
        return EXIT_OK
    print(
        f"Histórico: {report.imported} hilos importados ({report.messages} mensajes); "
        f"{report.skipped} ya estaban. Chat {report.user_id[:8]}."
    )
    return EXIT_OK
