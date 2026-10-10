"""Atajo para construir el índice de la base de conocimiento: `python run_build_kb_index.py`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cardio_materno.bootstrap.build_kb_index import main  # noqa: E402 (usa el sys.path)

if __name__ == "__main__":
    sys.exit(main())
