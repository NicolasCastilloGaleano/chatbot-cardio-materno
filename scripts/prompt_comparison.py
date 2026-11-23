"""Lógica de la comparación entre el prompt de análisis v8 y el v9 (ADR 0023).

No llama a ningún modelo: arma los casos, califica cada observación y resume. Así se prueba
sin Ollama (`tests/unit/test_prompt_comparison.py`) y `compare_analysis_prompts.py` solo
pone el modelo real.

Qué se mide y cómo se lee:

- **Contra lo esperado** (por categoría y variante): alarma detectada, falsa alarma,
  alcance, continuidad del hilo, pregunta de información, datos de acceso y recuperación.
- **Acuerdo v8~v9** por campo, junto al **acuerdo de cada variante consigo misma** entre
  repeticiones. El modelo no es determinista: v9 solo es distinguible de v8 en un campo si
  su desacuerdo con v8 supera el desacuerdo de v8 consigo mismo.
- **Casos discordantes de alarma** y una prueba de signos exacta. Con pocos casos, no
  encontrar diferencia **no** demuestra equivalencia.

Los casos son sintéticos y ninguno define contenido clínico: la regla esperada de cada
síntoma es la que ya le asignan las baterías existentes.
"""

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

V8, V9 = "v8", "v9"
VARIANTS = (V8, V9)
ALL = "todas"
CAT_ALARM, CAT_ALARM_BARRIER = "alarma coloquial", "alarma + barrera"
CAT_CALM, CAT_CALM_BARRIER = "sin alarma", "sin alarma + barrera"
CAT_SCOPE, CAT_SCOPE_BARRIER = "alcance", "alcance + barrera"
CAT_SEARCH, CAT_SEARCH_BARRIER = "búsqueda", "búsqueda + barrera"
SCOPE_GROUPS = ("en_alcance", "fuera_de_alcance", "conversacional")
IN_SCOPE = "en_alcance"
ROLES = {"user", "assistant"}
# Criterios, en el orden del informe.
ALARM, ALARM_MODEL, NO_FALSE_ALARM = "alarma detectada", "alarma por el modelo", "sin falsa alarma"
SCOPE, THREAD, INFORMATION = "alcance", "hilo", "pregunta de información"
FACTS, NO_FACTS = "dato de acceso marcado", "sin dato atribuido"
RETRIEVAL, EVIDENCE = "categoría recuperada", "evidencia suficiente"
CRITERIA = (
    ALARM, ALARM_MODEL, NO_FALSE_ALARM, SCOPE, THREAD,
    INFORMATION, FACTS, NO_FACTS, RETRIEVAL, EVIDENCE,
)  # fmt: skip
EXACT_FIELDS = (
    "scope", "domain", "thread_action", "rules_agent", "signs",
    "asks_information", "wants_guidance", "search_query", "retrieved",
)  # fmt: skip
SET_FIELDS = {"rules_agent", "signs", "retrieved"}
P50, P90 = 0.5, 0.9


@dataclass(frozen=True)
class Case:
    """Un mensaje de evaluación y lo que se espera de su análisis.

    Attributes:
        id: Identificador estable del caso.
        category: Batería a la que pertenece.
        message: Mensaje sintético de la persona.
        history: Mensajes anteriores del hilo, como (rol, texto).
        thread_summary: Resumen del hilo abierto ("" si no hay hilo).
        rule: Regla de alarma que debe activarse ("" si no se espera ninguna en particular).
        no_alarm: True si no debe activarse ninguna regla.
        scope: Alcance esperado ("" si no se califica).
        thread_action: Acción de hilo esperada ("" si no se califica).
        asks_information: Valor esperado de `asks_information` (None si no se califica).
        facts: Códigos de acceso que el v9 debería marcar.
        no_facts: Códigos de acceso que el v9 no debe marcar.
        domain: Dominio para la búsqueda directa de la sonda ("" si no aplica).
        categories: Categorías de la base que la búsqueda debería traer.
    """

    id: str
    category: str
    message: str
    history: tuple[tuple[str, str], ...] = ()
    thread_summary: str = ""
    rule: str = ""
    no_alarm: bool = False
    scope: str = ""
    thread_action: str = ""
    asks_information: bool | None = None
    facts: tuple[str, ...] = ()
    no_facts: tuple[str, ...] = ()
    domain: str = ""
    categories: tuple[str, ...] = ()


@dataclass(frozen=True)
class Observation:
    """Lo que produjo una llamada de análisis para un caso.

    Attributes:
        case_id: Caso analizado.
        variant: "v8" o "v9".
        run: Número de repetición (desde 0).
        error: Causa si la llamada falló ("" si no).
        seconds: Duración de la llamada.
        prompt_tokens: Tokens de prompt que informó Ollama (sin los que tenía en caché).
        scope: Alcance efectivo.
        domain: Dominio.
        thread_action: Acción de hilo.
        signs: Códigos de signos marcados.
        symptoms: Síntomas en texto.
        rules_user: Reglas del filtro 1 (texto de la persona; deterministas).
        rules_agent: Reglas del filtro 2 (lo que reportó el modelo).
        search_query: Consulta reformulada.
        asks_information: Si pidió un dato concreto.
        wants_guidance: Si pidió qué hacer.
        access_facts: Códigos de acceso marcados (siempre vacío en v8).
        retrieved: Registros recuperados, en orden (None si no se buscó).
        retrieved_categories: Categorías de esos registros.
        sufficient: Si la evidencia superó el umbral (None si no se buscó).
    """

    case_id: str
    variant: str
    run: int
    error: str = ""
    seconds: float = 0.0
    prompt_tokens: int = 0
    scope: str = ""
    domain: str = ""
    thread_action: str = ""
    signs: tuple[str, ...] = ()
    symptoms: tuple[str, ...] = ()
    rules_user: tuple[str, ...] = ()
    rules_agent: tuple[str, ...] = ()
    search_query: str = ""
    asks_information: bool = False
    wants_guidance: bool = False
    access_facts: tuple[str, ...] = ()
    retrieved: tuple[str, ...] | None = None
    retrieved_categories: tuple[str, ...] = ()
    sufficient: bool | None = None


# --- Casos ----------------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    """Lee un archivo JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases(live_dir: Path, alarm_phrases_file: Path) -> list[Case]:
    """Arma el conjunto completo desde las baterías existentes y los casos propios.

    Args:
        live_dir: Carpeta `tests/live` (frases coloquiales, alcance, sonda y casos propios).
        alarm_phrases_file: `tests/conversational/alarm_phrases.json` (frases sin alarma).

    Returns:
        Los casos, con cada frase sola y con una barrera de acceso agregada.
    """
    own = read_json(live_dir / "prompt_comparison_cases.json")
    barriers = [(b["text"], b["fact"]) for b in own["barriers"]]
    calm = read_json(alarm_phrases_file)["ninguna_regla"]
    return [
        *alarm_cases(read_json(live_dir / "colloquial_alarm_phrases.json")["cases"], barriers),
        *calm_cases(calm, barriers),
        *scope_cases(read_json(live_dir / "scope_cases.json"), barriers),
        *search_cases(read_json(live_dir / "retrieval_probe.json")["cases"], barriers),
        *(own_case(item) for item in own["cases"]),
    ]


def with_barrier(phrase: str, index: int, barriers: Sequence[tuple[str, str]]) -> tuple[str, str]:
    """Frase con una barrera agregada (se rota por índice) y el código de esa barrera."""
    text, fact = barriers[index % len(barriers)]
    return f"{phrase} {text}", fact


def alarm_cases(
    phrases: Sequence[Mapping[str, str]], barriers: Sequence[tuple[str, str]]
) -> list[Case]:
    """Frases coloquiales de alarma, solas y con barrera: la regla esperada no cambia."""
    cases = []
    for index, item in enumerate(phrases):
        message, fact = with_barrier(item["phrase"], index, barriers)
        cases.append(Case(f"col-{index:02d}", CAT_ALARM, item["phrase"], rule=item["rule"]))
        cases.append(
            Case(f"col-{index:02d}-b", CAT_ALARM_BARRIER, message, rule=item["rule"], facts=(fact,))
        )
    return cases


def calm_cases(phrases: Sequence[str], barriers: Sequence[tuple[str, str]]) -> list[Case]:
    """Frases que no activan ninguna regla, solas y con barrera: sigue sin haber alarma."""
    cases = []
    for index, phrase in enumerate(phrases):
        message, fact = with_barrier(phrase, index, barriers)
        cases.append(Case(f"cal-{index:02d}", CAT_CALM, phrase, no_alarm=True))
        cases.append(
            Case(f"cal-{index:02d}-b", CAT_CALM_BARRIER, message, no_alarm=True, facts=(fact,))
        )
    return cases


def scope_cases(groups: Mapping[str, Any], barriers: Sequence[tuple[str, str]]) -> list[Case]:
    """Casos de alcance; solo los que están en alcance se repiten con una barrera."""
    cases = []
    for group in SCOPE_GROUPS:
        for index, phrase in enumerate(groups[group]):
            cases.append(Case(f"alc-{group}-{index}", CAT_SCOPE, phrase, scope=group))
            if group == IN_SCOPE:
                message, fact = with_barrier(phrase, index, barriers)
                name = f"alc-{group}-{index}-b"
                cases.append(Case(name, CAT_SCOPE_BARRIER, message, scope=group, facts=(fact,)))
    return cases


def search_cases(
    probe: Sequence[Mapping[str, Any]], barriers: Sequence[tuple[str, str]]
) -> list[Case]:
    """Consultas de la sonda de recuperación, solas y con barrera: misma categoría esperada."""
    cases = []
    for index, item in enumerate(probe):
        expected = {"domain": item["domain"], "categories": tuple(item["expected_categories"])}
        message, fact = with_barrier(item["query"], index, barriers)
        cases.append(Case(f"bus-{index:02d}", CAT_SEARCH, item["query"], **expected))
        cases.append(
            Case(f"bus-{index:02d}-b", CAT_SEARCH_BARRIER, message, facts=(fact,), **expected)
        )
    return cases


def own_case(item: Mapping[str, Any]) -> Case:
    """Caso propio (adversarial o de continuidad) leído del archivo.

    Raises:
        ValueError: Si un mensaje del historial no es de la persona ni del asistente.
    """
    history = tuple((role, text) for role, text in item.get("history", ()))
    if any(role not in ROLES for role, _ in history):
        raise ValueError(f"Rol desconocido en el historial del caso {item['id']}")
    names = {field.name for field in fields(Case)} - {"history", "facts", "no_facts"}
    plain = {key: value for key, value in item.items() if key in names}
    return Case(
        **plain,
        history=history * int(item.get("history_repeat", 1)),
        facts=tuple(item.get("facts", ())),
        no_facts=tuple(item.get("no_facts", ())),
    )


# --- Calificación ---------------------------------------------------------------------------


def grade(case: Case, seen: Observation) -> dict[str, bool]:
    """Criterios que aplican al caso y si la observación los cumple.

    Una llamada fallida incumple todos los criterios que aplican: sin análisis, la persona
    no recibe orientación (y solo el filtro 1 puede avisarle).
    """
    checks = {**alarm_checks(case, seen), **turn_checks(case, seen), **search_checks(case, seen)}
    if seen.variant == V9:
        checks |= fact_checks(case, seen)
    return {name: passed and not seen.error for name, passed in checks.items()}


def alarm_checks(case: Case, seen: Observation) -> dict[str, bool]:
    """Detección de la regla esperada (con y sin el filtro 1) y ausencia de falsas alarmas."""
    checks: dict[str, bool] = {}
    if case.rule:
        checks[ALARM] = case.rule in {*seen.rules_user, *seen.rules_agent}
        checks[ALARM_MODEL] = case.rule in seen.rules_agent
    if case.no_alarm:
        checks[NO_FALSE_ALARM] = not seen.rules_user and not seen.rules_agent
    return checks


def turn_checks(case: Case, seen: Observation) -> dict[str, bool]:
    """Alcance, continuidad del hilo y pregunta de información."""
    checks: dict[str, bool] = {}
    if case.scope:
        checks[SCOPE] = seen.scope == case.scope
    if case.thread_action:
        checks[THREAD] = seen.thread_action == case.thread_action
    if case.asks_information is not None:
        checks[INFORMATION] = seen.asks_information is case.asks_information
    return checks


def fact_checks(case: Case, seen: Observation) -> dict[str, bool]:
    """Datos de acceso: marca los declarados y no atribuye los que la persona no dijo."""
    checks: dict[str, bool] = {}
    if case.facts:
        checks[FACTS] = set(case.facts) <= set(seen.access_facts)
    if case.no_facts:
        checks[NO_FACTS] = not set(case.no_facts) & set(seen.access_facts)
    return checks


def search_checks(case: Case, seen: Observation) -> dict[str, bool]:
    """Recuperación: la categoría esperada aparece y la evidencia supera el umbral."""
    if not case.categories or seen.retrieved is None:
        return {}
    found = bool(set(case.categories) & set(seen.retrieved_categories))
    return {RETRIEVAL: found, EVIDENCE: bool(seen.sufficient)}


# --- Resumen --------------------------------------------------------------------------------


def tally(
    cases: Sequence[Case], seen: Iterable[Observation]
) -> dict[str, dict[str, dict[str, list[int]]]]:
    """Aciertos y total por variante, categoría y criterio (más la fila "todas")."""
    by_id = {case.id: case for case in cases}
    table: dict[str, dict[str, dict[str, list[int]]]] = {variant: {} for variant in VARIANTS}
    for item in seen:
        case = by_id[item.case_id]
        for criterion, passed in grade(case, item).items():
            for category in (case.category, ALL):
                cell = table[item.variant].setdefault(category, {}).setdefault(criterion, [0, 0])
                cell[0] += passed
                cell[1] += 1
    return table


def same(field: str, left: Observation, right: Observation) -> bool:
    """Indica si dos observaciones coinciden en un campo (los conjuntos, sin importar el orden)."""
    a, b = getattr(left, field), getattr(right, field)
    if field in SET_FIELDS and a is not None and b is not None:
        return set(a) == set(b)
    return bool(a == b)


def agreement(pairs: Iterable[tuple[Observation, Observation]]) -> dict[str, list[int]]:
    """Coincidencias y total por campo entre pares de observaciones sin error."""
    counts = {field: [0, 0] for field in EXACT_FIELDS}
    for left, right in pairs:
        if left.error or right.error:
            continue
        for field in EXACT_FIELDS:
            if getattr(left, field) is None or getattr(right, field) is None:
                continue
            counts[field][0] += same(field, left, right)
            counts[field][1] += 1
    return counts


def cross_pairs(seen: Sequence[Observation]) -> list[tuple[Observation, Observation]]:
    """Pares v8~v9 del mismo caso y la misma repetición."""
    index = {(item.case_id, item.run, item.variant): item for item in seen}
    return [
        (item, index[(item.case_id, item.run, V9)])
        for item in seen
        if item.variant == V8 and (item.case_id, item.run, V9) in index
    ]


def self_pairs(seen: Sequence[Observation], variant: str) -> list[tuple[Observation, Observation]]:
    """Pares de una variante consigo misma: repeticiones consecutivas del mismo caso."""
    index = {(item.case_id, item.run): item for item in seen if item.variant == variant}
    return [
        (item, index[(case_id, run + 1)])
        for (case_id, run), item in index.items()
        if (case_id, run + 1) in index
    ]


def detection_rate(
    cases: Sequence[Case], seen: Sequence[Observation]
) -> dict[str, dict[str, list[int]]]:
    """Por caso con regla esperada y variante: repeticiones que la detectaron y total."""
    expected = {case.id: case for case in cases if case.rule}
    rates: dict[str, dict[str, list[int]]] = {}
    for item in seen:
        case = expected.get(item.case_id)
        if case is None:
            continue
        cell = rates.setdefault(case.id, {v: [0, 0] for v in VARIANTS})[item.variant]
        cell[0] += grade(case, item)[ALARM]
        cell[1] += 1
    return rates


def discordant(rates: Mapping[str, Mapping[str, Sequence[int]]]) -> dict[str, list[str]]:
    """Casos que una variante detecta en la mayoría de las repeticiones y la otra no."""

    def mostly(cell: Sequence[int]) -> bool:
        return cell[1] > 0 and 2 * cell[0] > cell[1]

    only_v8 = [name for name, cell in rates.items() if mostly(cell[V8]) and not mostly(cell[V9])]
    only_v9 = [name for name, cell in rates.items() if mostly(cell[V9]) and not mostly(cell[V8])]
    return {V8: sorted(only_v8), V9: sorted(only_v9)}


def sign_test(only_left: int, only_right: int) -> float:
    """Valor p bilateral exacto de la prueba de signos sobre los casos discordantes.

    Returns:
        1.0 si no hay discordantes. Un valor alto **no** demuestra equivalencia.
    """
    total = only_left + only_right
    if total == 0:
        return 1.0
    tail = sum(math.comb(total, k) for k in range(min(only_left, only_right) + 1))
    return float(min(1.0, 2 * tail / float(2**total)))


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Percentil por el método del rango más cercano (None si no hay valores)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def runtime(seen: Sequence[Observation], variant: str) -> dict[str, Any]:
    """Llamadas, errores, latencia p50 y p90, y el prompt más grande de una variante."""
    own = [item for item in seen if item.variant == variant]
    times = [item.seconds for item in own if not item.error]
    return {
        "llamadas": len(own),
        "errores": sum(bool(item.error) for item in own),
        "p50": percentile(times, P50),
        "p90": percentile(times, P90),
        "max_prompt_tokens": max((item.prompt_tokens for item in own), default=0),
    }


def summarize(cases: Sequence[Case], seen: Sequence[Observation]) -> dict[str, Any]:
    """Resumen completo de una corrida, listo para guardar como JSON o para el informe."""
    rates = detection_rate(cases, seen)
    split = discordant(rates)
    return {
        "casos": len(cases),
        "resultados": tally(cases, seen),
        "acuerdo": {
            "v8~v9": agreement(cross_pairs(seen)),
            "v8~v8": agreement(self_pairs(seen, V8)),
            "v9~v9": agreement(self_pairs(seen, V9)),
        },
        "alarmas_por_caso": rates,
        "discordantes": split,
        "prueba_de_signos_p": sign_test(len(split[V8]), len(split[V9])),
        "ejecucion": {variant: runtime(seen, variant) for variant in VARIANTS},
    }


# --- Informe --------------------------------------------------------------------------------


def ratio(cell: Sequence[int] | None) -> str:
    """Celda "aciertos/total (porcentaje)", o "—" si el criterio no aplica."""
    if not cell or not cell[1]:
        return "—"
    return f"{cell[0]}/{cell[1]} ({100 * cell[0] / cell[1]:.0f} %)"


def results_table(results: Mapping[str, Mapping[str, Mapping[str, Sequence[int]]]]) -> list[str]:
    """Tabla de resultados por categoría y criterio, con una columna por variante."""
    lines = ["| Categoría | Criterio | v8 | v9 |", "|---|---|---|---|"]
    categories = sorted({name for variant in VARIANTS for name in results[variant]} - {ALL})
    for category in (*categories, ALL):
        for criterion in CRITERIA:
            cells = [results[variant].get(category, {}).get(criterion) for variant in VARIANTS]
            if any(cells):
                lines.append(
                    f"| {category} | {criterion} | {ratio(cells[0])} | {ratio(cells[1])} |"
                )
    return lines


def agreement_table(table: Mapping[str, Mapping[str, Sequence[int]]]) -> list[str]:
    """Tabla de acuerdo por campo: v8~v9 junto al acuerdo de cada variante consigo misma."""
    lines = ["| Campo | v8~v9 | v8~v8 (ruido) | v9~v9 (ruido) |", "|---|---|---|---|"]
    for field in EXACT_FIELDS:
        cells = [ratio(table[pair][field]) for pair in ("v8~v9", "v8~v8", "v9~v9")]
        lines.append(f"| {field} | {' | '.join(cells)} |")
    return lines


def runtime_table(execution: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Tabla de llamadas, errores, latencia y tamaño de prompt por variante."""

    def secs(value: float | None) -> str:
        return "—" if value is None else f"{value:.1f} s"

    lines = [
        "| Variante | Llamadas | Errores | p50 | p90 | Prompt máx. (tokens) |",
        "|---|---|---|---|---|---|",
    ]
    for variant in VARIANTS:
        row = execution[variant]
        lines.append(
            f"| {variant} | {row['llamadas']} | {row['errores']} | {secs(row['p50'])} | "
            f"{secs(row['p90'])} | {row['max_prompt_tokens']} |"
        )
    return lines


def missed_lines(rates: Mapping[str, Mapping[str, Sequence[int]]]) -> list[str]:
    """Casos de alarma que alguna variante no detectó en todas las repeticiones."""
    lines = []
    for name, cell in sorted(rates.items()):
        if any(cell[variant][0] < cell[variant][1] for variant in VARIANTS):
            lines.append(f"- `{name}`: v8 {ratio(cell[V8])} · v9 {ratio(cell[V9])}")
    return lines or ["- Ninguno."]


def render_report(summary: Mapping[str, Any], header: Sequence[str]) -> str:
    """Informe en Markdown de una corrida.

    Args:
        summary: Resultado de `summarize`.
        header: Líneas con el modelo, la configuración y las huellas de lo que se comparó.

    Returns:
        El informe completo.
    """
    split = summary["discordantes"]
    return "\n".join(
        [
            "# Comparación del prompt de análisis v8 y v9",
            "",
            *header,
            f"- Casos: {summary['casos']}",
            "",
            "## Resultados contra lo esperado",
            *results_table(summary["resultados"]),
            "",
            "## Acuerdo entre variantes y ruido del modelo",
            "v9 solo se distingue de v8 en un campo si su acuerdo con v8 es menor que el ruido.",
            *agreement_table(summary["acuerdo"]),
            "",
            "## Alarmas no detectadas en alguna repetición",
            *missed_lines(summary["alarmas_por_caso"]),
            "",
            f"- Detectadas solo por v8 (mayoría de repeticiones): {split[V8] or 'ninguna'}",
            f"- Detectadas solo por v9: {split[V9] or 'ninguna'}",
            f"- Prueba de signos (bilateral, exacta): p = {summary['prueba_de_signos_p']:.3f}. "
            "Un valor alto no demuestra equivalencia.",
            "",
            "## Ejecución",
            *runtime_table(summary["ejecucion"]),
        ]
    )
