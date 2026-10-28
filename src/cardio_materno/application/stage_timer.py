"""Medición de la duración de cada etapa del turno (para la depuración y la traza)."""

import time
from collections.abc import Callable
from dataclasses import replace

from cardio_materno.application.errors import LanguageModelError
from cardio_materno.domain.trace import ModelUsage, StageTiming

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
        self._usages: list[ModelUsage] = []

    def measure[T](self, stage: str, action: Callable[[], T]) -> T:
        """Ejecuta `action`, registra su duración (aunque falle) y devuelve su resultado.

        Si el modelo falla, la excepción queda marcada con la etapa, para registrar la causa.
        """
        start = self._timer()
        try:
            return action()
        except LanguageModelError as error:
            error.stage = error.stage or stage
            raise
        finally:
            elapsed = round(self._timer() - start, SECONDS_DECIMALS)
            self._timings.append(StageTiming(stage, elapsed))

    def record_usage(self, stage: str, usage: ModelUsage | None) -> None:
        """Registra cómo se repartió el tiempo de la llamada al modelo de una etapa."""
        if usage is not None:
            self._usages.append(replace(usage, stage=stage))

    @property
    def timings(self) -> tuple[StageTiming, ...]:
        """Duraciones registradas hasta ahora."""
        return tuple(self._timings)

    @property
    def usages(self) -> tuple[ModelUsage, ...]:
        """Uso del modelo registrado por etapa."""
        return tuple(self._usages)
