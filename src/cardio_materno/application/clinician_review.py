"""Revisión de los casos escalados por el profesional de salud (HU-16, ADR 0022).

El profesional ve los casos abiertos, pide el borrador y decide: aprobarlo tal cual o
modificarlo, o abre un contacto directo. El mensaje se guarda en el hilo de la persona con el
rol `profesional`, nunca como del asistente. En WhatsApp, además, va a la bandeja de salida que
envía el proceso del canal, mientras haya dirección y la ventana siga abierta (ADR 0023).
"""

import logging
from dataclasses import replace

from cardio_materno.application.clinician_draft import ClinicianDraftWriter
from cardio_materno.application.conversation_service import Clock, utc_now
from cardio_materno.application.errors import (
    CaseChannelNotSupportedError,
    CaseConflictError,
    CaseNotFoundError,
    DraftNotReadyError,
    DraftRegenerationError,
    LanguageModelError,
)
from cardio_materno.application.ports.case_inbox import CaseInbox, InboxCase
from cardio_materno.application.ports.clinician_outbox import ClinicianOutbox, OutboxItem
from cardio_materno.application.ports.user_thread_store import UserThreadStore
from cardio_materno.domain.conversation import ChatMessage, Role
from cardio_materno.domain.escalation import (
    CaseAction,
    CaseStatus,
    ClinicalCase,
    DraftStatus,
    InvalidCaseTransitionError,
    apply_action,
)
from cardio_materno.domain.user import DIRECT_CHANNELS, Channel

logger = logging.getLogger(__name__)
MSG_EXPIRED = "El caso venció: pasó la ventana desde el último mensaje de la persona."
MSG_CHANGED = "El caso cambió mientras lo revisabas. Vuelve a abrirlo."
MSG_CHANNEL = "No se puede responder por el canal de esta persona."
MSG_WINDOW = "No se puede escribir por WhatsApp: no hay dirección guardada o se cerró la ventana."
MSG_NOT_IN_CONTACT = "El caso no está en contacto directo."
MSG_CLOSED = "El caso ya está cerrado."


class ClinicianReview:
    """Casos del profesional: listar, borrador, aprobar, modificar y contacto directo."""

    def __init__(
        self,
        inbox: CaseInbox,
        threads: UserThreadStore,
        writer: ClinicianDraftWriter,
        clock: Clock = utc_now,
        outbox: ClinicianOutbox | None = None,
    ) -> None:
        """Crea el caso de uso.

        Args:
            inbox: Casos de todas las personas.
            threads: Hilos por persona, para entregar el mensaje del profesional.
            writer: Redactor del borrador.
            clock: Reloj (UTC).
            outbox: Bandeja de salida de WhatsApp; None si no se puede responder por ahí.
        """
        self._inbox = inbox
        self._threads = threads
        self._writer = writer
        self._clock = clock
        self._outbox = outbox

    def pending_cases(self) -> list[InboxCase]:
        """Vence los casos cuyo plazo pasó y devuelve los abiertos."""
        self._inbox.expire_due(self._clock())
        return self._inbox.list_open()

    def case(self, case_id: str) -> InboxCase:
        """Un caso por su id.

        Raises:
            CaseNotFoundError: Si no existe.
        """
        found = self._inbox.get(case_id)
        if found is None:
            raise CaseNotFoundError(case_id)
        return found

    def prepare_draft(self, case_id: str) -> InboxCase:
        """Genera el borrador la primera vez que se pide; si falla, queda marcado como fallido.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso cambió mientras se generaba.
        """
        found = self.case(case_id)
        if found.case.draft_status is DraftStatus.READY:
            return found
        updated = self._with_draft(found.case)
        self._save(found, updated)
        return replace(found, case=updated)

    def regenerate_draft(self, case_id: str) -> InboxCase:
        """Reemplaza el borrador y la nota por unos nuevos (p. ej., tras cambiar el prompt).

        Sin borrador listo, equivale a `prepare_draft`. Si el modelo falla, el caso conserva el
        borrador y la nota anteriores.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso está cerrado o cambió mientras se generaba.
            DraftRegenerationError: Si el modelo no pudo escribir uno nuevo.
        """
        found = self.case(case_id)
        if not found.case.is_open:
            raise CaseConflictError(MSG_CLOSED)
        if found.case.draft_status is not DraftStatus.READY:
            return self.prepare_draft(case_id)
        updated = self._with_draft(found.case)
        if updated.draft_status is DraftStatus.FAILED:
            raise DraftRegenerationError(case_id)
        self._save(found, updated)
        return replace(found, case=updated)

    def approve(self, case_id: str) -> InboxCase:
        """Envía el borrador tal cual y resuelve el caso.

        Raises:
            CaseNotFoundError: Si no existe.
            DraftNotReadyError: Si no hay borrador listo.
            CaseConflictError: Si el caso ya no admite la acción o venció.
            CaseChannelNotSupportedError: Si todavía no se puede responder por su canal.
        """
        found = self.case(case_id)
        if found.case.draft_status is not DraftStatus.READY:
            raise DraftNotReadyError(case_id)
        return self._resolve(found, CaseAction.APPROVE, found.case.draft)

    def modify(self, case_id: str, text: str) -> InboxCase:
        """Envía el texto del profesional en vez del borrador y resuelve el caso.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso ya no admite la acción o venció.
            CaseChannelNotSupportedError: Si todavía no se puede responder por su canal.
        """
        return self._resolve(self.case(case_id), CaseAction.MODIFY, text.strip())

    def start_contact(self, case_id: str) -> InboxCase:
        """Abre el contacto directo: los mensajes nuevos de la persona van al profesional.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso ya no admite la acción o venció.
            CaseChannelNotSupportedError: Si todavía no se puede responder por su canal.
        """
        return self._transition(self.case(case_id), CaseAction.START_CONTACT)

    def send_message(self, case_id: str, text: str) -> InboxCase:
        """Envía un mensaje del profesional durante el contacto directo.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso no está en contacto directo o venció.
        """
        found = self.case(case_id)
        if found.case.status is not CaseStatus.IN_CONTACT:
            raise CaseConflictError(MSG_NOT_IN_CONTACT)
        if found.case.is_expired(self._clock()):
            raise CaseConflictError(MSG_EXPIRED)
        self._check_channel(found)
        self._deliver(found, text.strip())
        return found

    def deliverable(self, found: InboxCase) -> bool:
        """True si hoy se le puede escribir a la persona por su canal."""
        if found.channel in DIRECT_CHANNELS:
            return True
        outbox = self._outbox
        is_whatsapp = found.channel is Channel.WHATSAPP
        return is_whatsapp and outbox is not None and outbox.reachable(found.case.id, self._clock())

    def end_contact(self, case_id: str) -> InboxCase:
        """Cierra el contacto directo: el asistente vuelve a responder en el siguiente mensaje.

        Raises:
            CaseNotFoundError: Si no existe.
            CaseConflictError: Si el caso no está en contacto directo.
        """
        found = self.case(case_id)
        try:
            updated = apply_action(found.case, CaseAction.CLOSE, self._clock())
        except InvalidCaseTransitionError as error:
            raise CaseConflictError(MSG_NOT_IN_CONTACT) from error
        self._save(found, updated)
        return replace(found, case=updated)

    def _with_draft(self, case: ClinicalCase) -> ClinicalCase:
        """El caso con su borrador y su nota listos o, si el modelo falla, marcado como fallido."""
        try:
            written = self._writer.write(case.snapshot)
        except LanguageModelError as error:
            logger.warning("No se pudo generar el borrador del caso %s: %s", case.id, error)
            return replace(case, draft_status=DraftStatus.FAILED)
        return replace(
            case, draft=written.reply, draft_note=written.note, draft_status=DraftStatus.READY
        )

    def _resolve(self, found: InboxCase, action: CaseAction, text: str) -> InboxCase:
        """Aplica la acción y entrega el mensaje del profesional."""
        resolved = self._transition(found, action)
        self._deliver(found, text)
        return resolved

    def _transition(self, found: InboxCase, action: CaseAction) -> InboxCase:
        """Aplica una acción del profesional si el canal lo admite y el caso no venció."""
        self._check_channel(found)
        now = self._clock()
        if found.case.is_expired(now):
            raise CaseConflictError(MSG_EXPIRED)
        try:
            updated = apply_action(found.case, action, now)
        except InvalidCaseTransitionError as error:
            raise CaseConflictError(str(error)) from error
        self._save(found, updated)
        return replace(found, case=updated)

    def _check_channel(self, found: InboxCase) -> None:
        """Falla si hoy no se le puede escribir a la persona por su canal."""
        if self.deliverable(found):
            return
        if found.channel is Channel.WHATSAPP and self._outbox is not None:
            raise CaseChannelNotSupportedError(MSG_WINDOW)
        raise CaseChannelNotSupportedError(MSG_CHANNEL)

    def _deliver(self, found: InboxCase, text: str) -> None:
        """Guarda el mensaje en el hilo del caso y, si es de WhatsApp, lo deja para enviar."""
        now = self._clock()
        case = found.case
        message = ChatMessage(Role.CLINICIAN, text, case.thread_id, now)
        self._threads.scoped(found.user_id).append_message(message)
        if found.channel not in DIRECT_CHANNELS and self._outbox is not None:
            item = OutboxItem(0, case.id, found.user_id, case.thread_id, text)
            self._outbox.enqueue(item, now)

    def _save(self, found: InboxCase, updated: ClinicalCase) -> None:
        """Guarda el caso solo si nadie lo cambió desde que se leyó."""
        if not self._inbox.update_if(updated, found.case.status):
            raise CaseConflictError(MSG_CHANGED)
