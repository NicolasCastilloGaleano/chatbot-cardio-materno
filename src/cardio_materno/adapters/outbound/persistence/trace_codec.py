"""Serialización de la traza de una respuesta (`ReplyTrace`) para el JSON del hilo."""

from typing import Any

from cardio_materno.domain.trace import (
    EvidenceRef,
    GroundingCheck,
    ReplyTrace,
    RetrievalStatus,
    StageTiming,
)

LEGACY_SYMPTOMS_KEY = "reported_symptoms"


def trace_to_dict(trace: ReplyTrace) -> dict[str, Any]:
    """Convierte la traza en un diccionario legible (con "case" solo si hay cuadro)."""
    data = {
        "reported_symptoms": list(trace.reported_symptoms),
        "reported_signs": list(trace.reported_signs),
        "retrieval_status": str(trace.retrieval_status) if trace.retrieval_status else None,
        "best_score": trace.best_score,
        "evidence": [evidence_to_dict(ref) for ref in trace.evidence],
        "evidence_ids": list(trace.cited_evidence),
        "uncited_reply": trace.uncited,
        "timings": {timing.stage: timing.seconds for timing in trace.timings},
        "scope": trace.scope,
        "scope_reason": trace.scope_reason,
        "grounding": grounding_to_dict(trace.grounding) if trace.grounding else None,
        "unstated_symptoms": list(trace.unstated_symptoms),
        "search_query": trace.search_query,
    }
    case = case_to_dict(trace)
    return data if case is None else data | {"case": case}


def trace_from_dict(data: dict[str, Any]) -> ReplyTrace:
    """Reconstruye la traza desde su forma serializada."""
    status = data.get("retrieval_status")
    return ReplyTrace(
        reported_symptoms=tuple(data.get("reported_symptoms", [])),
        reported_signs=tuple(data.get("reported_signs", [])),
        evidence=tuple(evidence_from_dict(item) for item in data.get("evidence", [])),
        cited_evidence=tuple(data.get("evidence_ids", [])),
        retrieval_status=RetrievalStatus(status) if status else None,
        best_score=data.get("best_score"),
        timings=tuple(
            StageTiming(stage, seconds) for stage, seconds in data.get("timings", {}).items()
        ),
        scope=data.get("scope"),
        scope_reason=data.get("scope_reason", ""),
        grounding=grounding_from_dict(data["grounding"]) if data.get("grounding") else None,
        unstated_symptoms=tuple(data.get("unstated_symptoms", [])),
        search_query=data.get("search_query", ""),
        **case_from_dict(data.get("case")),
    )


def case_to_dict(trace: ReplyTrace) -> dict[str, Any] | None:
    """Serializa el estado del caso de la base v2 (None si la respuesta no tiene cuadro)."""
    if not trace.case_motive:
        return None
    return {
        "motive": trace.case_motive,
        "stage": trace.case_stage,
        "visited": list(trace.case_visited),
    }


def case_from_dict(data: dict[str, Any] | None) -> dict[str, Any]:
    """Campos de la traza con el estado del caso (vacío en trazas sin cuadro o anteriores)."""
    if not data:
        return {}
    return {
        "case_motive": str(data["motive"]),
        "case_stage": str(data["stage"]),
        "case_visited": tuple(str(stage) for stage in data.get("visited", [])),
    }


def legacy_trace(message: dict[str, Any]) -> ReplyTrace | None:
    """Traza de archivos anteriores, que guardaban solo `reported_symptoms` en el mensaje."""
    symptoms = message.get(LEGACY_SYMPTOMS_KEY)
    return ReplyTrace(reported_symptoms=tuple(symptoms)) if symptoms is not None else None


def evidence_to_dict(ref: EvidenceRef) -> dict[str, Any]:
    """Serializa una referencia de evidencia."""
    return {
        "label": ref.label,
        "entry_id": ref.entry_id,
        "score": ref.score,
        "category": ref.category,
    }


def evidence_from_dict(data: dict[str, Any]) -> EvidenceRef:
    """Reconstruye una referencia de evidencia."""
    return EvidenceRef(data["label"], data["entry_id"], float(data["score"]), data["category"])


def grounding_to_dict(check: GroundingCheck) -> dict[str, Any]:
    """Serializa la verificación del respaldo."""
    return {
        "supported": check.supported,
        "total": check.total,
        "literal": check.literal,
        "dropped": list(check.dropped),
    }


def grounding_from_dict(data: dict[str, Any]) -> GroundingCheck:
    """Reconstruye la verificación del respaldo."""
    return GroundingCheck(
        int(data["supported"]),
        int(data["total"]),
        bool(data.get("literal", False)),
        tuple(data.get("dropped", [])),
    )
