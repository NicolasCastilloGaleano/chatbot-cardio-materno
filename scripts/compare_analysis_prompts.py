"""Compara el prompt de análisis v8 con el v9 usando el modelo real (ADR 0023).

Uso (en el PC de pruebas, dentro de `.venv`, con Ollama y los modelos de `.env`):

    python scripts/compare_analysis_prompts.py --runs 3 --retrieval

Mantiene constante todo menos el prompt y su esquema: mismo modelo, misma temperatura, misma
ventana de contexto, mismo catálogo de alarmas, mismo corpus e índice y los mismos casos. En
cada caso alterna cuál variante va primero, para que el calentamiento no favorezca a una.

Opciones:
    --runs N        Repeticiones por caso (por defecto 3; con 1 no se mide el ruido).
    --retrieval     Busca en el índice real con la consulta de cada análisis.
    --category X    Solo esa batería (se puede repetir).
    --limit N       Solo los primeros N casos (para una prueba rápida).

Guarda el informe y las observaciones en `data/benchmarks/` (no se versiona). Todos los
mensajes son sintéticos. No cambia ninguna regla, umbral ni contenido.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)]

from cardio_materno.application.agent_turn import (  # noqa: E402
    AnalysisTurn,
    analysis_schema,
    parse_analysis,
)
from cardio_materno.application.alarm_policy import AlarmPolicy  # noqa: E402
from cardio_materno.application.errors import LanguageModelError  # noqa: E402
from cardio_materno.application.evidence import build_evidence_query  # noqa: E402
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery  # noqa: E402
from cardio_materno.application.scope import effective_scope  # noqa: E402
from cardio_materno.application.turn_context import TurnInput, analysis_context  # noqa: E402
from cardio_materno.domain.alarms import AlertOrigin  # noqa: E402
from cardio_materno.domain.conversation import (  # noqa: E402
    ChatMessage,
    Domain,
    Role,
    open_thread,
)
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus  # noqa: E402
from cardio_materno.domain.privacy import redact_identifiers  # noqa: E402
from cardio_materno.domain.trace import ModelUsage  # noqa: E402
from scripts.prompt_comparison import (  # noqa: E402
    V8,
    V9,
    VARIANTS,
    Case,
    Observation,
    load_cases,
    render_report,
    summarize,
)

LIVE_DIR = PROJECT_ROOT / "tests" / "live"
ALARM_PHRASES_FILE = PROJECT_ROOT / "tests" / "conversational" / "alarm_phrases.json"
REPORT_DIR = PROJECT_ROOT / "data" / "benchmarks"
DEFAULT_RUNS = 3
THREAD_ID = "hilo-comparacion"
DIGEST_CHARS = 12
Search = Callable[[EvidenceQuery], RetrievalResult]


class Analyzer(Protocol):
    """Lo que la comparación necesita del modelo de análisis."""

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Respuesta JSON del modelo restringida por el esquema."""
        ...

    def last_usage(self) -> ModelUsage | None:
        """Uso de la última llamada, si el modelo lo informa."""
        ...


@dataclass(frozen=True)
class Variant:
    """Una de las dos configuraciones que se comparan.

    Attributes:
        name: "v8" o "v9".
        prompt: Prompt de análisis ya renderizado.
        fact_codes: Códigos de acceso del esquema (vacío en v8).
    """

    name: str
    prompt: str
    fact_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bench:
    """Todo lo que permanece constante entre las dos variantes.

    Attributes:
        analyzer: Modelo de análisis.
        policy: Catálogo de alarmas.
        search: Búsqueda en el índice real, o None si no se mide la recuperación.
        clock: Reloj para medir cada llamada.
    """

    analyzer: Analyzer
    policy: AlarmPolicy
    search: Search | None = None
    clock: Callable[[], float] = time.perf_counter


def turn_of(case: Case) -> tuple[TurnInput, Any]:
    """Turno (ya minimizado, como en `ConversationService.send`) e hilo abierto del caso."""
    recent = tuple(ChatMessage(Role(role), text) for role, text in case.history)
    turn = TurnInput(redact_identifiers(case.message), recent)
    if not case.thread_summary:
        return turn, None
    now = datetime.now(UTC)
    return turn, open_thread(THREAD_ID, Domain.MATERNAL_CHILD, case.thread_summary, now)


def rule_ids(decisions: Sequence[Any]) -> tuple[str, ...]:
    """Reglas activadas por una o varias decisiones de alarma, sin repetir y en orden."""
    found = {rule_id for d in decisions if d is not None for rule_id in d.rule_ids}
    return tuple(sorted(found))


def observe(bench: Bench, variant: Variant, case: Case, run: int) -> Observation:
    """Analiza un caso con una variante y registra lo que produjo, sin lanzar errores."""
    turn, thread = turn_of(case)
    context = analysis_context(variant.prompt, thread, turn)
    schema = analysis_schema(bench.policy.codes, variant.fact_codes)
    by_user = rule_ids([bench.policy.evaluate([turn.user_text], AlertOrigin.USER)])
    start = bench.clock()
    try:
        data = bench.analyzer.complete_json(context, schema)
        analysis = parse_analysis(data, bench.policy.codes, variant.fact_codes)
    except LanguageModelError as error:
        elapsed = bench.clock() - start
        return Observation(
            case.id, variant.name, run, str(error) or "error", elapsed, rules_user=by_user
        )
    seen = Observation(case.id, variant.name, run, "", bench.clock() - start, rules_user=by_user)
    return with_search(with_analysis(seen, bench, analysis, turn), bench, case, analysis, turn)


def with_analysis(
    seen: Observation, bench: Bench, analysis: AnalysisTurn, turn: TurnInput
) -> Observation:
    """Agrega lo que decidió el análisis y las reglas que activa el filtro 2."""
    by_text = bench.policy.evaluate(analysis.reported_symptoms, AlertOrigin.AGENT)
    by_code = bench.policy.evaluate_codes(analysis.reported_signs)
    usage = bench.analyzer.last_usage()
    values = asdict(seen) | {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "scope": str(effective_scope(analysis, turn.recent)),
        "domain": str(analysis.domain),
        "thread_action": str(analysis.thread_action),
        "signs": analysis.reported_signs,
        "symptoms": analysis.reported_symptoms,
        "rules_agent": rule_ids([by_text, by_code]),
        "search_query": analysis.search_query,
        "asks_information": analysis.asks_information,
        "wants_guidance": analysis.wants_guidance,
        "access_facts": analysis.access_facts,
    }
    return Observation(**values)


def with_search(
    seen: Observation, bench: Bench, case: Case, analysis: AnalysisTurn, turn: TurnInput
) -> Observation:
    """Agrega lo que recupera la búsqueda real con la consulta del análisis."""
    if bench.search is None or not case.categories:
        return seen
    result = bench.search(build_evidence_query(analysis, turn.user_text))
    values = asdict(seen) | {
        "retrieved": tuple(item.entry.id for item in result.items),
        "retrieved_categories": tuple(item.entry.category for item in result.items),
        "sufficient": result.status is RetrievalStatus.SUFFICIENT,
    }
    return Observation(**values)


def run_comparison(
    bench: Bench, variants: Sequence[Variant], cases: Sequence[Case], runs: int
) -> list[Observation]:
    """Analiza cada caso con las dos variantes, `runs` veces, alternando el orden.

    Args:
        bench: Modelo, catálogo y búsqueda, iguales para las dos variantes.
        variants: Las dos variantes (v8 y v9).
        cases: Casos de evaluación.
        runs: Repeticiones por caso.

    Returns:
        Una observación por caso, variante y repetición.
    """
    seen = []
    for run in range(runs):
        for index, case in enumerate(cases):
            order = variants if (index + run) % 2 == 0 else tuple(reversed(variants))
            for variant in order:
                item = observe(bench, variant, case, run)
                seen.append(item)
                mark = "⚠️" if item.error else "·"
                print(f"{mark} {run + 1}/{runs} {variant.name} {case.id} {item.seconds:.1f} s")
    return seen


def digest(text: str) -> str:
    """Huella corta de un texto, para saber qué se comparó."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_CHARS]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Lee las opciones de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Compara el prompt de análisis v8 y v9.")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--retrieval", action="store_true")
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def selected(cases: Sequence[Case], args: argparse.Namespace) -> list[Case]:
    """Casos de las baterías pedidas, hasta el límite."""
    chosen = [case for case in cases if not args.category or case.category in args.category]
    return chosen[: args.limit] if args.limit else chosen


def save(report: str, summary: dict[str, Any], seen: Sequence[Observation]) -> Path:
    """Guarda el informe y las observaciones en `data/benchmarks/`; devuelve el informe."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = REPORT_DIR / f"comparacion-v8-v9-{datetime.now():%Y%m%d-%H%M}"
    stem.with_suffix(".md").write_text(report + "\n", encoding="utf-8")
    raw = {"resumen": summary, "observaciones": [asdict(item) for item in seen]}
    stem.with_suffix(".json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return stem.with_suffix(".md")


def main(argv: Sequence[str]) -> int:
    """Ejecuta la comparación con el modelo real y guarda el informe.

    Returns:
        0 si terminó; 1 si el entorno no tiene lo necesario.
    """
    # Las dependencias de arranque se importan aquí: la lógica de arriba se prueba sin ellas.
    from scripts.live_bench import LiveSetupError, build_live_bench

    args = parse_args(argv)
    try:
        bench, variants, header = build_live_bench(os.environ, args.retrieval)
    except LiveSetupError as error:
        print(f"No se puede comparar en este equipo: {error}", file=sys.stderr)
        return 1
    cases = selected(load_cases(LIVE_DIR, ALARM_PHRASES_FILE), args)
    seen = run_comparison(bench, variants, cases, args.runs)
    summary = summarize(cases, seen)
    report = render_report(summary, [*header, f"- Repeticiones por caso: {args.runs}"])
    print(report)
    print(f"\nInforme guardado en {save(report, summary, seen)}")
    return 0


__all__ = ["V8", "V9", "VARIANTS", "Bench", "Search", "Variant", "digest", "run_comparison"]

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
