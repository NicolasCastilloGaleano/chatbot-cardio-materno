"""Caso de uso: conversación en hilos con alarmas y evidencia (HU-06, HU-03/04, HU-02).

Flujo de cada turno (ADR 0007 y 0008):
1. **Filtro 1:** las reglas de alarma revisan el texto original. Si hay urgencia inmediata,
   se responde con el mensaje fijo, sin consultar al agente ni buscar evidencia.
2. **Llamada de análisis (sin evidencia):** decide el hilo, resume y lista los síntomas que
   reporta la persona.
3. **Filtro 2:** las mismas reglas revisan esos síntomas. El agente solo suma alarmas. Si hay
   urgencia inmediata, se responde con el mensaje fijo (sin RAG ni respuesta).
4. **Alcance (HU-07):** sin alarma, si el mensaje completo es ajeno al servicio se responde con
   un mensaje fijo y no se toca el hilo; si es conversacional, se responde sin evidencia.
5. **RAG:** se busca evidencia con el mensaje, el resumen y los síntomas.
6. **Llamada de respuesta (con evidencia):** redacta y cita la evidencia que usa.

La evidencia nunca llega a la llamada de análisis, así no puede alterar los síntomas que
revisan las reglas de alarma. El hilo solo se modifica al final del turno.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cardio_materno.application.agent_turn import (
    ANALYSIS_SCHEMA,
    AnalysisTurn,
    ReplyTurn,
    Scope,
    ThreadAction,
    parse_analysis,
    parse_reply,
    reply_schema,
)
from cardio_materno.application.alarm_policy import AlarmDecision, AlarmPolicy, compose_reply
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import build_evidence_query, format_evidence_context
from cardio_materno.application.ports.knowledge_retriever import EvidenceQuery, KnowledgeRetriever
from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.application.ports.thread_repository import ThreadRepository
from cardio_materno.application.scope import (
    CONVERSATIONAL_CONTEXT,
    OUT_OF_SCOPE_MESSAGE,
    effective_scope,
)
from cardio_materno.application.stage_timer import StageTimer, Timer
from cardio_materno.application.turn_context import TurnInput, analysis_context, reply_context
from cardio_materno.domain.alarms import Alert, AlertOrigin
from cardio_materno.domain.conversation import (
    ChatMessage,
    ConversationThread,
    Domain,
    Role,
    close_thread,
    open_thread,
    update_thread,
)
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import EvidenceRef, ReplyTrace, StageTiming

# Mensajes del hilo actual que se envían como contexto (3 turnos de pregunta y respuesta).
DEFAULT_CONTEXT_MESSAGES = 6
DEFAULT_EVIDENCE_ITEM_CHARS = 700
ALARM_SUMMARY_TEMPLATE = "Alerta: {sign}."
SYMPTOM_SEPARATOR = "; "
STAGE_ANALYSIS = "análisis"
STAGE_RAG = "RAG"
STAGE_REPLY = "respuesta"

Clock = Callable[[], datetime]
IdGenerator = Callable[[], str]


def utc_now() -> datetime:
    """Devuelve la fecha y hora actual en UTC."""
    return datetime.now(UTC)


def new_uuid() -> str:
    """Genera un identificador único aleatorio."""
    return str(uuid.uuid4())


def no_alarm_policy() -> AlarmPolicy:
    """Política sin reglas (útil cuando no se cargan alarmas, p. ej., en pruebas)."""
    return AlarmPolicy((), {})


class UnavailableRetriever:
    """Buscador nulo: se usa cuando el RAG está desactivado o no hay índice."""

    def retrieve(self, query: EvidenceQuery) -> RetrievalResult:
        """Siempre indica que no hay evidencia disponible."""
        return RetrievalResult(RetrievalStatus.UNAVAILABLE)


@dataclass(frozen=True)
class ConversationPorts:
    """Dependencias externas del caso de uso.

    Attributes:
        analyzer: Modelo de la llamada de análisis.
        responder: Modelo de la llamada de respuesta.
        repository: Repositorio de hilos.
        retriever: Buscador de evidencia (nulo si el RAG está desactivado).
    """

    analyzer: LanguageModel
    responder: LanguageModel
    repository: ThreadRepository
    retriever: KnowledgeRetriever = field(default_factory=UnavailableRetriever)


@dataclass(frozen=True)
class ConversationConfig:
    """Parámetros del caso de uso.

    Attributes:
        analysis_prompt: Instrucciones de la llamada de análisis.
        reply_prompt: Instrucciones de la llamada de respuesta.
        context_messages: Mensajes recientes del hilo que se envían como contexto.
        alarm_policy: Reglas de alarma y mensajes fijos.
        evidence_item_chars: Longitud máxima de cada respuesta de evidencia mostrada.
        clock: Fuente de la fecha y hora (se reemplaza en las pruebas).
        new_id: Generador de identificadores de hilo (se reemplaza en las pruebas).
        timer: Reloj monotónico para medir las etapas (se reemplaza en las pruebas).
    """

    analysis_prompt: str
    reply_prompt: str
    context_messages: int = DEFAULT_CONTEXT_MESSAGES
    alarm_policy: AlarmPolicy = field(default_factory=no_alarm_policy)
    evidence_item_chars: int = DEFAULT_EVIDENCE_ITEM_CHARS
    clock: Clock = utc_now
    new_id: IdGenerator = new_uuid
    timer: Timer = time.perf_counter


@dataclass(frozen=True)
class TurnResult:
    """Resultado de un turno de conversación.

    Attributes:
        reply: Respuesta para el usuario.
        thread: Hilo del turno (el activo sin cambios, o None, si fue fuera de alcance).
        is_new_thread: True si el turno abrió un hilo nuevo.
        alerts: Alertas registradas en el turno.
        trace: Cómo se produjo la respuesta (None si no se consultó al agente).
        out_of_scope: True si el mensaje se descartó por estar fuera de alcance (no se registra).
    """

    reply: str
    thread: ConversationThread | None
    is_new_thread: bool
    alerts: tuple[Alert, ...] = ()
    trace: ReplyTrace | None = None
    out_of_scope: bool = False


@dataclass(frozen=True)
class TurnOutcome:
    """Resultado interno del turno antes de modificar el hilo.

    Attributes:
        reply: Respuesta que se mostrará.
        decisions: Decisiones de alarma del turno.
        trace: Traza de la respuesta (None si no se consultó al agente).
        analysis: Resultado del análisis (None si no se hizo).
        record: False si el turno no debe tocar el hilo (mensaje fuera de alcance).
    """

    reply: str
    decisions: tuple[AlarmDecision, ...]
    trace: ReplyTrace | None = None
    analysis: AnalysisTurn | None = None
    record: bool = True


class ConversationService:
    """Coordina alarmas, agente, evidencia y repositorio para una sesión de un usuario."""

    def __init__(self, ports: ConversationPorts, config: ConversationConfig) -> None:
        """Crea el servicio.

        Args:
            ports: Modelos, repositorio y buscador de evidencia.
            config: Prompts, contexto, alarmas, reloj, ids y medidor de tiempos.
        """
        self._ports = ports
        self._config = config
        self._active_thread_id: str | None = None

    def send(self, user_text: str) -> TurnResult:
        """Procesa un mensaje del usuario y devuelve la respuesta.

        Si el modelo falla y no hay alarma, no se guarda nada y el hilo activo no cambia.
        Si hay alarma, el mensaje fijo se muestra aunque el modelo falle.

        Raises:
            LanguageModelError: Si el modelo falla (o responde mal) y no hay alarma.
        """
        current = self._active_thread()
        turn = TurnInput(user_text, self._recent(current))
        pre = self._config.alarm_policy.evaluate([user_text], AlertOrigin.USER)
        if pre is not None and pre.is_immediate:
            outcome = TurnOutcome(compose_reply([pre], None), (pre,))
        else:
            outcome = self._consult_agent(current, turn, pre)
        return self._finish(current, turn, outcome)

    def end_session(self) -> None:
        """Cierra el hilo activo, si existe (p. ej., cuando el usuario escribe "salir")."""
        current = self._active_thread()
        if current is not None:
            self._ports.repository.save_thread(close_thread(current, self._config.clock()))
        self._active_thread_id = None

    # --- Etapas del turno -------------------------------------------------------------

    def _consult_agent(
        self, current: ConversationThread | None, turn: TurnInput, pre: AlarmDecision | None
    ) -> TurnOutcome:
        """Análisis → filtro 2 → urgencia, alcance o evidencia y respuesta."""
        timer = StageTimer(self._config.timer)
        try:
            analysis = timer.measure(STAGE_ANALYSIS, lambda: self._analyze(current, turn))
        except LanguageModelError:
            if pre is None:
                raise
            return TurnOutcome(compose_reply([pre], None), (pre,))
        decisions = tuple(d for d in (pre, self._post_filter(analysis, pre)) if d is not None)
        return self._route(analysis, turn, decisions, timer)

    def _route(
        self,
        analysis: AnalysisTurn,
        turn: TurnInput,
        decisions: tuple[AlarmDecision, ...],
        timer: StageTimer,
    ) -> TurnOutcome:
        """Elige el camino: urgencia, fuera de alcance, conversacional o respuesta con evidencia.

        Las alarmas tienen prioridad sobre el alcance: con alarma el mensaje nunca se descarta.
        """
        scope = Scope.IN_SCOPE if decisions else effective_scope(analysis)
        if any(decision.is_immediate for decision in decisions):
            trace = analysis_trace(analysis, scope, timer.timings)
            return TurnOutcome(compose_reply(decisions, None), decisions, trace, analysis)
        if scope is Scope.OUT_OF_SCOPE:
            trace = analysis_trace(analysis, scope, timer.timings)
            return TurnOutcome(OUT_OF_SCOPE_MESSAGE, (), trace, analysis, record=False)
        if scope is Scope.CONVERSATIONAL:
            return self._converse(analysis, turn, timer)
        return self._answer(analysis, turn, decisions, timer)

    def _converse(self, analysis: AnalysisTurn, turn: TurnInput, timer: StageTimer) -> TurnOutcome:
        """Saludo, agradecimiento o despedida: llamada de respuesta sin buscar evidencia."""
        reply = timer.measure(
            STAGE_REPLY, lambda: self._reply(analysis, turn, CONVERSATIONAL_CONTEXT, ())
        )
        trace = analysis_trace(analysis, Scope.CONVERSATIONAL, timer.timings)
        return TurnOutcome(reply.reply, (), trace, analysis)

    def _answer(
        self,
        analysis: AnalysisTurn,
        turn: TurnInput,
        decisions: tuple[AlarmDecision, ...],
        timer: StageTimer,
    ) -> TurnOutcome:
        """Busca evidencia y pide la respuesta; con alarma, un fallo deja el mensaje fijo."""
        query = build_evidence_query(
            turn.user_text, analysis.summary, analysis.reported_symptoms, analysis.domain
        )
        retrieval = timer.measure(STAGE_RAG, lambda: self._ports.retriever.retrieve(query))
        evidence_text = format_evidence_context(retrieval, self._config.evidence_item_chars)
        try:
            reply = timer.measure(
                STAGE_REPLY, lambda: self._reply(analysis, turn, evidence_text, retrieval.labels)
            )
        except LanguageModelError:
            if not decisions:
                raise
            trace = build_trace(analysis, retrieval, (), timer.timings)
            return TurnOutcome(compose_reply(decisions, None), decisions, trace, analysis)
        trace = build_trace(analysis, retrieval, reply.evidence_ids, timer.timings)
        return TurnOutcome(compose_reply(decisions, reply.reply), decisions, trace, analysis)

    def _analyze(self, current: ConversationThread | None, turn: TurnInput) -> AnalysisTurn:
        """Llamada de análisis: sin evidencia (ADR 0008)."""
        context = analysis_context(self._config.analysis_prompt, current, turn)
        return parse_analysis(self._ports.analyzer.complete_json(context, ANALYSIS_SCHEMA))

    def _reply(
        self, analysis: AnalysisTurn, turn: TurnInput, context_text: str, labels: tuple[str, ...]
    ) -> ReplyTurn:
        """Llamada de respuesta con la evidencia (o el aviso) dada; solo cita esas etiquetas."""
        context = reply_context(self._config.reply_prompt, analysis, turn, context_text)
        data = self._ports.responder.complete_json(context, reply_schema(labels))
        return parse_reply(data, labels)

    def _post_filter(
        self, analysis: AnalysisTurn, pre: AlarmDecision | None
    ) -> AlarmDecision | None:
        """Filtro 2: revisa los síntomas reportados sin repetir las reglas ya detectadas."""
        if not analysis.reported_symptoms:
            return None
        symptoms = SYMPTOM_SEPARATOR.join(analysis.reported_symptoms)
        exclude = pre.rule_ids if pre is not None else ()
        return self._config.alarm_policy.evaluate([symptoms], AlertOrigin.AGENT, exclude)

    # --- Hilo y registro --------------------------------------------------------------

    def _finish(
        self, current: ConversationThread | None, turn: TurnInput, outcome: TurnOutcome
    ) -> TurnResult:
        """Modifica el hilo y registra el turno (solo cuando el turno terminó bien)."""
        if not outcome.record:
            return TurnResult(outcome.reply, current, False, (), outcome.trace, out_of_scope=True)
        if outcome.analysis is not None:
            thread, is_new = self._resolve_thread(current, outcome.analysis)
        else:
            thread, is_new = self._thread_for_alarm(current, outcome.decisions[0])
        alerts = self._record(thread.id, turn.user_text, outcome)
        return TurnResult(outcome.reply, thread, is_new, alerts, outcome.trace)

    def _active_thread(self) -> ConversationThread | None:
        """Obtiene el hilo activo de la sesión, si lo hay y sigue abierto."""
        if self._active_thread_id is None:
            return None
        thread = self._ports.repository.get_thread(self._active_thread_id)
        return thread if thread is not None and thread.is_open else None

    def _recent(self, current: ConversationThread | None) -> tuple[ChatMessage, ...]:
        """Últimos N mensajes del hilo activo."""
        if current is None:
            return ()
        return tuple(
            self._ports.repository.recent_messages(current.id, self._config.context_messages)
        )

    def _resolve_thread(
        self, current: ConversationThread | None, analysis: AnalysisTurn
    ) -> tuple[ConversationThread, bool]:
        """Aplica la decisión del análisis: actualiza el hilo actual o lo cierra y abre otro."""
        now = self._config.clock()
        if current is not None and analysis.thread_action is ThreadAction.CONTINUE:
            domain = continued_domain(current.domain, analysis.domain)
            thread = update_thread(current, domain, analysis.summary, now)
            self._ports.repository.save_thread(thread)
            return thread, False
        if current is not None:
            self._ports.repository.save_thread(close_thread(current, now))
        return self._open_new_thread(analysis.domain, analysis.summary), True

    def _thread_for_alarm(
        self, current: ConversationThread | None, decision: AlarmDecision
    ) -> tuple[ConversationThread, bool]:
        """Usa el hilo activo o abre uno nuevo con un resumen determinista de la alarma."""
        if current is not None:
            return current, False
        summary = ALARM_SUMMARY_TEMPLATE.format(sign=decision.primary_rule.sign)
        return self._open_new_thread(decision.domain, summary), True

    def _open_new_thread(self, domain: Domain, summary: str) -> ConversationThread:
        """Crea, guarda y activa un hilo nuevo."""
        thread = open_thread(self._config.new_id(), domain, summary, self._config.clock())
        self._ports.repository.save_thread(thread)
        self._active_thread_id = thread.id
        return thread

    def _record(self, thread_id: str, user_text: str, outcome: TurnOutcome) -> tuple[Alert, ...]:
        """Guarda los mensajes del turno (con la traza de la respuesta) y sus alertas."""
        now = self._config.clock()
        repository = self._ports.repository
        repository.append_message(ChatMessage(Role.USER, user_text, thread_id, now))
        repository.append_message(
            ChatMessage(Role.ASSISTANT, outcome.reply, thread_id, now, outcome.trace)
        )
        alerts = tuple(Alert(d.rule_ids, d.severity, d.origin, now) for d in outcome.decisions)
        for alert in alerts:
            repository.append_alert(thread_id, alert)
        return alerts


def build_trace(
    analysis: AnalysisTurn,
    retrieval: RetrievalResult,
    cited: tuple[str, ...],
    timings: tuple[StageTiming, ...],
) -> ReplyTrace:
    """Traza de una respuesta que pasó por análisis y búsqueda de evidencia."""
    evidence = tuple(
        EvidenceRef(item.label, item.entry.id, item.score, item.entry.category)
        for item in retrieval.items
    )
    return ReplyTrace(
        reported_symptoms=analysis.reported_symptoms,
        evidence=evidence,
        cited_evidence=cited,
        retrieval_status=retrieval.status,
        best_score=retrieval.best_score,
        timings=timings,
        scope=str(Scope.IN_SCOPE),
        scope_reason=analysis.scope_reason,
    )


def analysis_trace(
    analysis: AnalysisTurn, scope: Scope, timings: tuple[StageTiming, ...]
) -> ReplyTrace:
    """Traza de un turno que no buscó evidencia (urgencia, fuera de alcance o conversacional)."""
    return ReplyTrace(
        reported_symptoms=analysis.reported_symptoms,
        timings=timings,
        scope=str(scope),
        scope_reason=analysis.scope_reason,
    )


def continued_domain(current: Domain, analyzed: Domain) -> Domain:
    """Dominio de un hilo que continúa: un mensaje sin dominio ("gracias") no borra el del caso."""
    return current if analyzed is Domain.NONE else analyzed
