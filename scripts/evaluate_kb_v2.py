"""Evalúa la base v2 con sus propias preguntas (MIG-08, ADR 0016 y 0017).

Uso:
    python scripts/evaluate_kb_v2.py alarmas
    python scripts/evaluate_kb_v2.py recuperacion [etapas separadas por coma]

Usa los archivos de la base configurados en `.env` (`KB_ENTRIES_FILE`, `KB_CASES_FILE`,
`KB_INDEX_DIR`). La columna "Preguntas" de la base son mensajes reales etiquetados con su
cuadro y su etapa, así que sirven como banco de prueba:

- `alarmas` (sin Ollama): pasa cada pregunta por el filtro 1 de alarmas y cuenta cuántas
  activan una alarma según la ruta base de su cuadro. Ayuda a ver posibles falsos positivos
  (cuadros de autocuidado) y vacíos (cuadros de urgencias). Solo mide: no cambia reglas.
- `recuperacion` (con Ollama y el índice): busca cada pregunta **sin su propio registro**
  (dejando uno fuera) y mide si el cuadro correcto queda primero o entre los tres primeros, y
  la similitud de los aciertos. Sirve para recalibrar `min_similarity` (MIG-07). Por defecto
  usa las preguntas de las etapas T1 y de verificación, que son las que abren un caso.
"""

import os
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cardio_materno.adapters.outbound.clinical_rules.json_alarm_catalog import (  # noqa: E402
    load_alarm_policy,
)
from cardio_materno.adapters.outbound.rag.hybrid_retriever import HybridRetriever  # noqa: E402
from cardio_materno.adapters.outbound.rag.knowledge_files import (  # noqa: E402
    KnowledgeBaseError,
    load_case_profiles,
    load_entries,
)
from cardio_materno.adapters.outbound.rag.vector_index import load_index  # noqa: E402
from cardio_materno.application.alarm_policy import AlarmPolicy  # noqa: E402
from cardio_materno.application.errors import LanguageModelError  # noqa: E402
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery  # noqa: E402
from cardio_materno.bootstrap.env_file import load_env_file  # noqa: E402
from cardio_materno.bootstrap.rag_setup import build_embedder, load_effective_policy  # noqa: E402
from cardio_materno.bootstrap.settings import (  # noqa: E402
    ConfigurationError,
    RagSettings,
    load_ollama_settings,
    load_rag_settings,
)
from cardio_materno.domain.alarms import AlertOrigin  # noqa: E402
from cardio_materno.domain.knowledge import CaseProfile, KnowledgeEntry, Stage  # noqa: E402

MODE_ARG = 1
STAGES_ARG = 2
MODE_ALARMS = "alarmas"
MODE_RETRIEVAL = "recuperacion"
DEFAULT_RETRIEVAL_STAGES = (Stage.DISCRIMINATORS, Stage.CASE_CHECK)
ALARM_RULES_FILE = PROJECT_ROOT / "knowledge" / "alarm_rules.json"
EXAMPLES_SHOWN = 10
# Con el registro propio fuera, se piden cuatro para quedarse con los tres primeros.
LEAVE_ONE_OUT_TOP_K = 4
TOP_N = 3
PERCENTILES = (5, 10, 25, 50)
NO_ALARM = "sin alarma"
EXIT_OK = 0
EXIT_ERROR = 1


@dataclass
class AlarmTally:
    """Conteo del filtro 1 por ruta base del cuadro y ejemplos para revisar."""

    counts: defaultdict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    examples: list[str] = field(default_factory=list)


@dataclass
class RetrievalTally:
    """Aciertos del cuadro y similitudes del primer resultado."""

    total: int = 0
    top1: int = 0
    top3: int = 0
    hit_scores: list[float] = field(default_factory=list)
    miss_scores: list[float] = field(default_factory=list)


# --- Alarmas (sin Ollama) ---------------------------------------------------------------------


def evaluate_alarms(
    entries: Sequence[KnowledgeEntry], profiles: dict[str, CaseProfile], policy: AlarmPolicy
) -> AlarmTally:
    """Pasa cada pregunta por el filtro 1 y cuenta el resultado por ruta base del cuadro."""
    tally = AlarmTally()
    for entry in entries:
        route = str(profiles[entry.motive].base_route)
        decision = policy.evaluate([entry.question], AlertOrigin.USER)
        outcome = str(decision.severity) if decision is not None else NO_ALARM
        tally.counts[route][outcome] += 1
        if decision is not None and decision.is_immediate and route == "autocuidado":
            tally.examples.append(f"{entry.id}: {entry.question} → {decision.rule_ids}")
    return tally


def alarm_report(tally: AlarmTally) -> list[str]:
    """Tabla del filtro 1 por ruta base y ejemplos de urgencias en cuadros de autocuidado."""
    lines = ["Filtro 1 sobre las preguntas de la base, por ruta base del cuadro:"]
    for route, counter in sorted(tally.counts.items()):
        total = sum(counter.values())
        detail = ", ".join(f"{name}: {count}" for name, count in counter.most_common())
        lines.append(f"  {route} ({total}): {detail}")
    lines.append(f"Urgencias en cuadros de autocuidado ({len(tally.examples)}), para revisar:")
    lines += [f"  {example}" for example in tally.examples[:EXAMPLES_SHOWN]]
    return lines


# --- Recuperación (con Ollama) ----------------------------------------------------------------


def evaluate_retrieval(
    retriever: HybridRetriever, queries: Sequence[KnowledgeEntry]
) -> RetrievalTally:
    """Busca cada pregunta sin su propio registro y compara el cuadro encontrado."""
    tally = RetrievalTally()
    for number, entry in enumerate(queries, start=1):
        result = retriever.retrieve(EvidenceQuery(entry.question))
        others = [item for item in result.items if item.entry.id != entry.id][:TOP_N]
        record_hit(tally, entry.motive, [(item.entry.motive, item.score) for item in others])
        print(f"\r  {number}/{len(queries)}", end="", flush=True)
    print()
    return tally


def record_hit(tally: RetrievalTally, motive: str, ranked: list[tuple[str, float]]) -> None:
    """Suma el resultado de una pregunta: acierto en el primero, entre tres o fallo."""
    tally.total += 1
    if not ranked:
        return
    first_motive, first_score = ranked[0]
    tally.top3 += int(any(found == motive for found, _ in ranked))
    if first_motive == motive:
        tally.top1 += 1
        tally.hit_scores.append(first_score)
    else:
        tally.miss_scores.append(first_score)


def retrieval_report(tally: RetrievalTally, threshold: float) -> list[str]:
    """Precisión por cuadro y percentiles de similitud para elegir el umbral."""
    return [
        f"Cuadro correcto primero: {share(tally.top1, tally.total)} · entre los {TOP_N} "
        f"primeros: {share(tally.top3, tally.total)}",
        f"Similitud del primero cuando acierta: {percentiles(tally.hit_scores)}",
        f"Similitud del primero cuando falla:  {percentiles(tally.miss_scores)}",
        f"Umbral actual: {threshold:.2f}. Aciertos que quedarían por debajo: "
        f"{sum(1 for score in tally.hit_scores if score < threshold)}",
    ]


def share(count: int, total: int) -> str:
    """Cantidad y porcentaje ("12/20 (60 %)")."""
    return f"{count}/{total} ({100 * count / max(total, 1):.0f} %)"


def percentiles(scores: Sequence[float]) -> str:
    """Percentiles de una lista de similitudes ("sin datos" si está vacía)."""
    if not scores:
        return "sin datos"
    ordered = sorted(scores)
    picks = [ordered[min(len(ordered) - 1, len(ordered) * p // 100)] for p in PERCENTILES]
    return " · ".join(f"p{p} {value:.2f}" for p, value in zip(PERCENTILES, picks, strict=True))


def build_evaluation_retriever(
    settings: RagSettings, entries: Sequence[KnowledgeEntry]
) -> tuple[HybridRetriever, float]:
    """Buscador sin umbral y con cuatro resultados; devuelve también el umbral configurado.

    Raises:
        KnowledgeBaseError: Si falta el índice o no corresponde a la base.
        LanguageModelError: Si el modelo de embeddings no está disponible.
    """
    policy = load_effective_policy(settings)
    embedder = build_embedder(settings, load_ollama_settings(os.environ).base_url)
    embedder.verify_ready()
    evaluation = replace(policy, top_k=LEAVE_ONE_OUT_TOP_K, min_similarity=-1.0)
    retriever = HybridRetriever(entries, load_index(settings.index_dir), embedder, evaluation)
    return retriever, policy.min_similarity


# --- Punto de entrada -------------------------------------------------------------------------


def parse_stages(argv: list[str]) -> tuple[Stage, ...]:
    """Etapas cuyas preguntas se evalúan en `recuperacion` (por defecto T1 y verificación).

    Raises:
        ValueError: Si una etapa no existe.
    """
    if len(argv) <= STAGES_ARG:
        return DEFAULT_RETRIEVAL_STAGES
    return tuple(Stage(name.strip()) for name in argv[STAGES_ARG].split(","))


def run(mode: str, argv: list[str], settings: RagSettings) -> list[str]:
    """Ejecuta el modo pedido y devuelve las líneas del informe.

    Raises:
        KnowledgeBaseError, LanguageModelError, ValueError: Si falta algo para evaluar.
    """
    entries = [entry for entry in load_entries(settings.entries_file) if entry.stage is not None]
    if not entries:
        raise KnowledgeBaseError("La base configurada no tiene cuadros: no es la base v2")
    if mode == MODE_ALARMS:
        profiles = {p.motive: p for p in load_case_profiles(settings.cases_file)}
        tally = evaluate_alarms(entries, profiles, load_alarm_policy(ALARM_RULES_FILE))
        return alarm_report(tally)
    stages = parse_stages(argv)
    retriever, threshold = build_evaluation_retriever(settings, entries)
    queries = [entry for entry in entries if entry.stage in stages]
    return retrieval_report(evaluate_retrieval(retriever, queries), threshold)


def main(argv: list[str]) -> int:
    """Punto de entrada del script."""
    if len(argv) <= MODE_ARG or argv[MODE_ARG] not in (MODE_ALARMS, MODE_RETRIEVAL):
        print(__doc__)
        return EXIT_ERROR
    try:
        load_env_file(PROJECT_ROOT / ".env")
        settings = load_rag_settings(os.environ, PROJECT_ROOT)
        lines = run(argv[MODE_ARG], argv, settings)
    except (ConfigurationError, KnowledgeBaseError, LanguageModelError, ValueError) as error:
        print(f"ERROR: {error}")
        return EXIT_ERROR
    print("\n".join(lines))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
