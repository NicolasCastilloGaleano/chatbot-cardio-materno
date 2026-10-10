"""Serialización de la traza de una respuesta (`ReplyTrace`) para el JSON del hilo."""

from typing import Any

from cardio_materno.domain.trace import EvidenceRef, ReplyTrace, RetrievalStatus, StageTiming

LEGACY_SYMPTOMS_KEY = "reported_symptoms"


def trace_to_dict(trace: ReplyTrace) -> dict[str, Any]:
    """Convierte la traza en un diccionario legible."""
    return {
        "reported_symptoms": list(trace.reported_symptoms),
        "retrieval_status": str(trace.retrieval_status) if trace.retrieval_status else None,
        "best_score": trace.best_score,
        "evidence": [evidence_to_dict(ref) for ref in trace.evidence],
        "evidence_ids": list(trace.cited_evidence),
        "uncited_reply": trace.uncited,
        "timings": {timing.stage: timing.seconds for timing in trace.timings},
    }


def trace_from_dict(data: dict[str, Any]) -> ReplyTrace:
    """Reconstruye la traza desde su forma serializada."""
    status = data.get("retrieval_status")
    return ReplyTrace(
        reported_symptoms=tuple(data.get("reported_symptoms", [])),
        evidence=tuple(evidence_from_dict(item) for item in data.get("evidence", [])),
        cited_evidence=tuple(data.get("evidence_ids", [])),
        retrieval_status=RetrievalStatus(status) if status else None,
        best_score=data.get("best_score"),
        timings=tuple(
            StageTiming(stage, seconds) for stage, seconds in data.get("timings", {}).items()
        ),
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
