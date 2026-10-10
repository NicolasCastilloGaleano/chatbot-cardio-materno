"""Dobles de prueba compartidos para los puertos de la aplicación."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.application.conversation_service import (
    ConversationConfig,
    ConversationPorts,
    ConversationService,
)
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery
from cardio_materno.domain.alarms import AlarmRule, Alert, Severity, compile_pattern
from cardio_materno.domain.conversation import ChatMessage, ConversationThread, Domain
from cardio_materno.domain.knowledge import (
    EvidenceItem,
    Focus,
    KnowledgeEntry,
    RetrievalResult,
    RetrievalStatus,
)

ANALYSIS_KEYS = ("thread_action", "domain", "summary", "reported_symptoms")


def agent_json(
    reply: str | Exception = "respuesta",
    thread_action: str = "continuar",
    domain: str = "materno_infantil",
    summary: str = "resumen",
    reported_symptoms: list[str] | None = None,
) -> dict[str, Any]:
    """Guion de un turno: lo que devolverán la llamada de análisis y la de respuesta.

    `reply` puede ser una excepción para simular que falla la llamada de respuesta.
    """
    return {
        "thread_action": thread_action,
        "domain": domain,
        "summary": summary,
        "reported_symptoms": reported_symptoms or [],
        "reply": reply,
        "evidence_ids": [],
    }


def citing(turn: dict[str, Any], *labels: str) -> dict[str, Any]:
    """Guion de turno cuya respuesta cita las etiquetas de evidencia dadas."""
    return turn | {"evidence_ids": list(labels)}


class ScriptedStage:
    """Una de las dos llamadas (análisis o respuesta) de `ScriptedAgent`."""

    def __init__(self, agent: "ScriptedAgent", kind: str) -> None:
        self._agent = agent
        self._kind = kind
        self.calls: list[list[ChatMessage]] = []
        self.schemas: list[dict[str, Any]] = []

    def complete_json(
        self, messages: Sequence[ChatMessage], schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(list(messages))
        self.schemas.append(schema)
        return self._agent.analysis() if self._kind == "analysis" else self._agent.reply()


class ScriptedAgent:
    """Agente falso de dos llamadas: cada turno guionizado alimenta el análisis y la respuesta.

    Un turno que es una excepción hace fallar la llamada de análisis.
    """

    def __init__(self, *turns: dict[str, Any] | Exception) -> None:
        self.turns = list(turns)
        self.current: dict[str, Any] = {}
        self.analyzer = ScriptedStage(self, "analysis")
        self.responder = ScriptedStage(self, "reply")

    @property
    def calls(self) -> list[list[ChatMessage]]:
        """Contextos recibidos por la llamada de análisis."""
        return self.analyzer.calls

    def analysis(self) -> dict[str, Any]:
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        self.current = turn
        return {key: turn[key] for key in ANALYSIS_KEYS}

    def reply(self) -> dict[str, Any]:
        if isinstance(self.current["reply"], Exception):
            raise self.current["reply"]
        return {"reply": self.current["reply"], "evidence_ids": self.current["evidence_ids"]}


class FakeRetriever:
    """Buscador falso: devuelve un resultado fijo y registra las consultas."""

    def __init__(self, result: RetrievalResult | None = None) -> None:
        self.result = result or RetrievalResult(RetrievalStatus.INSUFFICIENT)
        self.queries: list[EvidenceQuery] = []

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        self.queries.append(query)
        return self.result


def knowledge_entry(
    entry_id: str = "k1", domain: Domain = Domain.MATERNAL_CHILD, answer: str = "respuesta validada"
) -> KnowledgeEntry:
    """Registro de la base para pruebas."""
    return KnowledgeEntry(entry_id, domain, "Categoría", Focus.SOLVE, "¿Pregunta?", answer)


def evidence_result(*entries: KnowledgeEntry) -> RetrievalResult:
    """Resultado SUFFICIENT con los registros dados etiquetados E1, E2…"""
    items = tuple(EvidenceItem(f"E{n}", entry, 0.8) for n, entry in enumerate(entries, start=1))
    return RetrievalResult(RetrievalStatus.SUFFICIENT, items, 0.8)


def make_service(
    agent: "ScriptedAgent",
    repo: "InMemoryThreadRepository | None" = None,
    config: dict[str, Any] | None = None,
    retriever: FakeRetriever | None = None,
) -> ConversationService:
    """Servicio con dobles: reloj, ids y tiempos deterministas."""
    ports = ConversationPorts(
        agent.analyzer,
        agent.responder,
        repo or InMemoryThreadRepository(),
        retriever or FakeRetriever(),
    )
    options: dict[str, Any] = {
        "clock": FakeClock(),
        "new_id": SequentialIds(),
        "timer": FakeTimer(),
    }
    return ConversationService(
        ports, ConversationConfig("ANALYSIS", "REPLY", **(options | (config or {})))
    )


class FakeTimer:
    """Reloj monotónico que avanza medio segundo en cada lectura."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.5
        return self.now


class InMemoryThreadRepository:
    """Repositorio de hilos en memoria para pruebas."""

    def __init__(self) -> None:
        self.threads: dict[str, ConversationThread] = {}
        self.messages: dict[str, list[ChatMessage]] = {}
        self.alerts: dict[str, list[Alert]] = {}

    def save_thread(self, thread: ConversationThread) -> None:
        self.threads[thread.id] = thread
        self.messages.setdefault(thread.id, [])

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        return self.threads.get(thread_id)

    def append_message(self, message: ChatMessage) -> None:
        if message.thread_id not in self.messages:
            raise KeyError(message.thread_id)
        self.messages[message.thread_id].append(message)

    def append_alert(self, thread_id: str, alert: Alert) -> None:
        if thread_id not in self.threads:
            raise KeyError(thread_id)
        self.alerts.setdefault(thread_id, []).append(alert)

    def recent_messages(self, thread_id: str, limit: int) -> list[ChatMessage]:
        return self.messages.get(thread_id, [])[-limit:] if limit > 0 else []


class FakeClock:
    """Reloj que avanza un segundo en cada llamada."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.current += timedelta(seconds=1)
        return self.current


class SequentialIds:
    """Generador de identificadores predecibles: hilo-1, hilo-2…"""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"hilo-{self.count}"


URGENT_MESSAGE = "URGENCIA: acude ya"
PRIORITY_MESSAGE = "PRIORITARIA: pide cita"


def make_alarm_policy() -> AlarmPolicy:
    """Política mínima: una regla de urgencia y una prioritaria."""
    rules = [
        AlarmRule(
            "T-URG",
            Domain.MATERNAL_CHILD,
            "gestante",
            "Sangrado vaginal",
            Severity.IMMEDIATE,
            (compile_pattern(r"sangrado vaginal"),),
            "urg",
            "prueba",
        ),
        AlarmRule(
            "T-PRI",
            Domain.CARDIOVASCULAR,
            "adulto",
            "Presión alta",
            Severity.PRIORITY,
            (compile_pattern(r"presion alta"),),
            "pri",
            "prueba",
        ),
    ]
    return AlarmPolicy(rules, {"urg": URGENT_MESSAGE, "pri": PRIORITY_MESSAGE})
