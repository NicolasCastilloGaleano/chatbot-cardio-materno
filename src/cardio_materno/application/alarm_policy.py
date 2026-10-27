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
    rules_for_codes,
)
from cardio_materno.domain.conversation import Domain

REPLY_SEPARATOR = "\n\n"
# Marcador del prompt de sistema que se reemplaza por la lista de signos del catálogo.
ALARM_SIGNS_PLACEHOLDER = "{{SIGNOS_DE_ALARMA}}"
NO_SIGNS_TEXT = "(no hay signos de alarma cargados)"
SIGN_LINE_TEMPLATE = "- {code}: {sign}{examples}"
SIGN_EXAMPLES_TEMPLATE = " (ej.: {examples})"
EXAMPLES_SEPARATOR = "; "
# Recordatorio de una regla ya avisada en el hilo que el filtro 2 vuelve a encontrar (ADR 0018).
REMINDER_MESSAGES = {
    Severity.IMMEDIATE: (
        "⚠️ Recuerda lo que te indiqué: por lo que me contaste, lo indicado es acudir al "
        "servicio de urgencias más cercano o llamar a la línea 123."
    ),
    Severity.PRIORITY: (
        "⚠️ Recuerda lo que te indiqué: por lo que me contaste, conviene que consultes pronto "
        "con el personal de salud."
    ),
}


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
        return self._decision(rules, origin)

    @property
    def codes(self) -> tuple[str, ...]:
        """Códigos de signos del catálogo, sin repetir y en orden (ADR 0012)."""
        return tuple(dict.fromkeys(rule.code for rule in self._rules if rule.code))

    def evaluate_codes(
        self, codes: Sequence[str], exclude: Collection[str] = ()
    ) -> AlarmDecision | None:
        """Cruce exacto de los códigos marcados por el análisis con las reglas (ADR 0012).

        Args:
            codes: Códigos de signos marcados en `reported_signs`.
            exclude: IDs de reglas ya detectadas que no se deben repetir.

        Returns:
            La decisión con origen `agente_codigo`, o None si no se activa ninguna regla.
        """
        rules = [rule for rule in rules_for_codes(codes, self._rules) if rule.id not in exclude]
        return self._decision(rules, AlertOrigin.AGENT_CODE)

    def split_alerted(
        self, decisions: Sequence[AlarmDecision], alerted: Collection[str]
    ) -> tuple[tuple[AlarmDecision, ...], tuple[AlarmRule, ...]]:
        """Separa las reglas ya avisadas en el hilo de las nuevas (ADR 0018).

        Args:
            decisions: Decisiones del filtro 2 del turno.
            alerted: IDs de las reglas con alerta registrada en el hilo activo.

        Returns:
            Las decisiones solo con reglas nuevas (cada una con el mensaje de su regla más
            grave) y las reglas ya avisadas, que solo se recuerdan.
        """
        fresh: list[AlarmDecision] = []
        reminded: list[AlarmRule] = []
        for decision in decisions:
            new_rules = [rule for rule in decision.rules if rule.id not in alerted]
            reminded.extend(rule for rule in decision.rules if rule.id in alerted)
            rebuilt = self._decision(new_rules, decision.origin)
            fresh.extend([rebuilt] if rebuilt is not None else [])
        return tuple(fresh), tuple(reminded)

    def _decision(self, rules: list[AlarmRule], origin: AlertOrigin) -> AlarmDecision | None:
        """Decisión con el mensaje fijo de la regla más grave, o None si no hay reglas."""
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
    """Tabla de signos para el prompt: código, nombre y ejemplos coloquiales (ADR 0012).

    Las reglas sin código se listan solo con su nombre.
    """
    lines = list(dict.fromkeys(format_sign_line(rule) for rule in policy.rules))
    return "\n".join(lines) if lines else NO_SIGNS_TEXT


def format_sign_line(rule: AlarmRule) -> str:
    """Línea de un signo: "- CÓDIGO: nombre (ej.: …)"."""
    examples = EXAMPLES_SEPARATOR.join(rule.examples)
    return SIGN_LINE_TEMPLATE.format(
        code=rule.code or rule.id,
        sign=rule.sign,
        examples=SIGN_EXAMPLES_TEMPLATE.format(examples=examples) if examples else "",
    )


def reminder_for(reminded: Sequence[AlarmRule], decisions: Sequence[AlarmDecision]) -> str | None:
    """Recordatorio corto de las reglas ya avisadas (ADR 0018).

    No hace falta si el turno ya muestra el aviso de una alarma nueva igual o más grave.

    Args:
        reminded: Reglas ya avisadas en el hilo que el filtro 2 volvió a encontrar.
        decisions: Alarmas nuevas del turno, cuyo mensaje fijo se mostrará completo.

    Returns:
        El texto del recordatorio según la gravedad, o None si no hace falta.
    """
    if not reminded:
        return None
    severity = most_severe(reminded).severity
    if (
        decisions
        and SEVERITY_RANK[most_severe_decision(decisions).severity] >= SEVERITY_RANK[severity]
    ):
        return None
    return REMINDER_MESSAGES[severity]
