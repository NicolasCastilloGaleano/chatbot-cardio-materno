"""Caso de uso: conversación de una persona de la comunidad en la vista ciudadana de la web.

Reúne lo que esa vista puede hacer y nada más: abrir su propia conversación, decidir el
consentimiento (HU-01), decidir aparte si autoriza los informes agregados (ADR 0023) y
escribir en ella. Solo opera sobre chats del canal web: quien tiene
el identificador de su conversación no puede leer ni escribir en los chats de otros canales
que el equipo audita.
"""

from dataclasses import dataclass

from cardio_materno.application.conversation_service import Clock, TurnResult, utc_now
from cardio_materno.application.direct_chat import DirectChat
from cardio_materno.application.errors import ChatNotFoundError, ConsentRequiredError
from cardio_materno.application.ports.user_directory import UserDirectory
from cardio_materno.domain.consent import (
    has_consented,
    with_consent_decision,
    with_research_decision,
)
from cardio_materno.domain.user import Channel, ConsentStatus, User


@dataclass(frozen=True)
class CitizenPolicy:
    """Reglas de la vista ciudadana.

    Attributes:
        consent_required: Si escribir exige haber aceptado el consentimiento (HU-01).
        research_text: Texto de la autorización opcional para informes agregados; vacío
            si no se ofrece (regla de acceso apagada).
    """

    consent_required: bool = False
    research_text: str = ""


class CitizenChat:
    """Conversación propia de una persona en la web, con su consentimiento."""

    def __init__(
        self,
        chats: DirectChat,
        users: UserDirectory,
        policy: CitizenPolicy,
        clock: Clock = utc_now,
    ) -> None:
        """Crea el caso de uso.

        Args:
            chats: Chats directos (crear y escribir).
            users: Directorio de usuarios, para leer y guardar el consentimiento.
            policy: Consentimiento obligatorio y autorización opcional para informes.
            clock: Reloj (UTC).
        """
        self._chats = chats
        self._users = users
        self.policy = policy
        self._clock = clock

    def start(self) -> str:
        """Abre una conversación nueva y devuelve su identificador."""
        return self._chats.start(Channel.WEB)

    def consent_status(self, session_id: str) -> ConsentStatus:
        """Estado del consentimiento de la conversación.

        Raises:
            ChatNotFoundError: Si la conversación no existe o no es de la web.
        """
        return self._user(session_id).consent_status

    def decide_consent(self, session_id: str, accepted: bool) -> ConsentStatus:
        """Registra que la persona aceptó o rechazó el tratamiento de sus datos.

        Raises:
            ChatNotFoundError: Si la conversación no existe o no es de la web.
        """
        user = with_consent_decision(self._user(session_id), accepted, self._clock())
        self._users.save(user)
        return user.consent_status

    def research_status(self, session_id: str) -> ConsentStatus:
        """Estado de la autorización para informes agregados.

        Raises:
            ChatNotFoundError: Si la conversación no existe o no es de la web.
        """
        return self._user(session_id).research_consent

    def decide_research(self, session_id: str, accepted: bool) -> ConsentStatus:
        """Registra si la persona autoriza usar sus datos de acceso en informes agregados.

        Es independiente del consentimiento para ser atendida y se puede cambiar después:
        desde que la retira, los códigos dejan de guardarse y deja de contar en los informes.

        Raises:
            ChatNotFoundError: Si la conversación no existe o no es de la web.
        """
        user = with_research_decision(self._user(session_id), accepted, self._clock())
        self._users.save(user)
        return user.research_consent

    def send(self, session_id: str, text: str) -> TurnResult:
        """Procesa un mensaje de la persona.

        Raises:
            ChatNotFoundError: Si la conversación no existe o no es de la web.
            ConsentRequiredError: Si se exige el consentimiento y no se ha aceptado.
            ChatReadOnlyError: Si el equipo tiene abierta la conversación en una consola.
            LanguageModelError: Si el modelo falla y no hay alarma.
        """
        user = self._user(session_id)
        if self.policy.consent_required and not has_consented(user):
            raise ConsentRequiredError(session_id)
        return self._chats.send(session_id, text)

    def _user(self, session_id: str) -> User:
        """Usuario de una conversación de la web.

        Raises:
            ChatNotFoundError: Si no existe o pertenece a otro canal.
        """
        owner = self._users.get(session_id)
        if owner is None or owner.channel is not Channel.WEB:
            raise ChatNotFoundError(session_id)
        return owner.user
