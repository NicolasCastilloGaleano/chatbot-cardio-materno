"""Serialización de la traza de una respuesta (`ReplyTrace`) para el JSON del hilo."""

from typing import Any

from cardio_materno.domain.trace import (
    EvidenceRef,
    GroundingCheck,
    InquiryTrace,
    ReplyTrace,
    RetrievalStatus,
    StageTiming,
    TurnMode,
)

LEGACY_SYMPTOMS_KEY = "reported_symptoms"


def trace_to_dict(trace: ReplyTrace) -> dict[str, Any]:
    """Convierte la traza en un diccionario legible."""
    return {
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
        "domain_fallback": trace.domain_fallback,
        "reminded_rules": list(trace.reminded_rules),
        "inquiry": inquiry_to_dict(trace.inquiry) if trace.inquiry else None,
    }


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
        domain_fallback=bool(data.get("domain_fallback", False)),
        reminded_rules=tuple(data.get("reminded_rules", [])),
        inquiry=inquiry_from_dict(data["inquiry"]) if data.get("inquiry") else None,
    )


def inquiry_to_dict(inquiry: InquiryTrace) -> dict[str, Any]:
    """Serializa la decisión de la regla de indagación (HU-11)."""
    return {
        "mode": str(inquiry.mode),
        "turn": inquiry.turn,
        "stalled": inquiry.stalled,
        "best_score": inquiry.best_score,
        "margin": inquiry.margin,
        "agreement": inquiry.agreement,
        "top_category": inquiry.top_category,
        "progress": inquiry.progress,
        "wants_guidance": inquiry.wants_guidance,
        "applied": inquiry.applied,
    }


def inquiry_from_dict(data: dict[str, Any]) -> InquiryTrace:
    """Reconstruye la decisión de la regla de indagación."""
    return InquiryTrace(
        mode=TurnMode(data["mode"]),
        turn=int(data.get("turn", 0)),
        stalled=int(data.get("stalled", 0)),
        best_score=float(data.get("best_score", 0.0)),
        margin=float(data.get("margin", 0.0)),
        agreement=int(data.get("agreement", 0)),
        top_category=data.get("top_category", ""),
        progress=data.get("progress"),
        wants_guidance=bool(data.get("wants_guidance", False)),
        applied=bool(data.get("applied", False)),
    )


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
        "literal_shown": check.literal_shown,
        "literal_total": check.literal_total,
    }


def grounding_from_dict(data: dict[str, Any]) -> GroundingCheck:
    """Reconstruye la verificación del respaldo."""
    return GroundingCheck(
        int(data["supported"]),
        int(data["total"]),
        bool(data.get("literal", False)),
        tuple(data.get("dropped", [])),
        int(data.get("literal_shown", 0)),
        int(data.get("literal_total", 0)),
    )
