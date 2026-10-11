"""Líneas de depuración de la consola: hilo, alertas, síntomas, evidencia y tiempos."""

from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ConversationThread
from cardio_materno.domain.trace import EvidenceRef, ReplyTrace, RetrievalStatus, StageTiming

SHORT_ID_LENGTH = 8
CATEGORY_MAX_CHARS = 32
THREAD_DEBUG_TEMPLATE = "[hilo {id} | {domain} | {status} | {change}{alerts}]"
ALERT_DEBUG_TEMPLATE = " | ⚠️ {rule_ids} {severity} ({origin})"
SYMPTOMS_DEBUG_TEMPLATE = "[síntomas reportados por el agente: {symptoms}]"
NO_SYMPTOMS_TEXT = "ninguno"
AGENT_NOT_CONSULTED_TEXT = "[agente no consultado: urgencia detectada en el mensaje]"
EVIDENCE_DEBUG_TEMPLATE = "[evidencia: {items} | citadas: {cited}{warning}]"
EVIDENCE_ITEM_TEMPLATE = "{label} {score:.2f} {category}"
EVIDENCE_NOT_SEARCHED_TEXT = "[evidencia: no se buscó (urgencia detectada en los síntomas)]"
EVIDENCE_CONVERSATIONAL_TEXT = "[evidencia: no se buscó (mensaje conversacional)]"
OUT_OF_SCOPE_TEMPLATE = "[fuera de alcance: {reason} · no se registra en el hilo]"
NO_REASON_TEXT = "sin motivo"
CONVERSATIONAL_SCOPE = "conversacional"
EVIDENCE_INSUFFICIENT_TEMPLATE = "[evidencia: insuficiente (mejor {best:.2f})]"
EVIDENCE_UNAVAILABLE_TEXT = "[evidencia: no disponible (RAG desactivado o sin índice)]"
UNCITED_WARNING = " | ⚠️ la respuesta no citó evidencia"
TIMINGS_DEBUG_TEMPLATE = "[tiempos: {timings}]"
TIMING_TEMPLATE = "{stage} {seconds:.1f} s"
NONE_TEXT = "ninguna"
LIST_SEPARATOR = "; "
ITEM_SEPARATOR = " | "
TIMING_SEPARATOR = " · "
NEW_THREAD_LABEL = "nuevo"
SAME_THREAD_LABEL = "continúa"


def debug_lines(result: TurnResult) -> list[str]:
    """Todas las líneas de depuración de un turno, en orden."""
    if result.out_of_scope or result.thread is None:
        return out_of_scope_lines(result.trace)
    lines = [format_thread_debug(result, result.thread), format_symptoms_debug(result.trace)]
    if result.trace is not None:
        lines.append(format_evidence_debug(result.trace))
        if result.trace.timings:
            lines.append(format_timings_debug(result.trace.timings))
    return lines


def out_of_scope_lines(trace: ReplyTrace | None) -> list[str]:
    """Líneas de un mensaje descartado por estar fuera de alcance (no se registra en el hilo)."""
    reason = (trace.scope_reason if trace else "") or NO_REASON_TEXT
    lines = [OUT_OF_SCOPE_TEMPLATE.format(reason=reason)]
    if trace is not None and trace.timings:
        lines.append(format_timings_debug(trace.timings))
    return lines


def format_thread_debug(result: TurnResult, thread: ConversationThread) -> str:
    """Estado del hilo y alertas, p. ej. "[hilo 3f2a91c0 | cardiovascular | abierto | nuevo]"."""
    return THREAD_DEBUG_TEMPLATE.format(
        id=thread.id[:SHORT_ID_LENGTH],
        domain=thread.domain,
        status=thread.status,
        change=NEW_THREAD_LABEL if result.is_new_thread else SAME_THREAD_LABEL,
        alerts="".join(format_alert_debug(alert) for alert in result.alerts),
    )


def format_alert_debug(alert: Alert) -> str:
    """Fragmento que describe una alerta."""
    return ALERT_DEBUG_TEMPLATE.format(
        rule_ids=",".join(alert.rule_ids), severity=alert.severity, origin=alert.origin
    )


def format_symptoms_debug(trace: ReplyTrace | None) -> str:
    """Síntomas que reportó el agente (filtro 2), o aviso de que no se le consultó."""
    if trace is None:
        return AGENT_NOT_CONSULTED_TEXT
    symptoms = LIST_SEPARATOR.join(trace.reported_symptoms) or NO_SYMPTOMS_TEXT
    return SYMPTOMS_DEBUG_TEMPLATE.format(symptoms=symptoms)


def format_evidence_debug(trace: ReplyTrace) -> str:
    """Evidencia ofrecida y citada, o por qué no la hubo."""
    if trace.retrieval_status is None:
        conversational = trace.scope == CONVERSATIONAL_SCOPE
        return EVIDENCE_CONVERSATIONAL_TEXT if conversational else EVIDENCE_NOT_SEARCHED_TEXT
    if trace.retrieval_status is RetrievalStatus.UNAVAILABLE:
        return EVIDENCE_UNAVAILABLE_TEXT
    if trace.retrieval_status is RetrievalStatus.INSUFFICIENT:
        return EVIDENCE_INSUFFICIENT_TEMPLATE.format(best=trace.best_score or 0.0)
    return EVIDENCE_DEBUG_TEMPLATE.format(
        items=ITEM_SEPARATOR.join(format_evidence_item(ref) for ref in trace.evidence),
        cited=",".join(trace.cited_evidence) or NONE_TEXT,
        warning=UNCITED_WARNING if trace.uncited else "",
    )


def format_evidence_item(ref: EvidenceRef) -> str:
    """Etiqueta, puntaje y categoría (abreviada) de un registro de evidencia."""
    category = ref.category[:CATEGORY_MAX_CHARS]
    return EVIDENCE_ITEM_TEMPLATE.format(label=ref.label, score=ref.score, category=category)


def format_timings_debug(timings: tuple[StageTiming, ...]) -> str:
    """Duración de cada etapa, p. ej. "[tiempos: análisis 3.1 s · RAG 0.4 s · respuesta 6.2 s]"."""
    parts = (TIMING_TEMPLATE.format(stage=t.stage, seconds=t.seconds) for t in timings)
    return TIMINGS_DEBUG_TEMPLATE.format(timings=TIMING_SEPARATOR.join(parts))
