"""Medición de la duración de cada etapa del turno (para la depuración y la traza)."""

import time
from collections.abc import Callable

from cardio_materno.domain.trace import StageTiming

Timer = Callable[[], float]
SECONDS_DECIMALS = 2


class StageTimer:
    """Acumula la duración de las etapas medidas, en orden."""

    def __init__(self, timer: Timer = time.perf_counter) -> None:
        """Crea el medidor.

        Args:
            timer: Reloj monotónico en segundos (se reemplaza en las pruebas).
        """
        self._timer = timer
        self._timings: list[StageTiming] = []

    def measure[T](self, stage: str, action: Callable[[], T]) -> T:
        """Ejecuta `action`, registra su duración (aunque falle) y devuelve su resultado."""
        start = self._timer()
        try:
            return action()
        finally:
            elapsed = round(self._timer() - start, SECONDS_DECIMALS)
            self._timings.append(StageTiming(stage, elapsed))

    @property
    def timings(self) -> tuple[StageTiming, ...]:
        """Duraciones registradas hasta ahora."""
        return tuple(self._timings)
