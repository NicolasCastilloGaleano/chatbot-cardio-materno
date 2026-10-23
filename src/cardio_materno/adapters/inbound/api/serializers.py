"""Contrato JSON de la interfaz de auditoría (HU-08, HU-10).

Convierte turnos, chats, mensajes y trazas al formato que consume el cliente web. La
evidencia se completa con la pregunta y la respuesta del registro de la base.
"""

from typing import Any

from cardio_materno.application.conversation_service import TurnResult
from cardio_materno.application.ports.chat_audit import ChatEntry, ChatSummary
from cardio_materno.domain.alarms import Alert
from cardio_materno.domain.conversation import ChatMessage, ConversationThread
from cardio_materno.domain.knowledge import KnowledgeEntry
from cardio_materno.domain.trace import EvidenceRef, GroundingCheck, ReplyTrace
from cardio_materno.domain.user import Channel, ChatLock, chat_lock

MISSING_ENTRY_TEXT = "Registro no disponible"
SHORT_ID_CHARS = 8
CHANNEL_LABELS = {
    Channel.CONSOLE: "Consola",
    Channel.WEB: "Web",
    Channel.WHATSAPP: "WhatsApp",
    Channel.TELEGRAM: "Telegram",
    Channel.HISTORICAL: "Histórico",
}
LOCK_TEXTS = {
    ChatLock.CHANNEL: "Chat de {channel}: solo auditoría.",
    ChatLock.LIVE_CONSOLE: "En uso en la consola: podrás escribir cuando se cierre.",
}

Entries = dict[str, KnowledgeEntry]


def chat_to_dict(chat: ChatSummary) -> dict[str, Any]:
    """Serializa un chat de la lista, con si se puede escribir en él y por qué no.

    Args:
        chat: Resumen del chat.

    Returns:
        Identificador, etiqueta, canal, fechas, conteo, hilo abierto y bloqueo.
    """
    lock = chat_lock(chat.channel, chat.live_session_at)
    label = CHANNEL_LABELS[chat.channel]
    return {
        "id": chat.user_id,
        "short_id": chat.user_id[:SHORT_ID_CHARS],
        "channel": str(chat.channel),
        "channel_label": label,
        "label": f"{label} · {chat.user_id[:SHORT_ID_CHARS]}",
        "created_at": chat.created_at.isoformat(),
        "last_seen_at": chat.last_seen_at.isoformat(),
        "message_count": chat.message_count,
        "has_open_thread": chat.has_open_thread,
        "writable": lock is None,
        "lock": str(lock) if lock else None,
        "lock_text": LOCK_TEXTS[lock].format(channel=label) if lock else None,
    }


def entry_to_dict(entry: ChatEntry, entries: Entries) -> dict[str, Any]:
    """Serializa un mensaje del chat con su posición, su hilo y las alertas de su turno.

    Args:
        entry: Mensaje leído para la auditoría.
        entries: Registros usados para completar el texto de evidencia.

    Returns:
        El mensaje con `seq`, `thread` y `alerts`.
    """
    return {
        "seq": entry.seq,
        **message_to_dict(entry.message, entries),
        "thread": thread_to_dict(entry.thread),
        "alerts": [alert_to_dict(alert) for alert in entry.alerts],
    }


def turn_to_dict(result: TurnResult, entries: Entries) -> dict[str, Any]:
    """Convierte el turno y las alertas al contrato HTTP del cliente.

    Args:
        result: Turno procesado por el caso de uso.
        entries: Registros usados para completar el texto de evidencia.

    Returns:
        Datos JSON de la respuesta, el hilo, las alertas y la traza.
    """
    return {
        "reply": result.reply,
        "thread": thread_to_dict(result.thread) if result.thread else None,
        "is_new_thread": result.is_new_thread,
        "out_of_scope": result.out_of_scope,
        "alerts": [alert_to_dict(alert) for alert in result.alerts],
        "trace": trace_to_dict(result.trace, entries) if result.trace else None,
    }


def thread_to_dict(thread: ConversationThread) -> dict[str, str]:
    """Serializa los datos visibles de un hilo.

    Args:
        thread: Hilo que se expondrá a la interfaz.

    Returns:
        Identificador, resumen, dominio, estado y fechas en formato JSON.
    """
    return {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def message_to_dict(message: ChatMessage, entries: Entries) -> dict[str, Any]:
    """Serializa un mensaje y su traza, si existe.

    Args:
        message: Mensaje persistido.
        entries: Registros usados para completar el texto de evidencia.

    Returns:
        Mensaje con el rol, contenido, fecha y traza opcional.
    """
    return {
        "role": str(message.role),
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "trace": trace_to_dict(message.trace, entries) if message.trace else None,
    }


def trace_to_dict(trace: ReplyTrace, entries: Entries) -> dict[str, Any]:
    """Serializa la traza y resuelve la evidencia recuperada.

    Args:
        trace: Traza persistida del turno.
        entries: Registros de conocimiento indexados por identificador.

    Returns:
        Datos de auditoría con evidencia, citas, verificación y tiempos.
    """
    return {
        "reported_symptoms": list(trace.reported_symptoms),
        "reported_signs": list(trace.reported_signs),
        "unstated_symptoms": list(trace.unstated_symptoms),
        "search_query": trace.search_query,
        "scope": trace.scope,
        "scope_reason": trace.scope_reason,
        "retrieval_status": str(trace.retrieval_status) if trace.retrieval_status else None,
        "best_score": trace.best_score,
        "evidence": [evidence_to_dict(ref, entries) for ref in trace.evidence],
        "cited_evidence": list(trace.cited_evidence),
        "uncited": trace.uncited,
        "grounding": grounding_to_dict(trace.grounding) if trace.grounding else None,
        "timings": [{"stage": t.stage, "seconds": t.seconds} for t in trace.timings],
        "case": case_snapshot(trace),
    }


def case_snapshot(trace: ReplyTrace) -> dict[str, Any] | None:
    """Estado del caso de la base v2 para el panel de auditoría (None si no hay cuadro)."""
    if not trace.case_motive:
        return None
    return {
        "motive": trace.case_motive,
        "stage": trace.case_stage,
        "visited": list(trace.case_visited),
    }


def evidence_to_dict(ref: EvidenceRef, entries: Entries) -> dict[str, Any]:
    """Serializa una referencia de evidencia con la pregunta y la respuesta del registro.

    Args:
        ref: Referencia guardada en la traza (etiqueta, id, puntaje, categoría).
        entries: Registros de conocimiento indexados por identificador.

    Returns:
        La referencia con el texto del registro, o un aviso si ya no está en la base.
    """
    entry = entries.get(ref.entry_id)
    return {
        "label": ref.label,
        "entry_id": ref.entry_id,
        "score": ref.score,
        "category": ref.category,
        "question": entry.question if entry else MISSING_ENTRY_TEXT,
        "answer": entry.answer if entry else "",
    }


def grounding_to_dict(check: GroundingCheck) -> dict[str, Any]:
    """Serializa la verificación del respaldo de la respuesta (ADR 0010).

    Args:
        check: Resultado de la verificación guardado en la traza.

    Returns:
        Frases mostradas, total, uso del texto literal y frases descartadas.
    """
    return {
        "supported": check.supported,
        "total": check.total,
        "literal": check.literal,
        "dropped": list(check.dropped),
    }


def alert_to_dict(alert: Alert) -> dict[str, Any]:
    """Serializa una alerta determinista.

    Args:
        alert: Alerta registrada por las reglas del dominio.

    Returns:
        Regla, gravedad, origen y fecha de la alerta.
    """
    return {
        "rule_ids": list(alert.rule_ids),
        "severity": str(alert.severity),
        "origin": str(alert.origin),
        "created_at": alert.created_at.isoformat(),
    }
