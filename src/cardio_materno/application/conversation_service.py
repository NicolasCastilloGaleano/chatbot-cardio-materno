"""Caso de uso: conversación en hilos con alarmas deterministas (HU-06, HU-03/04).

En cada turno:
1. **Filtro 1:** las reglas de alarma revisan el texto original del usuario. Si hay una
   urgencia inmediata, se responde con el mensaje fijo y no se consulta al agente.
2. El agente recibe solo el contexto del hilo actual (su JSON y sus últimos N mensajes) y
   responde en JSON: decide el hilo, resume, responde y lista los síntomas reportados.
3. **Filtro 2:** las mismas reglas revisan `reported_symptoms`. El agente solo puede
   sumar alarmas, nunca quitarlas (ADR 0007).
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cardio_materno.application.agent_turn import (
    AGENT_TURN_SCHEMA,
    AgentTurn,
    ThreadAction,
    parse_agent_turn,
)
from cardio_materno.application.alarm_policy import AlarmDecision, AlarmPolicy, compose_reply
from cardio_materno.application.errors import LanguageModelError
from cardio_materno.application.ports.language_model import LanguageModel
from cardio_materno.application.ports.thread_repository import ThreadRepository
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

# Mensajes del hilo actual que se envían como contexto (3 turnos de pregunta y respuesta).
DEFAULT_CONTEXT_MESSAGES = 6
THREAD_CONTEXT_TEMPLATE = "HILO ACTUAL (JSON):\n{thread_json}"
NO_THREAD_CONTEXT = "HILO ACTUAL: no hay un hilo activo. Este mensaje inicia un hilo nuevo."
ALARM_SUMMARY_TEMPLATE = "Alerta: {sign}."
SYMPTOM_SEPARATOR = "; "

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


@dataclass(frozen=True)
class TurnResult:
    """Resultado de un turno de conversación.

    Attributes:
        reply: Respuesta para el usuario.
        thread: Hilo en el que quedó registrado el turno.
        is_new_thread: True si el turno abrió un hilo nuevo.
        alerts: Alertas registradas en el turno (vacío si no hubo alarma).
        reported_symptoms: Síntomas que identificó el agente (None si no se le consultó).
    """

    reply: str
    thread: ConversationThread
    is_new_thread: bool
    alerts: tuple[Alert, ...] = ()
    reported_symptoms: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TurnRecord:
    """Lo que se guarda de un turno (agrupa datos para mantener funciones pequeñas).

    Attributes:
        user_text: Mensaje del usuario.
        reply: Respuesta mostrada.
        decisions: Decisiones de alarma del turno.
        reported_symptoms: Síntomas del agente (None si no se le consultó).
    """

    user_text: str
    reply: str
    decisions: tuple[AlarmDecision, ...]
    reported_symptoms: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ConversationConfig:
    """Parámetros del caso de uso (agrupados para mantener constructores pequeños).

    Attributes:
        system_prompt: Instrucciones de sistema del agente.
        context_messages: Cuántos mensajes recientes del hilo se envían como contexto.
        alarm_policy: Reglas de alarma y mensajes fijos.
        clock: Fuente de la fecha y hora (se reemplaza en las pruebas).
        new_id: Generador de identificadores de hilo (se reemplaza en las pruebas).
    """

    system_prompt: str
    context_messages: int = DEFAULT_CONTEXT_MESSAGES
    alarm_policy: AlarmPolicy = field(default_factory=no_alarm_policy)
    clock: Clock = utc_now
    new_id: IdGenerator = new_uuid


class ConversationService:
    """Coordina alarmas, agente y repositorio de hilos para una sesión de un usuario."""

    def __init__(
        self,
        language_model: LanguageModel,
        repository: ThreadRepository,
        config: ConversationConfig,
    ) -> None:
        """Crea el servicio.

        Args:
            language_model: Implementación del puerto de LLM.
            repository: Implementación del repositorio de hilos.
            config: Prompt, tamaño del contexto, política de alarmas, reloj y generador de ids.
        """
        self._language_model = language_model
        self._repository = repository
        self._system_message = ChatMessage(Role.SYSTEM, config.system_prompt)
        self._context_messages = config.context_messages
        self._alarm_policy = config.alarm_policy
        self._clock = config.clock
        self._new_id = config.new_id
        self._active_thread_id: str | None = None

    def send(self, user_text: str) -> TurnResult:
        """Procesa un mensaje del usuario y devuelve la respuesta.

        Si el modelo falla y no hay alarma, no se guarda nada y el hilo activo no cambia.
        Si hay alarma, el mensaje fijo se muestra aunque el modelo falle.

        Args:
            user_text: Texto escrito por el usuario.

        Returns:
            La respuesta, el hilo del turno y las alertas registradas.

        Raises:
            LanguageModelError: Si el modelo falla (o responde mal) y no hay alarma.
        """
        current = self._active_thread()
        pre = self._alarm_policy.evaluate([user_text], AlertOrigin.USER)
        if pre is not None and pre.is_immediate:
            return self._alarm_only_turn(current, user_text, pre)
        try:
            turn = self._ask_agent(current, user_text)
        except LanguageModelError:
            if pre is None:
                raise
            return self._alarm_only_turn(current, user_text, pre)
        return self._agent_turn(current, user_text, turn, pre)

    def end_session(self) -> None:
        """Cierra el hilo activo, si existe (p. ej., cuando el usuario escribe "salir")."""
        current = self._active_thread()
        if current is not None:
            self._repository.save_thread(close_thread(current, self._clock()))
        self._active_thread_id = None

    def _active_thread(self) -> ConversationThread | None:
        """Obtiene el hilo activo de la sesión, si lo hay y sigue abierto."""
        if self._active_thread_id is None:
            return None
        thread = self._repository.get_thread(self._active_thread_id)
        return thread if thread is not None and thread.is_open else None

    def _ask_agent(self, current: ConversationThread | None, user_text: str) -> AgentTurn:
        """Consulta al agente con el contexto acotado del hilo y valida su JSON."""
        context = self._build_context(current, user_text)
        return parse_agent_turn(self._language_model.complete_json(context, AGENT_TURN_SCHEMA))

    def _agent_turn(
        self,
        current: ConversationThread | None,
        user_text: str,
        turn: AgentTurn,
        pre: AlarmDecision | None,
    ) -> TurnResult:
        """Aplica el filtro 2 sobre los síntomas reportados y registra el turno del agente."""
        decisions = [d for d in (pre, self._post_filter(turn, pre)) if d is not None]
        thread, is_new = self._resolve_thread(current, turn)
        reply = compose_reply(decisions, turn.reply)
        record = TurnRecord(user_text, reply, tuple(decisions), turn.reported_symptoms)
        alerts = self._record_turn(thread.id, record)
        return TurnResult(reply, thread, is_new, alerts, turn.reported_symptoms)

    def _post_filter(self, turn: AgentTurn, pre: AlarmDecision | None) -> AlarmDecision | None:
        """Filtro 2: revisa `reported_symptoms` sin repetir las reglas ya detectadas."""
        if not turn.reported_symptoms:
            return None
        symptoms = SYMPTOM_SEPARATOR.join(turn.reported_symptoms)
        exclude = pre.rule_ids if pre is not None else ()
        return self._alarm_policy.evaluate([symptoms], AlertOrigin.AGENT, exclude)

    def _alarm_only_turn(
        self, current: ConversationThread | None, user_text: str, decision: AlarmDecision
    ) -> TurnResult:
        """Responde solo con el mensaje fijo (sin agente) y registra la alerta."""
        thread, is_new = self._thread_for_alarm(current, decision)
        reply = compose_reply([decision], agent_reply=None)
        alerts = self._record_turn(thread.id, TurnRecord(user_text, reply, (decision,)))
        return TurnResult(reply, thread, is_new, alerts)

    def _thread_for_alarm(
        self, current: ConversationThread | None, decision: AlarmDecision
    ) -> tuple[ConversationThread, bool]:
        """Usa el hilo activo o abre uno nuevo con un resumen determinista de la alarma."""
        if current is not None:
            return current, False
        summary = ALARM_SUMMARY_TEMPLATE.format(sign=decision.primary_rule.sign)
        return self._open_new_thread(decision.domain, summary), True

    def _build_context(
        self, current: ConversationThread | None, user_text: str
    ) -> list[ChatMessage]:
        """Arma el contexto: sistema + JSON del hilo + últimos N mensajes + mensaje nuevo."""
        recent = (
            self._repository.recent_messages(current.id, self._context_messages) if current else []
        )
        return [
            self._system_message,
            ChatMessage(Role.SYSTEM, describe_thread(current)),
            *recent,
            ChatMessage(Role.USER, user_text),
        ]

    def _resolve_thread(
        self, current: ConversationThread | None, turn: AgentTurn
    ) -> tuple[ConversationThread, bool]:
        """Aplica la decisión del agente: actualiza el hilo actual o lo cierra y abre otro."""
        now = self._clock()
        if current is not None and turn.thread_action is ThreadAction.CONTINUE:
            thread = update_thread(current, turn.domain, turn.summary, now)
            self._repository.save_thread(thread)
            return thread, False
        if current is not None:
            self._repository.save_thread(close_thread(current, now))
        return self._open_new_thread(turn.domain, turn.summary), True

    def _open_new_thread(self, domain: Domain, summary: str) -> ConversationThread:
        """Crea, guarda y activa un hilo nuevo."""
        thread = open_thread(self._new_id(), domain, summary, self._clock())
        self._repository.save_thread(thread)
        self._active_thread_id = thread.id
        return thread

    def _record_turn(self, thread_id: str, record: TurnRecord) -> tuple[Alert, ...]:
        """Guarda los mensajes del turno (con los síntomas del agente) y sus alertas."""
        now = self._clock()
        user_message = ChatMessage(Role.USER, record.user_text, thread_id, now)
        reply_message = ChatMessage(
            Role.ASSISTANT, record.reply, thread_id, now, record.reported_symptoms
        )
        self._repository.append_message(user_message)
        self._repository.append_message(reply_message)
        alerts = tuple(Alert(d.rule_ids, d.severity, d.origin, now) for d in record.decisions)
        for alert in alerts:
            self._repository.append_alert(thread_id, alert)
        return alerts


def describe_thread(thread: ConversationThread | None) -> str:
    """Describe el hilo actual para el agente, en JSON (o indica que no hay hilo).

    Args:
        thread: Hilo activo o None.

    Returns:
        Texto que se envía al agente como mensaje de sistema.
    """
    if thread is None:
        return NO_THREAD_CONTEXT
    snapshot = {
        "id": thread.id,
        "domain": str(thread.domain),
        "summary": thread.summary,
        "status": str(thread.status),
    }
    return THREAD_CONTEXT_TEMPLATE.format(thread_json=json.dumps(snapshot, ensure_ascii=False))
