"""Informe agregado de acceso a la atención (HU-18, ADR 0023).

Cuenta **personas**, no hilos: quien abrió tres conversaciones en un mes cuenta una vez, con
todo lo que declaró ese mes. Solo entran personas que autorizaron este uso, y solo meses ya
cerrados.

Controles que **reducen** el riesgo de reidentificación (no garantizan anonimato):

- un mes con menos de `min_population` personas no se publica;
- todos los indicadores del catálogo salen siempre, y los conteos de 0 a `min_cell - 1` se
  publican como "<N": que una fila exista no dice si alguien declaró ese dato;
- un conteo que deja fuera a menos de `min_cell` personas del mes se publica como
  "suprimido": si casi todas comparten un dato, el conteo lo revelaría de cada una;
- los demás se redondean al múltiplo de `rounding_base` más cercano.

Lo que estos controles **no** cubren: quien conoce a todas las personas de un mes pequeño
aprende algo del grupo; un conteo en el borde del redondeo cambia 5 cuando una persona
entra o sale, así que dos exportaciones del mismo mes (antes y después de que alguien
retire su autorización) pueden describir a esa persona. Por eso cada mes se publica una
sola vez (ver `scripts/export_care_access.py`).

El informe describe a quienes usaron el asistente y autorizaron el uso de sus datos. **No es
una muestra representativa** de un municipio ni del departamento, y los datos son lo que la
persona dijo o lo que el modelo interpretó de su mensaje, no un registro clínico.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from cardio_materno.domain.care_access import (
    GAP_NOT_CONTROLLED,
    GAP_NOT_MEASURED,
    GAP_NOT_TREATED,
    CareAccessCatalog,
    CascadeStep,
    FactGroup,
    StepState,
    cascade_gap,
    cascade_state,
    contradictions,
)

GROUP_TOTAL = "total"
PEOPLE_INDICATOR = "personas con datos de acceso declarados"
GROUP_CASCADE = "cascada del colesterol (declarada)"
CONTROLLED_STAGE = "declara tratamiento y control"
CONTRADICTORY_STAGE = "declaraciones contradictorias"
GAP_LABELS = {
    GAP_NOT_MEASURED: "declara que nunca se lo han medido",
    GAP_NOT_TREATED: "declara colesterol alto sin tratamiento",
    GAP_NOT_CONTROLLED: "declara tratamiento sin control posterior",
}
SUPPRESSED = "suprimido"
CAVEAT = (
    "No es una estimación representativa de Caldas ni de ningún municipio: describe solo a "
    "quienes usaron el asistente y autorizaron este uso. Son declaraciones de las personas "
    "o interpretaciones del modelo, no registros clínicos. Conteos redondeados."
)


@dataclass(frozen=True)
class ReportPolicy:
    """Umbrales de publicación del informe.

    Attributes:
        min_cell: Conteo mínimo que se publica con su valor (los menores salen como "<N").
        min_population: Personas mínimas en un mes para publicarlo.
        rounding_base: Los conteos publicados se redondean a un múltiplo de este número.
    """

    min_cell: int = 5
    min_population: int = 10
    rounding_base: int = 5


@dataclass(frozen=True)
class Observation:
    """Datos de acceso de un hilo de una persona que autorizó el informe.

    Attributes:
        person: Identificador interno de la persona (nunca se publica).
        period: Mes del hilo ("AAAA-MM", UTC).
        facts: Códigos registrados en el hilo.
    """

    person: str
    period: str
    facts: tuple[str, ...]


@dataclass(frozen=True)
class ReportRow:
    """Fila del informe ya protegida.

    Attributes:
        period: Mes ("AAAA-MM").
        group: Total, cascada, afiliación o barrera.
        indicator: Qué se cuenta.
        published: Conteo publicado: "<N", un múltiplo redondeado, "suprimido" u "omitido".
    """

    period: str
    group: str
    indicator: str
    published: str


def people_by_period(observations: Iterable[Observation]) -> dict[str, dict[str, set[str]]]:
    """Agrupa los códigos por mes y por persona: varios hilos de alguien cuentan una vez."""
    periods: dict[str, dict[str, set[str]]] = {}
    for observation in observations:
        if observation.facts:
            people = periods.setdefault(observation.period, {})
            people.setdefault(observation.person, set()).update(observation.facts)
    return periods


def build_report(
    observations: Iterable[Observation], catalog: CareAccessCatalog, policy: ReportPolicy
) -> list[ReportRow]:
    """Filas publicables del informe, por mes.

    Args:
        observations: Datos de acceso de personas que autorizaron el informe, de meses cerrados.
        catalog: Catálogo de acceso.
        policy: Umbrales de publicación.

    Returns:
        Por mes, el total y un conteo por indicador; un mes con pocas personas sale omitido.
    """
    rows: list[ReportRow] = []
    for period, people in sorted(people_by_period(observations).items()):
        if len(people) < policy.min_population:
            omitted = f"omitido (menos de {policy.min_population} personas)"
            rows.append(ReportRow(period, GROUP_TOTAL, PEOPLE_INDICATOR, omitted))
            continue
        rows.extend(period_rows(period, list(people.values()), catalog, policy))
    return rows


def period_rows(
    period: str, people: Sequence[set[str]], catalog: CareAccessCatalog, policy: ReportPolicy
) -> list[ReportRow]:
    """Total del mes y un conteo protegido por cada indicador del catálogo, haya o no casos."""
    counts: Counter[tuple[str, str]] = Counter()
    for facts in people:
        counts.update(person_indicators(facts, catalog))
    population = len(people)
    total = ReportRow(period, GROUP_TOTAL, PEOPLE_INDICATOR, protect(population, policy))
    rest = [
        ReportRow(period, group, name, protect_cell(counts[(group, name)], population, policy))
        for group, name in all_indicators(catalog)
    ]
    return [total, *rest]


def all_indicators(catalog: CareAccessCatalog) -> list[tuple[str, str]]:
    """Todos los indicadores que el informe puede traer, en orden estable."""
    declared = {
        (str(fact.group), fact.label)
        for fact in catalog.facts
        if fact.group is not FactGroup.CASCADE
    }
    stages = (*GAP_LABELS.values(), CONTROLLED_STAGE, CONTRADICTORY_STAGE)
    return sorted(declared | {(GROUP_CASCADE, stage) for stage in stages})


def person_indicators(facts: set[str], catalog: CareAccessCatalog) -> set[tuple[str, str]]:
    """Indicadores de una persona: afiliación y barreras declaradas, y su paso de la cascada."""
    found = {
        (str(fact.group), fact.label)
        for fact in catalog.facts
        if fact.code in facts and fact.group is not FactGroup.CASCADE
    }
    stage = cascade_stage(facts, catalog)
    if stage:
        found.add((GROUP_CASCADE, stage))
    return found


def cascade_stage(facts: set[str], catalog: CareAccessCatalog) -> str:
    """Paso de la cascada que la persona declaró ("" si no declaró lo suficiente)."""
    state = cascade_state(facts, catalog)
    if contradictions(state):
        return CONTRADICTORY_STAGE
    gap = cascade_gap(state)
    if gap is not None:
        return GAP_LABELS[gap]
    treated = state[CascadeStep.TREATED] is StepState.YES
    if treated and state[CascadeStep.CONTROLLED] is StepState.YES:
        return CONTROLLED_STAGE
    return ""


def protect_cell(count: int, population: int, policy: ReportPolicy) -> str:
    """Conteo publicable de un indicador dentro de un mes de `population` personas.

    Se suprime si deja fuera a menos de `min_cell` personas: saber que casi todas
    comparten un dato lo revela de cada una, aunque el conteo sea grande.
    """
    if count >= policy.min_cell and population - count < policy.min_cell:
        return SUPPRESSED
    return protect(count, policy)


def protect(count: int, policy: ReportPolicy) -> str:
    """Conteo publicable: "<N" si es pequeño (incluido el cero), redondeado si no."""
    if count < policy.min_cell:
        return f"<{policy.min_cell}"
    base = policy.rounding_base
    return str(base * ((count + base // 2) // base))
