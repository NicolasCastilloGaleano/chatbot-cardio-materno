"""Herramienta: construye el índice vectorial de la base de conocimiento (ADR 0008).

Uso (en el PC con Ollama y el modelo de embeddings):
    python run_build_kb_index.py
"""

import os
import sys
import time

from cardio_materno.adapters.outbound.rag.kb_index_builder import build_index
from cardio_materno.adapters.outbound.rag.knowledge_files import KnowledgeBaseError, load_entries
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.bootstrap.env_file import load_env_file
from cardio_materno.bootstrap.main import ENV_FILE, PROJECT_ROOT
from cardio_materno.bootstrap.rag_setup import build_embedder
from cardio_materno.bootstrap.settings import (
    ConfigurationError,
    load_ollama_settings,
    load_rag_settings,
)

EXIT_OK = 0
EXIT_ERROR = 1


def main() -> int:
    """Lee la base, calcula los embeddings y guarda el índice.

    Returns:
        Código de salida (0 si el índice quedó construido).
    """
    try:
        load_env_file(ENV_FILE)
        settings = load_rag_settings(os.environ, PROJECT_ROOT)
        entries = load_entries(settings.entries_file)
        embedder = build_embedder(settings, load_ollama_settings(os.environ).base_url)
        embedder.verify_ready()
        print(f"Calculando embeddings de {len(entries)} registros con '{embedder.model}'…")
        start = time.perf_counter()
        manifest = build_index(
            entries, settings.entries_file, embedder, settings.index_dir, _progress
        )
    except (ConfigurationError, KnowledgeBaseError, LanguageModelError) as error:
        print(f"\nNo se pudo construir el índice: {error}", file=sys.stderr)
        return EXIT_ERROR
    elapsed = time.perf_counter() - start
    size = f"{manifest.count} × {manifest.dimensions}"
    print(f"\nÍndice listo en {settings.index_dir} ({size}, {elapsed:.0f} s)")
    return EXIT_OK


def _progress(done: int, total: int) -> None:
    """Muestra el avance en la misma línea."""
    print(f"\r  {done}/{total}", end="", flush=True)
