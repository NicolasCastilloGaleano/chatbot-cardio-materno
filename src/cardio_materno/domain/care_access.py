"""Datos de acceso a la atención: barreras, afiliación y cascada del colesterol (HU-18, ADR 0023).

Reglas deterministas sobre los códigos cerrados de `knowledge/care_access.json`. Estos datos
**nunca** intervienen en la detección de alarmas, en el alcance, en la evidencia ni en la ruta
de atención: solo permiten acompañar una respuesta con un aviso de acceso o con una pregunta.

Solo cuenta lo que la persona declaró. Un paso de la cascada que nadie mencionó queda
**desconocido**: tomar tratamiento no prueba que el colesterol esté alto ni que se haya
medido. Dos declaraciones opuestas sobre el mismo paso, o una que choca con "nunca me lo han
medido", dejan el paso como **contradictorio** y no producen ningún aviso.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from cardio_materno.domain.alarms import normalize_text

GAP_NOT_MEASURED = "CASCADA_SIN_MEDICION"
GAP_NOT_TREATED = "CASCADA_SIN_TRATAMIENTO"
GAP_NOT_CONTROLLED = "CASCADA_SIN_CONTROL"
APPROVED = "aprobado"


class FactGroup(StrEnum):
    """Tipo de dato de acceso."""

    CASCADE = "cascada"
    INSURANCE = "afiliacion"
    BARRIER = "barrera"


class CascadeStep(StrEnum):
    """Pasos de la cascada del colesterol, en orden."""

    MEASURED = "medicion"
    DIAGNOSED = "diagnostico"
    TREATED = "tratamiento"
    CONTROLLED = "control"


CASCADE_ORDER: tuple[CascadeStep, ...] = tuple(CascadeStep)


class StepState(StrEnum):
    """Lo que se sabe de un paso de la cascada, solo por lo que la persona declaró."""

    YES = "si"
    NO = "no"
    UNKNOWN = "desconocido"
    CONTRADICTORY = "contradictorio"


class NoticeRoute(StrEnum):
    """Variante del aviso según la ruta que **ya** decidió el turno."""

    CONSULTATION = "consulta"
    EMERGENCY = "urgencias"


class NoticeKind(StrEnum):
    """Naturaleza de un aviso: no es evidencia de la base de conocimiento."""

    ADMINISTRATIVE = "administrativo"
    CLINICAL = "clinico"


CascadeState = Mapping[CascadeStep, StepState]


@dataclass(frozen=True)
class CareFact:
    """Dato de acceso que la persona puede declarar (un código del catálogo).

    Attributes:
        code: Código estable (p. ej., SIN_AFILIACION).
        group: Cascada, afiliación o barrera.
        label: Significado del código, para el prompt y el informe.
        examples: Expresiones coloquiales, para el prompt.
        patterns: Expresiones regulares sobre texto normalizado (solo barreras).
        step: Paso de la cascada (solo cascada).
        value: Valor declarado del paso: True (sí) o False (no) (solo cascada).
        barrier: Clase de barrera: económica, geográfica, administrativa, medicamentos o cuidado.
    """

    code: str
    group: FactGroup
    label: str
    examples: tuple[str, ...] = ()
    patterns: tuple[re.Pattern[str], ...] = ()
    step: CascadeStep | None = None
    value: bool | None = None
    barrier: str = ""

    def matches(self, normalized_text: str) -> bool:
        """True si algún patrón aparece en el texto normalizado."""
        return any(pattern.search(normalized_text) for pattern in self.patterns)


@dataclass(frozen=True)
class Notice:
    """Aviso fijo de acceso, con su procedencia y su estado de aprobación.

    Attributes:
        code: Código del aviso (el de la barrera, o el de la brecha de la cascada).
        kind: Administrativo o jurídico, o clínico. Nunca es evidencia de la base.
        status: `aprobado` o `pendiente`. Solo un aviso aprobado se muestra a una persona.
        texts: Texto por variante de ruta.
        basis: Normas o criterios en que se apoya, tal como los registró el equipo.
        source_ids: Fuentes del catálogo de la base (`fuentes-base-conocimiento.md`).
    """

    code: str
    kind: NoticeKind
    status: str
    texts: Mapping[NoticeRoute, str]
    basis: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @property
    def approved(self) -> bool:
        """True si el equipo aprobó el aviso."""
        return self.status == APPROVED


@dataclass(frozen=True)
class CascadeQuestion:
    """Pregunta fija sobre un paso de la cascada.

    Attributes:
        step: Paso por el que pregunta.
        text: Texto de la pregunta.
        status: `aprobado` o `pendiente`.
    """

    step: CascadeStep
    text: str
    status: str

    @property
    def approved(self) -> bool:
        """True si el equipo aprobó la pregunta."""
        return self.status == APPROVED


@dataclass(frozen=True)
class CareAccessCatalog:
    """Catálogo de datos de acceso, avisos y preguntas.

    Attributes:
        version: Versión del contenido.
        facts: Datos que la persona puede declarar, en el orden del catálogo.
        notices: Avisos por código.
        questions: Pregunta de cada paso de la cascada que tiene una.
        topic_patterns: Patrones que indican que un texto habla del colesterol.
        research_text: Texto de la autorización opcional para informes agregados.
    """

    version: str
    facts: tuple[CareFact, ...]
    notices: Mapping[str, Notice]
    questions: Mapping[CascadeStep, CascadeQuestion]
    topic_patterns: tuple[re.Pattern[str], ...] = ()
    research_text: str = ""

    @property
    def codes(self) -> tuple[str, ...]:
        """Códigos del catálogo, en orden."""
        return tuple(fact.code for fact in self.facts)

    def fact(self, code: str) -> CareFact | None:
        """Dato de un código, o None si no está en el catálogo."""
        return next((fact for fact in self.facts if fact.code == code), None)


def detect_barriers(texts: Iterable[str], catalog: CareAccessCatalog) -> tuple[str, ...]:
    """Códigos de barreras cuyos patrones aparecen en los textos de la persona."""
    normalized = [normalize_text(text) for text in texts if text.strip()]
    return tuple(
        fact.code
        for fact in catalog.facts
        if fact.patterns and any(fact.matches(text) for text in normalized)
    )


def mentions_cholesterol(texts: Iterable[str], catalog: CareAccessCatalog) -> bool:
    """True si algún texto de la persona habla del colesterol."""
    normalized = [normalize_text(text) for text in texts]
    return any(p.search(text) for p in catalog.topic_patterns for text in normalized)


def ordered_facts(codes: Iterable[str], catalog: CareAccessCatalog) -> tuple[str, ...]:
    """Códigos conocidos, sin repetir y en el orden del catálogo."""
    known = set(codes)
    return tuple(code for code in catalog.codes if code in known)


def cascade_state(codes: Iterable[str], catalog: CareAccessCatalog) -> dict[CascadeStep, StepState]:
    """Estado declarado de cada paso de la cascada, sin deducir ninguno.

    Args:
        codes: Códigos que la persona declaró.
        catalog: Catálogo.

    Returns:
        Por paso: sí, no, desconocido (nadie lo mencionó) o contradictorio (se declaró sí y
        no, o un paso posterior choca con "nunca me lo han medido").
    """
    declared: dict[CascadeStep, set[bool]] = {step: set() for step in CASCADE_ORDER}
    known = set(codes)
    for fact in catalog.facts:
        if fact.step is not None and fact.value is not None and fact.code in known:
            declared[fact.step].add(fact.value)
    state = {step: _declared_state(values) for step, values in declared.items()}
    return _with_measurement_conflicts(state)


def _declared_state(values: set[bool]) -> StepState:
    """Estado de un paso según los valores declarados."""
    if not values:
        return StepState.UNKNOWN
    if len(values) > 1:
        return StepState.CONTRADICTORY
    return StepState.YES if True in values else StepState.NO


def _with_measurement_conflicts(
    state: dict[CascadeStep, StepState],
) -> dict[CascadeStep, StepState]:
    """Marca el choque entre «nunca me lo han medido» y un resultado o un control hecho."""
    later_claims = (
        state[CascadeStep.DIAGNOSED] in (StepState.YES, StepState.NO)
        or state[CascadeStep.CONTROLLED] is StepState.YES
    )
    if state[CascadeStep.MEASURED] is StepState.NO and later_claims:
        return {**state, CascadeStep.MEASURED: StepState.CONTRADICTORY}
    return state


def contradictions(state: CascadeState) -> tuple[str, ...]:
    """Pasos de la cascada con declaraciones contradictorias."""
    return tuple(str(step) for step in CASCADE_ORDER if state[step] is StepState.CONTRADICTORY)


def cascade_gap(state: CascadeState) -> str | None:
    """Aviso de la brecha que la persona **declaró**, o None.

    Cada brecha exige las declaraciones exactas que la describen: nada se deduce de otro
    paso, y un paso contradictorio no produce aviso.
    """
    if state[CascadeStep.MEASURED] is StepState.NO:
        return GAP_NOT_MEASURED
    if state[CascadeStep.DIAGNOSED] is StepState.YES and state[CascadeStep.TREATED] is StepState.NO:
        return GAP_NOT_TREATED
    treated = state[CascadeStep.TREATED] is StepState.YES
    if treated and state[CascadeStep.CONTROLLED] is StepState.NO:
        return GAP_NOT_CONTROLLED
    return None


def follow_up_step(state: CascadeState) -> CascadeStep | None:
    """Paso por el que tendría sentido preguntar: el que sigue a un "sí" declarado.

    No es una secuencia: sin un "sí" declarado no hay nada que preguntar, y con un paso
    contradictorio tampoco.
    """
    if StepState.CONTRADICTORY in state.values():
        return None
    for previous, step in zip(CASCADE_ORDER, CASCADE_ORDER[1:], strict=False):
        if state[previous] is StepState.YES and state[step] is StepState.UNKNOWN:
            return step
    return None


@dataclass(frozen=True)
class PublicEmergencyInfo:
    """Indicaciones generales para buscar atención urgente, visibles sin consentimiento.

    Attributes:
        version: Versión del contenido.
        status: Estado de validación del archivo.
        title: Título del aviso.
        phone: Línea de emergencias.
        lines: Indicaciones generales, sin nada que dependa de lo que cuente la persona.
        disclaimer: Límite del servicio.
    """

    version: str
    status: str
    title: str
    phone: str
    lines: tuple[str, ...]
    disclaimer: str
