"""Permite ejecutar `python -m cardio_materno` (con `src` en el PYTHONPATH)."""

import sys

from cardio_materno.bootstrap.main import main

sys.exit(main())
