"""Atajo para importar los hilos JSON anteriores al chat "Histórico" (una sola vez)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cardio_materno.bootstrap.import_history import main  # noqa: E402 (usa el sys.path)

if __name__ == "__main__":
    sys.exit(main())
