"""Compara combinaciones de modelos de Ollama para decidir la latencia (B-022, ADR 0011).

Para cada combinación (modelo de análisis + modelo de respuesta) mide, con los casos que ya
usa el proyecto:

- **Alcance:** aciertos en `tests/live/scope_cases.json`.
- **Filtro 2:** reglas de alarma que se activan con los síntomas que reporta el análisis, con
  las frases coloquiales de `tests/live/colloquial_alarm_phrases.json`. Se mide el filtro 2 por
  sí solo (cuánto entiende el modelo el lenguaje coloquial), con el mismo conjunto en todas las
  rondas; las frases que también capta el filtro 1 se marcan en la consola.
- **Turnos completos:** las consultas de `tests/live/retrieval_probe.json` con el asistente
  armado como en producción: respuestas verificadas, con texto literal o con abstención, y
  tiempos por etapa.
- **Errores:** respuestas del modelo que no cumplen el JSON esperado.

Cuando un turno termina en texto literal, se imprimen las frases descartadas (para calibrar).

Uso (en el PC de pruebas, con los modelos descargados):
    .venv/bin/python scripts/benchmark_models.py mistral-small3.1:24b qwen3:8b+mistral-small3.1:24b

Cada argumento es "MODELO" (ambas etapas) o "ANÁLISIS+RESPUESTA". El informe se imprime y se
guarda en `data/benchmarks/` (no se versiona). Elegir el modelo es una decisión del equipo.
"""

import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import (  # noqa: E402
    load_alarm_policy,
)
from cardio_materno.adapters.outbound.llm.ollama_language_model import (  # noqa: E402
    OllamaLanguageModel,
)
from cardio_materno.application.agent_turn import (  # noqa: E402
    ANALYSIS_SCHEMA,
    AnalysisTurn,
    Scope,
    parse_analysis,
)
from cardio_materno.application.alarm_policy import (  # noqa: E402
    AlarmPolicy,
    render_system_prompt,
)
from cardio_materno.application.conversation_service import ConversationService  # noqa: E402
from cardio_materno.application.errors import LanguageModelError  # noqa: E402
from cardio_materno.application.scope import effective_scope  # noqa: E402
from cardio_materno.application.turn_context import TurnInput, analysis_context  # noqa: E402
from cardio_materno.bootstrap.env_file import load_env_file  # noqa: E402
from cardio_materno.bootstrap.main import (  # noqa: E402
    ANALYSIS_PROMPT_FILE,
    ENV_FILE,
    build_service,
)
from cardio_materno.bootstrap.settings import (  # noqa: E402
    ANALYSIS_MODEL_VARIABLE,
    REPLY_MODEL_VARIABLE,
    load_conversation_settings,
    load_stage_settings,
)
from cardio_materno.domain.alarms import AlertOrigin  # noqa: E402
from cardio_materno.domain.trace import ReplyTrace  # noqa: E402

LIVE_DIR = PROJECT_ROOT / "tests" / "live"
COLLOQUIAL_PHRASES_FILE = LIVE_DIR / "colloquial_alarm_phrases.json"
REPORT_DIR = PROJECT_ROOT / "data" / "benchmarks"
COMBO_SEPARATOR = "+"
P90 = 0.9
SCOPE_KEYS = {
    "en_alcance": Scope.IN_SCOPE,
    "fuera_de_alcance": Scope.OUT_OF_SCOPE,
    "conversacional": Scope.CONVERSATIONAL,
}
TABLE_HEADER = (
    "| Análisis | Respuesta | Errores JSON | Alcance | Filtro 2 (coloquiales) | Verificadas | "
    "Literal | Abstención | Otros | Turno p50 | Turno p90 | Análisis p50 | Respuesta p50 |\n"
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
)


@dataclass
class ComboResult:
    """Resultados de una combinación de modelos."""

    analysis_model: str
    reply_model: str
    json_errors: int = 0
    scope_hits: int = 0
    scope_total: int = 0
    alarm_hits: int = 0
    alarm_total: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)
    turn_seconds: list[float] = field(default_factory=list)
    analysis_seconds: list[float] = field(default_factory=list)
    reply_seconds: list[float] = field(default_factory=list)


def main(argv: Sequence[str]) -> int:
    """Ejecuta la comparación de las combinaciones dadas y guarda el informe.

    Returns:
        0 si terminó; 1 si faltan argumentos.
    """
    if not argv:
        print(__doc__)
        return 1
    load_env_file(ENV_FILE)
    results = [run_combo(*parse_combo(arg)) for arg in argv]
    report = render_report(results)
    print(report)
    print(f"\nInforme guardado en {save_report(report)}")
    return 0


def parse_combo(arg: str) -> tuple[str, str]:
    """Separa una combinación: "A+B" → (A, B); "A" → (A, A)."""
    analysis, _, reply = arg.partition(COMBO_SEPARATOR)
    return analysis, reply or analysis


def run_combo(analysis_model: str, reply_model: str) -> ComboResult:
    """Mide una combinación: alcance, filtro 2 y turnos completos."""
    print(f"\n=== {analysis_model} + {reply_model} ===")
    os.environ[ANALYSIS_MODEL_VARIABLE] = analysis_model
    os.environ[REPLY_MODEL_VARIABLE] = reply_model
    result = ComboResult(analysis_model, reply_model)
    analyzer = OllamaLanguageModel(load_stage_settings(os.environ, ANALYSIS_MODEL_VARIABLE))
    analyzer.verify_ready()
    analyzer.warm_up()
    policy = load_alarm_policy(
        load_conversation_settings(os.environ, PROJECT_ROOT).alarm_rules_file
    )
    prompt = render_system_prompt(ANALYSIS_PROMPT_FILE.read_text(encoding="utf-8"), policy)
    measure_scope(analyzer, prompt, result)
    measure_alarms(analyzer, prompt, policy, result)
    measure_turns(result)
    return result


def analyze(
    analyzer: OllamaLanguageModel, prompt: str, text: str, result: ComboResult
) -> AnalysisTurn | None:
    """Llamada de análisis sin hilo; registra el tiempo y los errores de JSON."""
    start = time.perf_counter()
    try:
        context = analysis_context(prompt, None, TurnInput(text))
        return parse_analysis(analyzer.complete_json(context, ANALYSIS_SCHEMA))
    except LanguageModelError as error:
        result.json_errors += 1
        print(f"  ⚠️ {text[:50]}… → {error}")
        return None
    finally:
        result.analysis_seconds.append(time.perf_counter() - start)


def measure_scope(analyzer: OllamaLanguageModel, prompt: str, result: ComboResult) -> None:
    """Aciertos de alcance con los casos compartidos de HU-07."""
    cases: dict[str, Any] = read_json(LIVE_DIR / "scope_cases.json")
    for key, expected in SCOPE_KEYS.items():
        for message in cases[key]:
            analysis = analyze(analyzer, prompt, message, result)
            hit = analysis is not None and effective_scope(analysis) is expected
            result.scope_total += 1
            result.scope_hits += hit
            print(f"  alcance {'✅' if hit else '❌'} {message[:60]}")


def measure_alarms(
    analyzer: OllamaLanguageModel, prompt: str, policy: AlarmPolicy, result: ComboResult
) -> None:
    """Reglas que capta el filtro 2 por sí solo en las frases coloquiales."""
    for case in read_json(COLLOQUIAL_PHRASES_FILE)["cases"]:
        rule_id, phrase = case["rule"], case["phrase"]
        analysis = analyze(analyzer, prompt, phrase, result)
        symptoms = analysis.reported_symptoms if analysis else ()
        hit = triggers(policy, symptoms, AlertOrigin.AGENT, rule_id)
        result.alarm_total += 1
        result.alarm_hits += hit
        also = (
            " (también filtro 1)" if triggers(policy, [phrase], AlertOrigin.USER, rule_id) else ""
        )
        print(
            f"  filtro 2 {'✅' if hit else '❌'}{also} {rule_id}: {phrase[:50]} → {list(symptoms)}"
        )


def triggers(policy: AlarmPolicy, texts: Sequence[str], origin: AlertOrigin, rule_id: str) -> bool:
    """True si los textos activan la regla indicada."""
    decision = policy.evaluate(texts, origin)
    return decision is not None and rule_id in decision.rule_ids


def measure_turns(result: ComboResult) -> None:
    """Turnos completos con las consultas de la sonda, como en producción."""
    with tempfile.TemporaryDirectory() as threads_dir:
        os.environ["THREADS_DIR"] = threads_dir
        service = build_service(load_conversation_settings(os.environ, PROJECT_ROOT))
        for case in read_json(LIVE_DIR / "retrieval_probe.json")["cases"]:
            run_turn(service, case["query"], result)


def run_turn(service: ConversationService, text: str, result: ComboResult) -> None:
    """Un turno completo: clasifica cómo terminó y guarda sus tiempos."""
    start = time.perf_counter()
    try:
        trace = service.send(text).trace
        kind = outcome_kind(trace)
    except LanguageModelError:
        result.json_errors += 1
        trace, kind = None, "error"
    result.turn_seconds.append(time.perf_counter() - start)
    service.end_session()
    result.outcomes[kind] = result.outcomes.get(kind, 0) + 1
    record_stage_times(trace, result)
    print(f"  turno {kind}: {text[:60]}")
    for sentence in dropped_sentences(trace):
        print(f"      descartada: {sentence}")


def outcome_kind(trace: ReplyTrace | None) -> str:
    """Cómo terminó un turno: verificada, literal, abstención u otro (urgencia, saludo…)."""
    if trace is None or trace.retrieval_status is None:
        return "otro"
    if trace.grounding is None:
        return "abstención"
    return "literal" if trace.grounding.literal else "verificada"


def dropped_sentences(trace: ReplyTrace | None) -> tuple[str, ...]:
    """Frases que el verificador descartó en un turno (vacío si no hubo)."""
    return trace.grounding.dropped if trace and trace.grounding else ()


def record_stage_times(trace: ReplyTrace | None, result: ComboResult) -> None:
    """Guarda el tiempo de la llamada de respuesta, si la hubo."""
    for timing in trace.timings if trace else ():
        if timing.stage == "respuesta":
            result.reply_seconds.append(timing.seconds)


def render_report(results: Sequence[ComboResult]) -> str:
    """Informe en Markdown con una fila por combinación."""
    header = f"# Comparación de modelos ({datetime.now():%Y-%m-%d %H:%M})\n\n{TABLE_HEADER}"
    return "\n".join([header, *(render_row(result) for result in results)])


def render_row(r: ComboResult) -> str:
    """Fila de la tabla de una combinación."""
    count: Callable[[str], int] = lambda kind: r.outcomes.get(kind, 0)  # noqa: E731
    cells = [
        r.analysis_model,
        r.reply_model,
        str(r.json_errors),
        f"{r.scope_hits}/{r.scope_total}",
        f"{r.alarm_hits}/{r.alarm_total}",
        str(count("verificada")),
        str(count("literal")),
        str(count("abstención")),
        str(count("otro") + count("error")),
        seconds(percentile(r.turn_seconds, 0.5)),
        seconds(percentile(r.turn_seconds, P90)),
        seconds(percentile(r.analysis_seconds, 0.5)),
        seconds(percentile(r.reply_seconds, 0.5)),
    ]
    return "| " + " | ".join(cells) + " |"


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Percentil por el método del rango más cercano (None si no hay valores)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def seconds(value: float | None) -> str:
    """Segundos con un decimal, o "—" si no hay dato."""
    return "—" if value is None else f"{value:.1f} s"


def save_report(report: str) -> Path:
    """Guarda el informe en `data/benchmarks/` y devuelve su ruta."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"benchmark-{datetime.now():%Y%m%d-%H%M}.md"
    path.write_text(report + "\n", encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    """Lee un archivo JSON del proyecto."""
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
