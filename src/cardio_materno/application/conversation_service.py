"""Caso de uso: conversación en hilos con alarmas y evidencia (HU-06, HU-03/04, HU-02).

Flujo de cada turno (ADR 0007 y 0008):
1. **Filtro 1:** las reglas de alarma revisan el texto original. Si hay urgencia inmediata,
   se responde con el mensaje fijo, sin consultar al agente ni buscar evidencia.
2. **Llamada de análisis (sin evidencia):** decide el hilo, resume y lista los síntomas que
   reporta la persona.
3. **Filtro 2:** las mismas reglas revisan cada síntoma por separado y, por cruce exacto,
   los códigos de signos que marcó el análisis (ADR 0012). El agente solo suma alarmas. Si hay
   urgencia inmediata, se responde con el mensaje fijo (sin RAG ni respuesta).
4. **Alcance (HU-07):** sin alarma, si el mensaje completo es ajeno al servicio se responde con
   un mensaje fijo y no se toca el hilo; si es conversacional, se responde sin evidencia y
   nunca se abre un hilo.
5. **RAG:** se busca evidencia con la consulta reformulada por el análisis. Sin evidencia
   suficiente no se llama al LLM: se muestra un mensaje fijo de abstención (ADR 0010).
6. **Llamada de respuesta (con evidencia):** redacta frase por frase, citando el registro que
   respalda cada una. Un verificador determinista comprueba el respaldo; si una frase citada
   no está respaldada, se muestra el texto literal del registro (ADR 0010).

La evidencia nunca llega a la llamada de análisis, así no puede alterar los síntomas que
revisan las reglas de alarma. El hilo solo se modifica al final del turno.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from cardio_materno.application.agent_turn import (
    AnalysisTurn,
    DraftSentence,
    ReplyTurn,
    Scope,
    ThreadAction,
    analysis_schema,
    grounded_reply_schema,
    parse_analysis,
    parse_grounded_reply,
    parse_reply,
    reply_schema,
)
from cardio_materno.application.alarm_policy import (
    REPLY_SEPARATOR,
    AlarmDecision,
    AlarmPolicy,
    compose_reply,
    reminder_for,
)
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.evidence import build_evidence_query, format_evidence_context
from cardio_materno.application.grounded_reply import abstention_text, compose_grounded_reply
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
from cardio_materno.domain.alarms import AlarmRule, Alert, AlertOrigin
from cardio_materno.domain.conversation import (
    ChatMessage,
    ConversationThread,
    Domain,
    Role,
    close_thread,
    open_thread,
    update_thread,
)
from cardio_materno.domain.grounding import GroundingPolicy, unstated_details
from cardio_materno.domain.knowledge import RetrievalResult, RetrievalStatus
from cardio_materno.domain.trace import EvidenceRef, GroundingCheck, ReplyTrace, StageTiming

# Mensajes del hilo actual que se envían como contexto (3 turnos de pregunta y respuesta).
DEFAULT_CONTEXT_MESSAGES = 6
DEFAULT_EVIDENCE_ITEM_CHARS = 700
ALARM_SUMMARY_TEMPLATE = "Alerta: {sign}."
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
        grounding: Parámetros de la verificación del respaldo (ADR 0010).
        clock: Fuente de la fecha y hora (se reemplaza en las pruebas).
        new_id: Generador de identificadores de hilo (se reemplaza en las pruebas).
        timer: Reloj monotónico para medir las etapas (se reemplaza en las pruebas).
    """

    analysis_prompt: str
    reply_prompt: str
    context_messages: int = DEFAULT_CONTEXT_MESSAGES
    alarm_policy: AlarmPolicy = field(default_factory=no_alarm_policy)
    evidence_item_chars: int = DEFAULT_EVIDENCE_ITEM_CHARS
    grounding: GroundingPolicy = field(default_factory=GroundingPolicy)
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
        conversational: True si fue un saludo o agradecimiento (nunca abre un hilo).
    """

    reply: str
    decisions: tuple[AlarmDecision, ...]
    trace: ReplyTrace | None = None
    analysis: AnalysisTurn | None = None
    record: bool = True
    conversational: bool = False


class ConversationService:
    """Coordina alarmas, agente, evidencia y repositorio para una sesión de un usuario."""

    def __init__(
        self,
        ports: ConversationPorts,
        config: ConversationConfig,
        active_thread_id: str | None = None,
    ) -> None:
        """Crea el servicio.

        Args:
            ports: Modelos, repositorio y buscador de evidencia.
            config: Prompts, contexto, alarmas, reloj, ids y medidor de tiempos.
            active_thread_id: Hilo abierto que retoma la sesión (canales de chat continuo,
                ADR 0015). None para empezar sin hilo activo, como la consola.
        """
        self._ports = ports
        self._config = config
        self._active_thread_id = active_thread_id
        self._sign_codes = config.alarm_policy.codes
        self._analysis_schema = analysis_schema(self._sign_codes)

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
        found = self._post_filter(analysis, pre)
        post, reminded = self._config.alarm_policy.split_alerted(
            found, self._alerted_rules(current, analysis)
        )
        decisions = (pre, *post) if pre is not None else post
        outcome = self._route(analysis, turn, decisions, timer)
        return with_unstated_details(with_reminder(outcome, reminded), turn)

    def _alerted_rules(
        self, current: ConversationThread | None, analysis: AnalysisTurn
    ) -> frozenset[str]:
        """Reglas con alerta registrada en el hilo que continúa (vacío si el turno abre otro).

        Un hilo nuevo evalúa las alarmas desde cero (ADR 0018).
        """
        if current is None or analysis.thread_action is not ThreadAction.CONTINUE:
            return frozenset()
        alerts = self._ports.repository.all_alerts(current.id)
        return frozenset(rule_id for alert in alerts for rule_id in alert.rule_ids)

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
        scope = Scope.IN_SCOPE if decisions else effective_scope(analysis, turn.recent)
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
        reply = timer.measure(STAGE_REPLY, lambda: self._conversational_reply(analysis, turn))
        trace = analysis_trace(analysis, Scope.CONVERSATIONAL, timer.timings)
        return TurnOutcome(reply.reply, (), trace, analysis, conversational=True)

    def _answer(
        self,
        analysis: AnalysisTurn,
        turn: TurnInput,
        decisions: tuple[AlarmDecision, ...],
        timer: StageTimer,
    ) -> TurnOutcome:
        """Busca evidencia; sin evidencia suficiente se abstiene sin llamar al LLM."""
        query = build_evidence_query(analysis, turn.user_text)
        retrieval, widened = timer.measure(STAGE_RAG, lambda: self._search(query))
        if retrieval.status is not RetrievalStatus.SUFFICIENT:
            trace = build_trace(analysis, retrieval, (), timer.timings)
            reply = (
                compose_reply(decisions, None) if decisions else abstention_text(retrieval.status)
            )
            outcome = TurnOutcome(reply, decisions, trace, analysis)
            return with_search_query(outcome, query.text, widened)
        outcome = self._grounded_answer(analysis, turn, decisions, retrieval, timer)
        return with_search_query(outcome, query.text, widened)

    def _search(self, query: EvidenceQuery) -> tuple[RetrievalResult, bool]:
        """Busca en el dominio del análisis y, si no hay evidencia suficiente, en los dos.

        Solo se repite cuando la primera búsqueda fue insuficiente y tenía dominio: si el
        análisis se equivocó de dominio, la persona no recibe una abstención innecesaria.
        Con el buscador no disponible no se repite.

        Returns:
            El resultado de la búsqueda y True si se usó la búsqueda en los dos dominios.
        """
        found = self._ports.retriever.retrieve(query)
        if found.status is not RetrievalStatus.INSUFFICIENT or not query.domains:
            return found, False
        widened = self._ports.retriever.retrieve(replace(query, domains=()))
        if widened.status is RetrievalStatus.SUFFICIENT:
            return widened, True
        return found, False

    def _grounded_answer(
        self,
        analysis: AnalysisTurn,
        turn: TurnInput,
        decisions: tuple[AlarmDecision, ...],
        retrieval: RetrievalResult,
        timer: StageTimer,
    ) -> TurnOutcome:
        """Pide la redacción con evidencia y la verifica; con alarma, si falla, el mensaje fijo."""
        try:
            draft = timer.measure(STAGE_REPLY, lambda: self._draft(analysis, turn, retrieval))
        except LanguageModelError:
            if not decisions:
                raise
            trace = build_trace(analysis, retrieval, (), timer.timings)
            return TurnOutcome(compose_reply(decisions, None), decisions, trace, analysis)
        query_text = build_evidence_query(analysis, turn.user_text).text
        grounded = compose_grounded_reply(
            draft, retrieval.items, turn.user_text, self._config.grounding, query_text
        )
        trace = build_trace(analysis, retrieval, grounded.cited, timer.timings, grounded.check)
        return TurnOutcome(compose_reply(decisions, grounded.text), decisions, trace, analysis)

    def _analyze(self, current: ConversationThread | None, turn: TurnInput) -> AnalysisTurn:
        """Llamada de análisis: sin evidencia (ADR 0008)."""
        context = analysis_context(self._config.analysis_prompt, current, turn)
        data = self._ports.analyzer.complete_json(context, self._analysis_schema)
        return parse_analysis(data, self._sign_codes)

    def _conversational_reply(self, analysis: AnalysisTurn, turn: TurnInput) -> ReplyTurn:
        """Llamada de respuesta sin evidencia (saludos): texto simple, sin citas."""
        context = reply_context(self._config.reply_prompt, analysis, turn, CONVERSATIONAL_CONTEXT)
        data = self._ports.responder.complete_json(context, reply_schema(()))
        return parse_reply(data, ())

    def _draft(
        self, analysis: AnalysisTurn, turn: TurnInput, retrieval: RetrievalResult
    ) -> tuple[DraftSentence, ...]:
        """Llamada de respuesta con evidencia: frases que solo pueden citar las etiquetas dadas."""
        evidence_text = format_evidence_context(retrieval.items, self._config.evidence_item_chars)
        context = reply_context(self._config.reply_prompt, analysis, turn, evidence_text)
        data = self._ports.responder.complete_json(context, grounded_reply_schema(retrieval.labels))
        return parse_grounded_reply(data, retrieval.labels)

    def _post_filter(
        self, analysis: AnalysisTurn, pre: AlarmDecision | None
    ) -> tuple[AlarmDecision, ...]:
        """Filtro 2: síntomas en texto y códigos de signos, sin repetir reglas ya detectadas.

        Cada síntoma se evalúa por separado: el contexto de uno ("en el embarazo") no se combina
        con el signo de otro ("fiebre en el bebé"). Los códigos marcados (ADR 0012) se cruzan
        de forma exacta con las reglas. Las dos vías solo suman alarmas.
        """
        policy = self._config.alarm_policy
        exclude = set(pre.rule_ids) if pre is not None else set()
        by_text = policy.evaluate(analysis.reported_symptoms, AlertOrigin.AGENT, exclude)
        exclude |= set(by_text.rule_ids) if by_text is not None else set()
        by_code = policy.evaluate_codes(analysis.reported_signs, exclude)
        return tuple(d for d in (by_text, by_code) if d is not None)

    # --- Hilo y registro --------------------------------------------------------------

    def _finish(
        self, current: ConversationThread | None, turn: TurnInput, outcome: TurnOutcome
    ) -> TurnResult:
        """Modifica el hilo y registra el turno (solo cuando el turno terminó bien)."""
        if not outcome.record:
            return TurnResult(outcome.reply, current, False, (), outcome.trace, out_of_scope=True)
        if outcome.conversational:
            return self._finish_conversational(current, turn, outcome)
        if outcome.analysis is not None:
            thread, is_new = self._resolve_thread(current, outcome.analysis)
        else:
            thread, is_new = self._thread_for_alarm(current, outcome.decisions[0])
        alerts = self._record(thread.id, turn.user_text, outcome)
        return TurnResult(outcome.reply, thread, is_new, alerts, outcome.trace)

    def _finish_conversational(
        self, current: ConversationThread | None, turn: TurnInput, outcome: TurnOutcome
    ) -> TurnResult:
        """Saludo o agradecimiento: queda en el hilo activo sin cambiarlo; sin hilo no se guarda."""
        if current is None:
            return TurnResult(outcome.reply, None, False, (), outcome.trace)
        thread = update_thread(current, current.domain, current.summary, self._config.clock())
        self._ports.repository.save_thread(thread)
        self._record(thread.id, turn.user_text, outcome)
        return TurnResult(outcome.reply, thread, False, (), outcome.trace)

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
        """Usa el hilo activo si es del dominio de la alarma; si no, abre uno nuevo.

        El resumen del hilo nuevo es determinista (el signo de la regla principal).
        """
        if current is not None and current.domain is decision.domain:
            return current, False
        if current is not None:
            self._ports.repository.save_thread(close_thread(current, self._config.clock()))
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
    grounding: GroundingCheck | None = None,
) -> ReplyTrace:
    """Traza de una respuesta que pasó por análisis y búsqueda de evidencia."""
    evidence = tuple(
        EvidenceRef(item.label, item.entry.id, item.score, item.entry.category)
        for item in retrieval.items
    )
    return ReplyTrace(
        reported_symptoms=analysis.reported_symptoms,
        reported_signs=analysis.reported_signs,
        evidence=evidence,
        cited_evidence=cited,
        retrieval_status=retrieval.status,
        best_score=retrieval.best_score,
        timings=timings,
        scope=str(Scope.IN_SCOPE),
        scope_reason=analysis.scope_reason,
        grounding=grounding,
    )


def analysis_trace(
    analysis: AnalysisTurn, scope: Scope, timings: tuple[StageTiming, ...]
) -> ReplyTrace:
    """Traza de un turno que no buscó evidencia (urgencia, fuera de alcance o conversacional)."""
    return ReplyTrace(
        reported_symptoms=analysis.reported_symptoms,
        reported_signs=analysis.reported_signs,
        timings=timings,
        scope=str(scope),
        scope_reason=analysis.scope_reason,
    )


def with_reminder(outcome: TurnOutcome, reminded: tuple[AlarmRule, ...]) -> TurnOutcome:
    """Antepone el recordatorio de las reglas ya avisadas y lo registra en la traza (ADR 0018).

    No se agrega si el turno ya muestra el aviso de una alarma nueva igual o más grave.
    """
    reminder = reminder_for(reminded, outcome.decisions)
    if reminder is None:
        return outcome
    trace = outcome.trace
    if trace is not None:
        trace = replace(trace, reminded_rules=tuple(rule.id for rule in reminded))
    return replace(outcome, reply=f"{reminder}{REPLY_SEPARATOR}{outcome.reply}", trace=trace)


def with_search_query(outcome: TurnOutcome, query_text: str, widened: bool = False) -> TurnOutcome:
    """Registra en la traza la consulta de búsqueda (B-021) y si se amplió a los dos dominios."""
    if outcome.trace is None:
        return outcome
    trace = replace(outcome.trace, search_query=query_text, domain_fallback=widened)
    return replace(outcome, trace=trace)


def with_unstated_details(outcome: TurnOutcome, turn: TurnInput) -> TurnOutcome:
    """Marca en la traza los síntomas con datos que la persona no escribió en el hilo."""
    if outcome.trace is None:
        return outcome
    user_texts = [turn.user_text, *(m.content for m in turn.recent if m.role is Role.USER)]
    unstated = unstated_details(outcome.trace.reported_symptoms, user_texts)
    return replace(outcome, trace=replace(outcome.trace, unstated_symptoms=unstated))


def continued_domain(current: Domain, analyzed: Domain) -> Domain:
    """Dominio de un hilo que continúa: un mensaje sin dominio ("gracias") no borra el del caso."""
    return current if analyzed is Domain.NONE else analyzed
