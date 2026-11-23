"""Acceso a la atención en el turno: un aviso de barrera o una pregunta de contexto (HU-18).

Se aplica **después** de que el turno decidió alarma, alcance, evidencia y respuesta
(ADR 0023). Como mucho agrega un aviso fijo o una pregunta fija, y lo registra en la traza.
Nunca cambia la alarma, el alcance, la evidencia, el hilo ni la ruta: la variante del aviso
(consulta o urgencias) se **lee** de lo que el turno ya decidió.

Responde a lo que la persona dice en **este** mensaje: una barrera mencionada antes no
vuelve a generar su aviso, la cascada del colesterol no es un formulario (una sola pregunta
por hilo, solo si sigue a algo que la persona contó y no pidió un dato concreto) y en una
urgencia nunca se pregunta.

- `observar`: solo registra en la traza lo que se habría mostrado.
- `activo`: lo muestra, pero **solo** si el equipo aprobó ese texto en el catálogo.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from cardio_materno.application.alarm_policy import REPLY_SEPARATOR
from cardio_materno.domain.care_access import (
    CareAccessCatalog,
    CareFact,
    FactGroup,
    Notice,
    NoticeKind,
    NoticeRoute,
    cascade_gap,
    cascade_state,
    contradictions,
    detect_barriers,
    follow_up_step,
    mentions_cholesterol,
    ordered_facts,
)
from cardio_materno.domain.trace import CareAccessTrace

# Marcador del prompt de análisis v9 que se reemplaza por la tabla de códigos del catálogo.
CARE_ACCESS_PLACEHOLDER = "{{DATOS_DE_ACCESO}}"
FACT_LINE_TEMPLATE = "- {code}: {label}{examples}"
FACT_EXAMPLES_TEMPLATE = " (ej.: {examples})"
EXAMPLES_SEPARATOR = "; "
# Encabezado fijo de un aviso administrativo: lo distingue de la orientación con evidencia.
ADMINISTRATIVE_HEADING = "Sobre trámites y acceso a la atención (no es una recomendación médica):"
QUESTION_MARK = "?"
OPENING_QUESTION_MARK = "¿"
SENTENCE_ENDS = (".", "!", "?", "\n")


class CareAccessActivation(StrEnum):
    """Cómo participa la regla de acceso (`CARE_ACCESS_MODE`, ADR 0023)."""

    OFF = "apagado"
    OBSERVE = "observar"
    ACTIVE = "activo"


@dataclass(frozen=True)
class AccessTurn:
    """Lo que la regla de acceso lee del turno ya decidido.

    Attributes:
        message: Mensaje de la persona en este turno.
        earlier_messages: Mensajes anteriores de la persona en el hilo.
        assistant_texts: Respuestas recientes del asistente en el hilo (para no repetir).
        analysis_facts: Códigos que marcó el análisis en este turno.
        route: Variante del aviso según la ruta del turno (None si el turno no orienta).
        has_question: True si la respuesta ya trae una pregunta.
        informational: True si la persona pidió un dato concreto (no se le pregunta nada).
    """

    message: str
    earlier_messages: tuple[str, ...] = ()
    assistant_texts: tuple[str, ...] = ()
    analysis_facts: tuple[str, ...] = ()
    route: NoticeRoute | None = None
    has_question: bool = False
    informational: bool = False


def decide_care_access(turn: AccessTurn, catalog: CareAccessCatalog) -> CareAccessTrace:
    """Datos declarados, aviso y pregunta del turno: como mucho un aviso **o** una pregunta.

    Args:
        turn: Lo que ya decidió el turno.
        catalog: Catálogo de acceso.

    Returns:
        La decisión, sin aplicar (`applied` en False).
    """
    stated = detect_barriers((turn.message,), catalog)
    interpreted = supported_interpretations(turn, stated, catalog)
    facts = ordered_facts((*stated, *interpreted), catalog)
    state = cascade_state(facts, catalog)
    decision = CareAccessTrace(
        stated_facts=ordered_facts(stated, catalog),
        interpreted_facts=ordered_facts(interpreted, catalog),
        contradictions=contradictions(state),
        route=str(turn.route) if turn.route is not None else "",
    )
    notice = choose_notice(facts, turn, catalog)
    if notice is not None:
        return replace(decision, notice=notice.code, pending_approval=not notice.approved)
    return with_question(decision, facts, turn, catalog)


def supported_interpretations(
    turn: AccessTurn, stated: Sequence[str], catalog: CareAccessCatalog
) -> tuple[str, ...]:
    """Códigos del análisis que se aceptan como interpretación de lo que dijo la persona.

    Un código de la cascada solo se acepta si la persona habló del colesterol en el hilo:
    así el modelo no puede atribuirle un dato clínico sobre un tema que no mencionó.
    """
    on_topic = mentions_cholesterol((turn.message, *turn.earlier_messages), catalog)
    accepted = []
    for code in turn.analysis_facts:
        fact = catalog.fact(code)
        if fact is None or code in stated:
            continue
        if fact.group is FactGroup.CASCADE and not on_topic:
            continue
        accepted.append(code)
    return tuple(accepted)


def choose_notice(
    facts: Sequence[str], turn: AccessTurn, catalog: CareAccessCatalog
) -> Notice | None:
    """Primer aviso con texto para la ruta que no se haya dicho ya en el hilo.

    Las barreras van primero. La brecha de la cascada solo se avisa en una consulta y si
    este mensaje habla del colesterol.
    """
    if turn.route is None:
        return None
    codes = [code for code in facts if code in catalog.notices]
    gap = cascade_gap(cascade_state(facts, catalog))
    on_topic = mentions_cholesterol((turn.message,), catalog)
    if gap and on_topic and turn.route is NoticeRoute.CONSULTATION:
        codes.append(gap)
    for code in codes:
        notice = catalog.notices.get(code)
        text = notice.texts.get(turn.route) if notice else None
        if notice and text and not already_said(text, turn.assistant_texts):
            return notice
    return None


def with_question(
    decision: CareAccessTrace, facts: Sequence[str], turn: AccessTurn, catalog: CareAccessCatalog
) -> CareAccessTrace:
    """Agrega la pregunta de contexto de la cascada, si corresponde.

    Solo cuando este mensaje habla del colesterol, la persona no pidió un dato concreto, el
    turno no es una urgencia, la respuesta no trae otra pregunta y en el hilo todavía no se
    hizo ninguna pregunta de la cascada.
    """
    blocked = turn.has_question or turn.informational or turn.route is NoticeRoute.EMERGENCY
    if blocked or not mentions_cholesterol((turn.message,), catalog):
        return decision
    asked = any(already_said(q.text, turn.assistant_texts) for q in catalog.questions.values())
    step = follow_up_step(cascade_state(facts, catalog))
    question = catalog.questions.get(step) if step is not None and not asked else None
    if question is None:
        return decision
    return replace(decision, question=str(question.step), pending_approval=not question.approved)


def already_said(text: str, assistant_texts: Sequence[str]) -> bool:
    """True si el texto ya está en una respuesta reciente del asistente."""
    return any(text in said for said in assistant_texts)


def shown_text(decision: CareAccessTrace, catalog: CareAccessCatalog) -> str:
    """Texto fijo que corresponde a la decisión ("" si no decidió nada)."""
    notice = catalog.notices.get(decision.notice)
    if notice is not None:
        return notice.texts.get(NoticeRoute(decision.route), "")
    question = next((q for q in catalog.questions.values() if q.step == decision.question), None)
    return question.text if question else ""


def render_care_access(reply: str, decision: CareAccessTrace, catalog: CareAccessCatalog) -> str:
    """Respuesta con el aviso (antes de la pregunta final) o con la pregunta de contexto."""
    text = shown_text(decision, catalog)
    if not text:
        return reply
    notice = catalog.notices.get(decision.notice)
    if notice is None:
        return f"{reply.rstrip()}{REPLY_SEPARATOR}{text}"
    if notice.kind is NoticeKind.ADMINISTRATIVE:
        text = f"{ADMINISTRATIVE_HEADING}\n{text}"
    return insert_before_final_question(reply, text)


def insert_before_final_question(reply: str, notice: str) -> str:
    """Pone el aviso antes de la pregunta final, para que el mensaje siga terminando en ella.

    Si la respuesta no termina en pregunta, el aviso va al final.
    """
    text = reply.rstrip()
    if not text.endswith(QUESTION_MARK):
        return REPLY_SEPARATOR.join(part for part in (text, notice) if part)
    start = final_question_start(text)
    head, question = text[:start].rstrip(), text[start:].lstrip()
    return REPLY_SEPARATOR.join(part for part in (head, notice, question) if part)


def final_question_start(text: str) -> int:
    """Posición donde empieza la frase de la pregunta final (0 si todo el texto es esa frase)."""
    opening = text.rfind(OPENING_QUESTION_MARK)
    limit = opening if opening >= 0 else len(text) - 1
    return max(text.rfind(mark, 0, limit) for mark in SENTENCE_ENDS) + 1


def render_care_access_prompt(template: str, catalog: CareAccessCatalog) -> str:
    """Inserta en el prompt de análisis v9 la tabla de códigos de acceso del catálogo."""
    lines = "\n".join(format_fact_line(fact) for fact in catalog.facts)
    return template.replace(CARE_ACCESS_PLACEHOLDER, lines)


def format_fact_line(fact: CareFact) -> str:
    """Línea de un código: "- CÓDIGO: significado (ej.: …)"."""
    examples = EXAMPLES_SEPARATOR.join(fact.examples)
    return FACT_LINE_TEMPLATE.format(
        code=fact.code,
        label=fact.label,
        examples=FACT_EXAMPLES_TEMPLATE.format(examples=examples) if examples else "",
    )
