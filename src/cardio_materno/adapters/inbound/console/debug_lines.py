"""Líneas de depuración de la consola: hilo, alertas, síntomas, evidencia y tiempos."""

from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ConversationThread
from cardio_materno.domain.trace import (
    EvidenceRef,
    GroundingCheck,
    ReplyTrace,
    RetrievalStatus,
    StageTiming,
)

SHORT_ID_LENGTH = 8
CATEGORY_MAX_CHARS = 32
THREAD_DEBUG_TEMPLATE = "[hilo {id} | {domain} | {status} | {change}{alerts}]"
ALERT_DEBUG_TEMPLATE = " | ⚠️ {rule_ids} {severity} ({origin})"
SYMPTOMS_DEBUG_TEMPLATE = "[síntomas reportados por el agente: {symptoms}]"
UNSTATED_DEBUG_TEMPLATE = "[⚠️ datos que la persona no escribió: {symptoms}]"
SEARCH_DEBUG_TEMPLATE = "[búsqueda: {query}{widened}]"
WIDENED_SEARCH_NOTE = " · ampliada a los dos dominios"
SIGNS_DEBUG_TEMPLATE = "[signos marcados: {codes}]"
NO_SYMPTOMS_TEXT = "ninguno"
AGENT_NOT_CONSULTED_TEXT = "[agente no consultado: urgencia detectada en el mensaje]"
EVIDENCE_DEBUG_TEMPLATE = "[evidencia: {items} | citadas: {cited}{warning}]"
EVIDENCE_ITEM_TEMPLATE = "{label} {score:.2f} {category}"
EVIDENCE_NOT_SEARCHED_TEXT = "[evidencia: no se buscó (urgencia detectada en los síntomas)]"
EVIDENCE_CONVERSATIONAL_TEXT = "[evidencia: no se buscó (mensaje conversacional)]"
OUT_OF_SCOPE_TEMPLATE = "[fuera de alcance: {reason} · no se registra en el hilo]"
NO_REASON_TEXT = "sin motivo"
UNRECORDED_CONVERSATIONAL_TEXT = "[sin hilo: mensaje conversacional · no se registra]"
CONVERSATIONAL_SCOPE = "conversacional"
EVIDENCE_INSUFFICIENT_TEMPLATE = "[evidencia: insuficiente (mejor {best:.2f})]"
EVIDENCE_UNAVAILABLE_TEXT = "[evidencia: no disponible (RAG desactivado o sin índice)]"
UNCITED_WARNING = " | ⚠️ la respuesta no citó evidencia"
GROUNDING_DEBUG_TEMPLATE = "[respaldo: {supported}/{total} frases{literal}]"
GROUNDING_LITERAL_TEXT = " · texto literal del registro"
ABSTENTION_DEBUG_TEXT = "[respaldo: abstención sin LLM (sin evidencia suficiente)]"
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
    if result.out_of_scope:
        return out_of_scope_lines(result.trace)
    if result.thread is None:
        return unrecorded_lines(result.trace)
    lines = [format_thread_debug(result, result.thread), format_symptoms_debug(result.trace)]
    if result.trace is not None:
        lines.extend(trace_lines(result.trace))
    return lines


def trace_lines(trace: ReplyTrace) -> list[str]:
    """Líneas de la traza: datos no dichos, búsqueda, evidencia, respaldo y tiempos."""
    optional = [
        SIGNS_DEBUG_TEMPLATE.format(codes=", ".join(trace.reported_signs))
        if trace.reported_signs
        else "",
        format_unstated_debug(trace),
        format_search_debug(trace),
        format_evidence_debug(trace),
        format_grounding_debug(trace),
        format_timings_debug(trace.timings) if trace.timings else "",
    ]
    return [line for line in optional if line]


def format_unstated_debug(trace: ReplyTrace) -> str:
    """Aviso de síntomas con datos que la persona no escribió, o "" si no hay."""
    if not trace.unstated_symptoms:
        return ""
    return UNSTATED_DEBUG_TEMPLATE.format(symptoms=LIST_SEPARATOR.join(trace.unstated_symptoms))


def out_of_scope_lines(trace: ReplyTrace | None) -> list[str]:
    """Líneas de un mensaje descartado por estar fuera de alcance (no se registra en el hilo)."""
    reason = (trace.scope_reason if trace else "") or NO_REASON_TEXT
    lines = [OUT_OF_SCOPE_TEMPLATE.format(reason=reason)]
    if trace is not None and trace.timings:
        lines.append(format_timings_debug(trace.timings))
    return lines


def unrecorded_lines(trace: ReplyTrace | None) -> list[str]:
    """Líneas de un mensaje conversacional sin hilo activo (no se registra)."""
    lines = [UNRECORDED_CONVERSATIONAL_TEXT]
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


def format_grounding_debug(trace: ReplyTrace) -> str:
    """Resultado de la verificación del respaldo, o "" si no aplica (ADR 0010)."""
    if trace.grounding is not None:
        return format_grounding_check(trace.grounding)
    searched_without_evidence = trace.retrieval_status in (
        RetrievalStatus.INSUFFICIENT,
        RetrievalStatus.UNAVAILABLE,
    )
    return ABSTENTION_DEBUG_TEXT if searched_without_evidence else ""


def format_grounding_check(check: GroundingCheck) -> str:
    """Frases mostradas de las redactadas y si se usó el texto literal del registro."""
    return GROUNDING_DEBUG_TEMPLATE.format(
        supported=check.supported,
        total=check.total,
        literal=GROUNDING_LITERAL_TEXT if check.literal else "",
    )


def format_evidence_item(ref: EvidenceRef) -> str:
    """Etiqueta, puntaje y categoría (abreviada) de un registro de evidencia."""
    category = ref.category[:CATEGORY_MAX_CHARS]
    return EVIDENCE_ITEM_TEMPLATE.format(label=ref.label, score=ref.score, category=category)


def format_timings_debug(timings: tuple[StageTiming, ...]) -> str:
    """Duración de cada etapa, p. ej. "[tiempos: análisis 3.1 s · RAG 0.4 s · respuesta 6.2 s]"."""
    parts = (TIMING_TEMPLATE.format(stage=t.stage, seconds=t.seconds) for t in timings)
    return TIMINGS_DEBUG_TEMPLATE.format(timings=TIMING_SEPARATOR.join(parts))


def format_search_debug(trace: ReplyTrace) -> str:
    """Consulta de búsqueda y si se amplió a los dos dominios ("" si no se buscó)."""
    if not trace.search_query:
        return ""
    widened = WIDENED_SEARCH_NOTE if trace.domain_fallback else ""
    return SEARCH_DEBUG_TEMPLATE.format(query=trace.search_query, widened=widened)
