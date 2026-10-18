"""Atajo para iniciar el chat por consola sin instalar el paquete: `python run_console.py`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cardio_materno.bootstrap.console import main  # noqa: E402 (requiere el sys.path anterior)

if __name__ == "__main__":
    sys.exit(main())
