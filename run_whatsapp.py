"""Atajo para iniciar el canal de WhatsApp (webhook + cola) sin instalar el paquete."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from cardio_materno.bootstrap.whatsapp import main  # noqa: E402 (requiere el sys.path anterior)

if __name__ == "__main__":
    sys.exit(main())
