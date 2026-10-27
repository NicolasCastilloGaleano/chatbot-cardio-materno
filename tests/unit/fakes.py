"""Dobles de prueba compartidos para los puertos de la aplicación."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from cardio_materno.application.agent_turn import NO_CITATION
from cardio_materno.application.alarm_policy import AlarmPolicy
from cardio_materno.application.conversation_service import (
    ConversationConfig,
    ConversationPorts,
    ConversationService,
    TurnResult,
)
from cardio_materno.application.errors import ChannelDeliveryError
from cardio_materno.application.ports.knowledge_retriever import (
    EvidenceQuery,
    KnowledgeRetriever,
)
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.ports.user_thread_store import UserThreadStore
from cardio_materno.application.user_conversations import UserConversations
from cardio_materno.domain.alarms import AlarmRule, Alert, Severity, compile_pattern
from cardio_materno.domain.conversation import ChatMessage, ConversationThread, Domain
from cardio_materno.domain.knowledge import (
    EvidenceItem,
    Focus,
    KnowledgeEntry,
    RetrievalResult,
    RetrievalStatus,
)

ANALYSIS_KEYS = (
    "thread_action",
    "domain",
    "summary",
    "reported_symptoms",
    "reported_signs",
    "search_query",
    "scope",
    "scope_reason",
)


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
        "reported_signs": [],
        "reply": reply,
        "evidence_ids": [],
        "search_query": "",
        "scope": "en_alcance",
        "scope_reason": "",
    }


def scoped(turn: dict[str, Any], scope: str, reason: str = "") -> dict[str, Any]:
    """Guion de turno con el alcance que decidirá el análisis."""
    return turn | {"scope": scope, "scope_reason": reason}


def signing(turn: dict[str, Any], *codes: str) -> dict[str, Any]:
    """Guion de turno cuyo análisis marca los códigos de signos dados (ADR 0012)."""
    return turn | {"reported_signs": list(codes)}


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
        return self._agent.analysis() if self._kind == "analysis" else self._agent.reply(schema)


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

    @property
    def reply_text(self) -> str:
        """Texto guionizado de la respuesta del turno actual ("" si la respuesta falla)."""
        reply = self.current.get("reply", "")
        return reply if isinstance(reply, str) else ""

    def reply(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Respuesta simple (saludos) o frase por frase (con evidencia), según el esquema.

        Con evidencia, el texto guionizado es una sola frase que cita la primera etiqueta de
        `evidence_ids` o, si no hay, la primera etiqueta ofrecida. `sentences` en el guion
        reemplaza esa frase.
        """
        if isinstance(self.current["reply"], Exception):
            raise self.current["reply"]
        if "sentences" not in schema["properties"]:
            return {"reply": self.current["reply"], "evidence_ids": self.current["evidence_ids"]}
        if "sentences" in self.current:
            return {"sentences": self.current["sentences"]}
        offered = schema["properties"]["sentences"]["items"]["properties"]["evidence_id"]["enum"]
        label = (self.current["evidence_ids"] or [*offered[:-1], NO_CITATION])[0]
        return {"sentences": [{"text": self.current["reply"], "evidence_id": label}]}


class FakeRetriever:
    """Buscador falso: devuelve los resultados dados en orden y registra las consultas.

    Sin resultados devuelve INSUFFICIENT; cuando se acaban, repite el último.
    """

    def __init__(self, *results: RetrievalResult) -> None:
        self.results = results or (RetrievalResult(RetrievalStatus.INSUFFICIENT),)
        self.queries: list[EvidenceQuery] = []

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        self.queries.append(query)
        return self.results[min(len(self.queries), len(self.results)) - 1]


class BackingRetriever:
    """Buscador por defecto: un registro que respalda exactamente la respuesta guionizada.

    Así, las pruebas que no tratan sobre la evidencia ven la respuesta del agente tal cual.
    """

    def __init__(self, agent: "ScriptedAgent") -> None:
        self._agent = agent
        self.queries: list[EvidenceQuery] = []

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        self.queries.append(query)
        return evidence_result(knowledge_entry(answer=self._agent.reply_text or "respuesta"))


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
    repo: ThreadRepository | None = None,
    config: dict[str, Any] | None = None,
    retriever: KnowledgeRetriever | None = None,
    active_thread_id: str | None = None,
) -> ConversationService:
    """Servicio con dobles: reloj, ids y tiempos deterministas.

    Sin `retriever`, la evidencia respalda la respuesta guionizada (`BackingRetriever`).
    `active_thread_id` retoma un hilo abierto, como en los canales de chat continuo.
    """
    ports = ConversationPorts(
        agent.analyzer,
        agent.responder,
        repo or InMemoryThreadRepository(),
        retriever or BackingRetriever(agent),
    )
    options: dict[str, Any] = {
        "clock": FakeClock(),
        "new_id": SequentialIds(),
        "timer": FakeTimer(),
    }
    return ConversationService(
        ports,
        ConversationConfig("ANALYSIS", "REPLY", **(options | (config or {}))),
        active_thread_id,
    )


def make_user_conversations(
    agent: "ScriptedAgent",
    threads: UserThreadStore,
    clock: "FakeClock",
    idle_timeout: timedelta = timedelta(hours=12),
    service_config: dict[str, Any] | None = None,
) -> UserConversations:
    """Servicio por usuario con el agente guionizado, reloj compartido e ids hilo-1, hilo-2…"""
    options = {"clock": clock, "new_id": SequentialIds()} | (service_config or {})

    def factory(repository: ThreadRepository, active: str | None) -> ConversationService:
        return make_service(agent, repository, options, active_thread_id=active)

    return UserConversations(threads, factory, idle_timeout, clock)


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

    def list_threads(self) -> list[ConversationThread]:
        return sorted(self.threads.values(), key=lambda thread: thread.updated_at, reverse=True)

    def all_messages(self, thread_id: str) -> list[ChatMessage]:
        return list(self.messages.get(thread_id, []))

    def append_message(self, message: ChatMessage) -> None:
        if message.thread_id not in self.messages:
            raise KeyError(message.thread_id)
        self.messages[message.thread_id].append(message)

    def append_alert(self, thread_id: str, alert: Alert) -> None:
        if thread_id not in self.threads:
            raise KeyError(thread_id)
        self.alerts.setdefault(thread_id, []).append(alert)

    def all_alerts(self, thread_id: str) -> list[Alert]:
        return list(self.alerts.get(thread_id, []))

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


class FakeSender:
    """Canal falso: registra los envíos y puede simular fallos."""

    def __init__(self, fail_send: bool = False, fail_acknowledge: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.acknowledged: list[str] = []
        self.fail_send = fail_send
        self.fail_acknowledge = fail_acknowledge

    def send_text(self, reply_to: str, text: str) -> str:
        if self.fail_send:
            raise ChannelDeliveryError("canal caído")
        self.sent.append((reply_to, text))
        return f"wamid.enviado-{len(self.sent)}"

    def acknowledge(self, reply_to: str, channel_message_id: str) -> None:
        if self.fail_acknowledge:
            raise ChannelDeliveryError("sin indicador")
        self.acknowledged.append(channel_message_id)

    def texts_to(self, reply_to: str) -> list[str]:
        """Textos enviados a una dirección."""
        return [text for address, text in self.sent if address == reply_to]


class FakeDelayedActions:
    """Temporizador falso: con `fire=True` la acción se ejecuta al programarla (respuesta lenta)."""

    def __init__(self, fire: bool = False) -> None:
        self.fire = fire
        self.delays: list[float] = []
        self.cancelled = 0

    def schedule(self, delay_seconds: float, action: Callable[[], None]) -> Callable[[], None]:
        self.delays.append(delay_seconds)
        if self.fire:
            action()
        return self._cancel

    def _cancel(self) -> None:
        self.cancelled += 1


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
            code="SANGRADO_VAGINAL",
            examples=("me sangra",),
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
            code="PRESION_ALTA",
        ),
    ]
    return AlarmPolicy(rules, {"urg": URGENT_MESSAGE, "pri": PRIORITY_MESSAGE})


def thread_of(result: TurnResult) -> ConversationThread:
    """Hilo de un turno que sí se registró (falla la prueba si fue fuera de alcance)."""
    assert result.thread is not None
    return result.thread
