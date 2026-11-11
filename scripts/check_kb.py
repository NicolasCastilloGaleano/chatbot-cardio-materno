"""Revisa los borradores de la base (CSV) o `entries.jsonl` contra las reglas de la matriz (§11).

Uso:
    python scripts/check_kb.py <archivo.csv | entries.jsonl> [...] [--base entries.jsonl]
                               [--sources fuentes.md]

Errores (código de salida 1): enfoque o tipo inválido, longitud de respuesta fuera de rango,
términos prohibidos (dosis, diagnóstico), pregunta repetida, fuente vacía o fuera del catálogo.
Avisos: preguntas casi iguales a otras, y categorías fuera de las cuotas de enfoque o de
preguntas generales. Solo usa la librería estándar.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_sheet_kb import clean, normalize_header, read_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "knowledge" / "kb" / "entries.jsonl"
DEFAULT_SOURCES = ROOT / "docs" / "04-datos" / "fuentes-base-conocimiento.md"
FOCUS_VALUES = {"Solucionar", "Indagar"}
TYPE_VALUES = {"general", "escenario"}
MIN_ANSWER_CHARS = 300
MAX_ANSWER_CHARS = 650
SOLVE_SHARE_RANGE = (0.6, 0.8)
MIN_GENERAL_SHARE = 0.3
NEAR_DUPLICATE_JACCARD = 0.8
MIN_TOKEN_CHARS = 3
FORBIDDEN_PATTERNS = {
    "dosis": re.compile(r"\b\d+([.,]\d+)?\s?(mg|ml|mcg|µg|ui|unidades)\b", re.IGNORECASE),
    "diagnóstico": re.compile(
        r"\b(usted tiene|lo que tienes es|seguramente tienes|tu diagnóstico es)\b", re.I
    ),
}
SOURCE_ID_PATTERN = re.compile(r"^\|\s*`?([A-Z0-9][A-Z0-9-]{2,})`?\s*\|", re.MULTILINE)
HEADER_FIELDS = {
    "categoria": "category",
    "enfoque": "focus",
    "preguntas": "question",
    "pregunta": "question",
    "respuestas": "answer",
    "respuesta": "answer",
    "fuente": "source",
    "tipo": "kind",
}


@dataclass(frozen=True)
class Record:
    """Un registro por revisar, con su origen para los mensajes."""

    origin: str
    category: str
    focus: str
    question: str
    answer: str
    source: str | None = None
    kind: str | None = None


@dataclass
class Report:
    """Errores y avisos acumulados."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_csv(path: Path) -> list[Record]:
    """Lee un borrador en CSV con cabecera (las columnas Fuente y Tipo son opcionales)."""
    rows = read_csv(path)
    if not rows:
        return []
    index = {
        HEADER_FIELDS[h]: i
        for i, h in enumerate(map(normalize_header, rows[0]))
        if h in HEADER_FIELDS
    }
    records = []
    for number, row in enumerate(rows[1:], start=2):
        values = {name: clean(row[i]) if i < len(row) else "" for name, i in index.items()}
        if any(values.values()):
            records.append(make_record(f"{path.name}:{number}", values))
    return records


def make_record(origin: str, values: Mapping[str, str | None]) -> Record:
    """Arma un registro a partir de los campos leídos."""
    return Record(
        origin=origin,
        category=values.get("category") or "",
        focus=values.get("focus") or "",
        question=values.get("question") or "",
        answer=values.get("answer") or "",
        source=values.get("source"),
        kind=values.get("kind"),
    )


def load_jsonl(path: Path) -> list[Record]:
    """Lee `entries.jsonl` (sin fuente ni tipo)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [
        make_record(f"{path.name}:{number}", json.loads(line))
        for number, line in enumerate(lines, start=1)
        if line.strip()
    ]


def load_records(path: Path) -> list[Record]:
    """Lee un archivo según su extensión."""
    return load_jsonl(path) if path.suffix == ".jsonl" else load_csv(path)


def load_source_ids(path: Path) -> set[str] | None:
    """Ids del catálogo de fuentes (primera columna de sus tablas); None si no existe."""
    if not path.is_file():
        return None
    return set(SOURCE_ID_PATTERN.findall(path.read_text(encoding="utf-8")))


def record_errors(record: Record, source_ids: set[str] | None) -> list[str]:
    """Errores de un registro aislado."""
    errors = []
    if record.focus not in FOCUS_VALUES:
        errors.append(f"enfoque inválido {record.focus!r}")
    if record.kind is not None and record.kind not in TYPE_VALUES:
        errors.append(f"tipo inválido {record.kind!r} (usa general o escenario)")
    is_draft = record.source is not None  # la base heredada tiene respuestas más cortas
    if is_draft and not MIN_ANSWER_CHARS <= len(record.answer) <= MAX_ANSWER_CHARS:
        errors.append(f"respuesta de {len(record.answer)} caracteres")
    errors += [
        f"término prohibido ({name})"
        for name, rx in FORBIDDEN_PATTERNS.items()
        if rx.search(record.answer)
    ]
    return errors + source_errors(record, source_ids)


def source_errors(record: Record, source_ids: set[str] | None) -> list[str]:
    """Errores de la columna Fuente (solo en los borradores que la traen)."""
    if record.source is None:
        return []
    cited = [part.strip() for part in record.source.split(";") if part.strip()]
    if not cited:
        return ["sin fuente"]
    if source_ids is None:
        return []
    return [f"fuente fuera del catálogo: {s}" for s in cited if s not in source_ids]


def tokens(text: str) -> frozenset[str]:
    """Palabras de una pregunta, en minúsculas, para comparar parecidos."""
    return frozenset(w for w in re.findall(r"\w+", text.casefold()) if len(w) >= MIN_TOKEN_CHARS)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Proporción de palabras compartidas entre dos preguntas."""
    return len(a & b) / len(a | b) if a and b else 0.0


def duplicate_findings(records: list[Record], base: list[Record], report: Report) -> None:
    """Marca preguntas repetidas (error) o casi iguales (aviso), en el lote y frente a la base."""
    seen: dict[str, str] = {r.question.casefold(): r.origin for r in base}
    known: list[tuple[str, frozenset[str]]] = [(r.origin, tokens(r.question)) for r in base]
    for record in records:
        key = record.question.casefold()
        if key in seen:
            report.errors.append(f"{record.origin}: pregunta repetida ({seen[key]})")
            continue
        words = tokens(record.question)
        close = next((o for o, t in known if jaccard(words, t) >= NEAR_DUPLICATE_JACCARD), None)
        if close:
            report.warnings.append(f"{record.origin}: pregunta casi igual a {close}")
        seen[key] = record.origin
        known.append((record.origin, words))


def quota_warnings(records: Iterable[Record]) -> list[str]:
    """Avisos por categoría: proporción de Solucionar y de preguntas generales."""
    by_category: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        by_category[record.category].append(record)
    warnings = []
    for category, group in sorted(by_category.items()):
        solve = sum(r.focus == "Solucionar" for r in group) / len(group)
        if not SOLVE_SHARE_RANGE[0] <= solve <= SOLVE_SHARE_RANGE[1]:
            warnings.append(f"{category}: {solve:.0%} Solucionar (cuota 70 %)")
        kinds = [r.kind for r in group if r.kind is not None]
        if kinds and kinds.count("general") / len(kinds) < MIN_GENERAL_SHARE:
            warnings.append(
                f"{category}: {kinds.count('general') / len(kinds):.0%} preguntas generales"
            )
    return warnings


def check(records: list[Record], base: list[Record], source_ids: set[str] | None) -> Report:
    """Aplica todas las revisiones a un conjunto de registros."""
    report = Report()
    for record in records:
        report.errors += [f"{record.origin}: {e}" for e in record_errors(record, source_ids)]
    duplicate_findings(records, base, report)
    report.warnings += quota_warnings(records)
    return report


def summary(records: Iterable[Record]) -> list[str]:
    """Líneas del resumen por categoría: registros, Solucionar/Indagar y generales."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        counts[record.category].update([record.focus, f"tipo:{record.kind}"])
    return [
        f"{sum(c[f] for f in FOCUS_VALUES):4d}  S/I {c['Solucionar']}/{c['Indagar']}"
        f"  generales {c['tipo:general']}  {category}"
        for category, c in sorted(counts.items())
    ]


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Punto de entrada: imprime el resumen, los avisos y los errores."""
    args = parse_args(argv)
    records = [r for path in args.files for r in load_records(path)]
    checked = {p.resolve() for p in args.files}
    base = (
        [] if args.base.resolve() in checked or not args.base.is_file() else load_records(args.base)
    )
    report = check(records, base, load_source_ids(args.sources))
    print("\n".join(summary(records)))
    for title, lines in (("Avisos", report.warnings), ("Errores", report.errors)):
        print(f"\n{title}: {len(lines)}")
        print("\n".join(f"  - {line}" for line in lines))
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
