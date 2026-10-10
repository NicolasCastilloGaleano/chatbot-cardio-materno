"""Política de alarmas: evalúa textos con el catálogo y decide el mensaje fijo (ADR 0007)."""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from cardio_materno.domain.alarms import (
    SEVERITY_RANK,
    AlarmRule,
    AlertOrigin,
    Severity,
    detect_alarms,
    most_severe,
)
from cardio_materno.domain.conversation import Domain

REPLY_SEPARATOR = "\n\n"
# Marcador del prompt de sistema que se reemplaza por la lista de signos del catálogo.
ALARM_SIGNS_PLACEHOLDER = "{{SIGNOS_DE_ALARMA}}"
NO_SIGNS_TEXT = "(no hay signos de alarma cargados)"


@dataclass(frozen=True)
class AlarmDecision:
    """Resultado de evaluar un texto contra el catálogo.

    Attributes:
        rules: Reglas activadas.
        origin: Texto donde se detectaron (usuario o agente).
        message: Mensaje fijo de la regla más grave.
    """

    rules: tuple[AlarmRule, ...]
    origin: AlertOrigin
    message: str

    @property
    def primary_rule(self) -> AlarmRule:
        """Regla más grave de la decisión."""
        return most_severe(self.rules)

    @property
    def severity(self) -> Severity:
        """Gravedad máxima de las reglas activadas."""
        return self.primary_rule.severity

    @property
    def is_immediate(self) -> bool:
        """Indica si exige atención de urgencia inmediata."""
        return self.severity is Severity.IMMEDIATE

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Identificadores de las reglas activadas."""
        return tuple(rule.id for rule in self.rules)

    @property
    def domain(self) -> Domain:
        """Dominio de salud de la regla más grave."""
        return self.primary_rule.domain


class AlarmPolicy:
    """Evalúa textos con el catálogo de reglas y asocia el mensaje fijo correspondiente."""

    def __init__(self, rules: Sequence[AlarmRule], messages: Mapping[str, str]) -> None:
        """Crea la política.

        Args:
            rules: Catálogo de reglas (ya validado).
            messages: Mensajes fijos por identificador.
        """
        self._rules = tuple(rules)
        self._messages = dict(messages)

    @property
    def rules(self) -> tuple[AlarmRule, ...]:
        """Reglas del catálogo."""
        return self._rules

    def evaluate(
        self, texts: Sequence[str], origin: AlertOrigin, exclude: Collection[str] = ()
    ) -> AlarmDecision | None:
        """Evalúa textos y devuelve la decisión, o None si no se activa ninguna regla.

        Args:
            texts: Textos a revisar.
            origin: De dónde provienen los textos.
            exclude: IDs de reglas ya detectadas que no se deben repetir.

        Returns:
            La decisión con las reglas activadas y el mensaje fijo, o None.
        """
        rules = [rule for rule in detect_alarms(texts, self._rules) if rule.id not in exclude]
        if not rules:
            return None
        message = self._messages[most_severe(rules).message_id]
        return AlarmDecision(tuple(rules), origin, message)


def compose_reply(decisions: Sequence[AlarmDecision], agent_reply: str | None) -> str:
    """Arma la respuesta final según las alarmas detectadas.

    - Sin alarmas: la respuesta del agente.
    - Con una urgencia inmediata, o sin respuesta del agente: solo el mensaje fijo.
    - Con una consulta prioritaria: el mensaje fijo seguido de la respuesta del agente.

    Args:
        decisions: Decisiones de alarma del turno (puede estar vacía).
        agent_reply: Respuesta del agente, o None si no se consultó o falló.

    Returns:
        Texto que se muestra al usuario.

    Raises:
        ValueError: Si no hay alarmas ni respuesta del agente.
    """
    if not decisions:
        if agent_reply is None:
            raise ValueError("No hay respuesta del agente ni alarma que mostrar")
        return agent_reply
    notice = most_severe_decision(decisions).message
    if agent_reply is None or any(decision.is_immediate for decision in decisions):
        return notice
    return f"{notice}{REPLY_SEPARATOR}{agent_reply}"


def most_severe_decision(decisions: Sequence[AlarmDecision]) -> AlarmDecision:
    """Decisión más grave; ante empate, la primera (la del usuario)."""
    return max(decisions, key=lambda decision: SEVERITY_RANK[decision.severity])


def render_system_prompt(template: str, policy: AlarmPolicy) -> str:
    """Inserta en el prompt la lista de nombres de signos de alarma del catálogo.

    Así el agente puede usar el nombre exacto de cada signo en `reported_symptoms`, y el
    filtro 2 lo reconoce sin depender de su redacción (puente hacia B-015).

    Args:
        template: Prompt de sistema con el marcador `{{SIGNOS_DE_ALARMA}}`.
        policy: Política con las reglas del catálogo.

    Returns:
        El prompt con la lista de signos (o el prompt sin cambios si no tiene marcador).
    """
    return template.replace(ALARM_SIGNS_PLACEHOLDER, format_sign_list(policy))


def format_sign_list(policy: AlarmPolicy) -> str:
    """Lista con viñetas de los nombres de signos, sin repetir y en el orden del catálogo."""
    signs = list(dict.fromkeys(rule.sign for rule in policy.rules))
    return "\n".join(f"- {sign}" for sign in signs) if signs else NO_SIGNS_TEXT
