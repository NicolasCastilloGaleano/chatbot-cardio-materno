"""Búsqueda léxica BM25 en memoria (portada del piloto; la base cabe holgada en RAM)."""

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence

from cardio_materno.domain.alarms import normalize_text

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
WORD_PATTERN = re.compile(r"\w+")
# Palabras cortas del español que no aportan señal de búsqueda.
STOPWORDS = frozenset(
    {
        "que", "con", "para", "por", "una", "uno", "los", "las", "del", "como", "mas", "pero",
        "sus", "este", "esta", "esto", "ese", "esa", "son", "hay", "muy", "sin", "sobre",
        "cuando", "desde", "tiene", "tengo", "puede", "debo", "hace", "entre", "porque", "cual",
        "cuales", "donde",
    }
)  # fmt: skip


def tokenize(text: str, min_chars: int) -> list[str]:
    """Divide un texto normalizado en términos útiles (sin palabras vacías ni números)."""
    return [
        token
        for token in WORD_PATTERN.findall(normalize_text(text))
        if len(token) >= min_chars and token not in STOPWORDS and not token.isdigit()
    ]


class Bm25Index:
    """Índice BM25 clásico sobre documentos ya tokenizados."""

    def __init__(
        self, documents: Mapping[str, Sequence[str]], k1: float = DEFAULT_K1, b: float = DEFAULT_B
    ) -> None:
        """Construye el índice.

        Args:
            documents: Identificador del documento → términos.
            k1: Saturación de la frecuencia del término.
            b: Peso de la normalización por longitud.
        """
        self._k1, self._b = k1, b
        self._frequencies = {doc_id: Counter(tokens) for doc_id, tokens in documents.items()}
        self._lengths = {doc_id: len(tokens) for doc_id, tokens in documents.items()}
        self._average = sum(self._lengths.values()) / len(self._lengths) if self._lengths else 0.0
        self._idf = inverse_document_frequencies(documents)

    def rank(self, query_tokens: Sequence[str], limit: int) -> list[str]:
        """Devuelve los documentos con puntaje > 0, de mayor a menor, hasta `limit`."""
        unique = set(query_tokens)
        scores = Counter({doc_id: self._score(doc_id, unique) for doc_id in self._frequencies})
        return [doc_id for doc_id, score in scores.most_common(limit) if score > 0]

    def _score(self, doc_id: str, query_tokens: set[str]) -> float:
        """Puntaje BM25 de un documento para los términos de la consulta."""
        frequencies = self._frequencies[doc_id]
        norm = self._k1 * (1 - self._b + self._b * self._lengths[doc_id] / (self._average or 1))
        score = 0.0
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if frequency:
                score += self._idf[token] * frequency * (self._k1 + 1) / (frequency + norm)
        return score


def inverse_document_frequencies(documents: Mapping[str, Sequence[str]]) -> dict[str, float]:
    """IDF suavizado de cada término (variante BM25 siempre positiva)."""
    counts: Counter[str] = Counter()
    for tokens in documents.values():
        counts.update(set(tokens))
    total = len(documents)
    return {
        token: math.log(1 + (total - count + 0.5) / (count + 0.5))
        for token, count in counts.items()
    }
