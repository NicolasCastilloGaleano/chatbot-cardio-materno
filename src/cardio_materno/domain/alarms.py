"""Reglas deterministas de signos de alarma (HU-03, HU-04, ADR 0004, ADR 0007).

Las reglas se aplican sobre texto normalizado (minúsculas, sin tildes y sin espacios
repetidos). Criterio conservador: no se interpretan negaciones; ante la duda se
prefiere un falso positivo a dejar pasar una alarma.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from cardio_materno.domain.conversation import Domain

COMBINING_MARK_CATEGORY = "Mn"


class Severity(StrEnum):
    """Gravedad de un signo de alarma."""

    IMMEDIATE = "urgencia_inmediata"
    PRIORITY = "consulta_prioritaria"


# Orden de gravedad: mayor número = más grave.
SEVERITY_RANK = {Severity.PRIORITY: 1, Severity.IMMEDIATE: 2}


class AlertOrigin(StrEnum):
    """Texto en el que se detectó la alarma."""

    USER = "usuario"
    AGENT = "agente"


@dataclass(frozen=True)
class AlarmRule:
    """Regla clínica determinista (definida en el catálogo `knowledge/alarm_rules.json`).

    Attributes:
        id: Identificador trazable (p. ej., RN-MI-01).
        domain: Dominio de salud de la regla.
        population: Población a la que aplica (gestante, recién nacido, adulto…).
        sign: Descripción del signo de alarma.
        severity: Gravedad del signo.
        patterns: Expresiones regulares ya compiladas sobre texto normalizado.
        message_id: Mensaje fijo que se muestra al activarse.
        source: Fuente clínica de la regla.
    """

    id: str
    domain: Domain
    population: str
    sign: str
    severity: Severity
    patterns: tuple[re.Pattern[str], ...]
    message_id: str
    source: str

    def matches(self, normalized_text: str) -> bool:
        """Indica si el texto normalizado contiene el nombre del signo o algún patrón.

        El nombre del signo funciona como término canónico: el prompt le pide al agente
        usarlo en `reported_symptoms` (puente hacia B-015, códigos cerrados).
        """
        if normalize_text(self.sign) in normalized_text:
            return True
        return any(pattern.search(normalized_text) for pattern in self.patterns)


@dataclass(frozen=True)
class Alert:
    """Alerta registrada en un hilo.

    Attributes:
        rule_ids: Reglas que se activaron.
        severity: Gravedad máxima de esas reglas.
        origin: Si se detectó en el mensaje del usuario o en los síntomas reportados por el agente.
        created_at: Momento del registro.
    """

    rule_ids: tuple[str, ...]
    severity: Severity
    origin: AlertOrigin
    created_at: datetime


def strip_accents(text: str) -> str:
    """Elimina tildes y diéresis (á→a, ü→u, ñ→n)."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != COMBINING_MARK_CATEGORY)


def normalize_text(text: str) -> str:
    """Normaliza un texto para comparar con los patrones: minúsculas, sin tildes, un espacio."""
    return " ".join(strip_accents(text).lower().split())


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compila un patrón del catálogo sin tildes e ignorando mayúsculas.

    Raises:
        re.error: Si el patrón no es una expresión regular válida.
    """
    return re.compile(strip_accents(pattern), re.IGNORECASE)


def detect_alarms(texts: Iterable[str], rules: Sequence[AlarmRule]) -> list[AlarmRule]:
    """Devuelve las reglas que se activan en alguno de los textos, en el orden del catálogo.

    Args:
        texts: Textos a revisar (mensaje del usuario o síntomas reportados).
        rules: Catálogo de reglas.

    Returns:
        Reglas activadas (vacío si no hay alarma).
    """
    normalized = [normalize_text(text) for text in texts if text.strip()]
    return [rule for rule in rules if any(rule.matches(text) for text in normalized)]


def most_severe(rules: Sequence[AlarmRule]) -> AlarmRule:
    """Devuelve la regla más grave; ante empate, la primera.

    Raises:
        ValueError: Si la lista está vacía.
    """
    if not rules:
        raise ValueError("Se necesita al menos una regla")
    return max(rules, key=lambda rule: SEVERITY_RANK[rule.severity])
