"""Respuesta de salud siempre respaldada: verificación, texto literal y abstención (ADR 0010).

- Sin evidencia suficiente no se llama al LLM: se muestra `ABSTENTION_TEXT`, que pide más
  detalles para volver a buscar. Si el buscador no está disponible, `UNAVAILABLE_TEXT`.
- Con evidencia, el LLM redacta frase por frase y cada frase de salud cita su registro. Si una
  frase citada no está respaldada por ese registro, se muestra el **texto literal** del
  registro, para no perder ni deformar lo que dice (p. ej., un aviso de atención inmediata).
  Del registro se muestran solo las frases pertinentes a la consulta y los avisos (B-028).
- Las frases sin cita solo se conservan si no pueden contener afirmaciones de salud.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from cardio_materno.application.agent_turn import DraftSentence
from cardio_materno.domain.grounding import (
    GroundingPolicy,
    is_allowed_without_citation,
    is_supported,
    pertinent_sentences,
    without_questions,
)
from cardio_materno.domain.knowledge import EvidenceItem, KnowledgeEntry
from cardio_materno.domain.trace import GroundingCheck, RetrievalStatus

# Sin evidencia suficiente: se pide más detalle en lugar de cerrar la conversación.
ABSTENTION_TEXT = (
    "No tengo información validada sobre eso en la base de conocimiento del proyecto. "
    "Te recomiendo consultarlo con el personal de salud de tu EPS o centro de salud. "
    "¿Me puedes contar con otras palabras qué sientes, desde cuándo y a quién le pasa?"
)
# El buscador no está disponible: pedir más detalles no ayudaría.
UNAVAILABLE_TEXT = (
    "En este momento no puedo consultar la información para orientarte. "
    "Te recomiendo consultarlo con el personal de salud de tu EPS o centro de salud."
)
# Cierre honesto de la indagación (HU-11, ADR 0017): sin LLM. Pendiente de revisión clínica.
CLOSING_TEXT = (
    "Con lo que me cuentas no encuentro información validada en la base del proyecto para "
    "orientarte sobre esto. Te recomiendo consultarlo con el personal de salud de tu EPS o "
    "centro de salud. Si tienes otra duda sobre el corazón, la presión arterial, el embarazo o "
    "tu bebé, con gusto te ayudo."
)
LITERAL_TEMPLATE = "Según la información validada del proyecto: {answer}"
SENTENCE_SEPARATOR = " "


@dataclass(frozen=True)
class GroundedReply:
    """Respuesta verificada que se mostrará.

    Attributes:
        text: Texto para la persona.
        cited: Etiquetas de los registros que respaldan el texto.
        check: Resultado de la verificación (para la traza).
    """

    text: str
    cited: tuple[str, ...]
    check: GroundingCheck


@dataclass(frozen=True)
class SentenceVerdict:
    """Frase redactada y si se puede mostrar."""

    sentence: DraftSentence
    accepted: bool


def abstention_text(status: RetrievalStatus) -> str:
    """Mensaje fijo cuando no hay evidencia suficiente (no se llama al LLM, ADR 0010).

    Args:
        status: Resultado de la búsqueda (insuficiente o no disponible).

    Returns:
        `UNAVAILABLE_TEXT` si el buscador no está disponible; si no, `ABSTENTION_TEXT`.
    """
    return UNAVAILABLE_TEXT if status is RetrievalStatus.UNAVAILABLE else ABSTENTION_TEXT


def compose_grounded_reply(
    draft: Sequence[DraftSentence],
    items: Sequence[EvidenceItem],
    user_text: str,
    policy: GroundingPolicy,
    query_text: str = "",
) -> GroundedReply:
    """Verifica la redacción del agente y arma la respuesta (o usa el texto literal).

    Args:
        draft: Frases redactadas por el agente (citas ya validadas contra las etiquetas).
        items: Evidencia ofrecida al agente (al menos un registro).
        user_text: Mensaje de la persona (permite nombrar su tema al decir "no puedo ayudar").
        policy: Parámetros de la verificación.
        query_text: Consulta de búsqueda; con el mensaje, elige las frases del literal.

    Returns:
        La respuesta con las frases aceptadas, o el texto literal del registro principal si
        alguna frase citada no está respaldada o no queda ninguna frase.
    """
    verdicts = verify_sentences(draft, items, user_text, policy)
    accepted = [v.sentence for v in verdicts if v.accepted]
    kept = accepted if policy.allow_questions else [s for s in accepted if not is_question(s)]
    dropped = tuple(v.sentence.text for v in verdicts if not v.accepted) + tuple(
        s.text for s in accepted if s not in kept
    )
    failed_citation = any(v.sentence.evidence_id for v in verdicts if not v.accepted)
    if failed_citation or not kept:
        check = GroundingCheck(len(kept), len(draft), True, dropped)
        return literal_reply(draft, items, f"{query_text} {user_text}", check, policy)
    cited = tuple(dict.fromkeys(s.evidence_id for s in kept if s.evidence_id))
    text = SENTENCE_SEPARATOR.join(s.text for s in kept)
    return GroundedReply(text, cited, GroundingCheck(len(kept), len(draft), False, dropped))


def verify_sentences(
    draft: Sequence[DraftSentence],
    items: Sequence[EvidenceItem],
    user_text: str,
    policy: GroundingPolicy,
) -> list[SentenceVerdict]:
    """Decide, frase por frase y en orden, cuáles se pueden mostrar."""
    verdicts: list[SentenceVerdict] = []
    free_kept = 0
    for sentence in draft:
        if sentence.evidence_id is not None:
            evidence = evidence_text(entry_of(sentence.evidence_id, items))
            accepted = is_supported(sentence.text, evidence, policy)
        else:
            accepted = free_kept < policy.max_free_sentences and is_allowed_without_citation(
                sentence.text, user_text, policy
            )
            free_kept += int(accepted)
        verdicts.append(SentenceVerdict(sentence, accepted))
    return verdicts


def literal_reply(
    draft: Sequence[DraftSentence],
    items: Sequence[EvidenceItem],
    query_text: str,
    check: GroundingCheck,
    policy: GroundingPolicy,
) -> GroundedReply:
    """Texto literal del registro principal, solo con sus frases pertinentes (B-028)."""
    label = main_label(draft, items)
    shown, total = pertinent_sentences(entry_of(label, items).answer, query_text, policy)
    full_check = replace(check, literal_shown=len(shown), literal_total=total)
    return GroundedReply(literal_text(shown) if shown else "", (label,), full_check)


def is_question(sentence: DraftSentence) -> bool:
    """True si la frase redactada es una pregunta."""
    return not without_questions([sentence.text])


def main_label(draft: Sequence[DraftSentence], items: Sequence[EvidenceItem]) -> str:
    """Etiqueta del registro principal: el de mayor similitud; ante un empate, uno citado.

    Se usa cuando la redacción falló, y entonces la cita del agente no es confiable. Caso real
    (2026-10-24): "tengo acidez en el embarazo" citó un registro de preeclampsia (0,55)
    habiendo uno de acidez (0,60), y el texto literal remitió a urgencias.
    """
    cited = {s.evidence_id for s in draft if s.evidence_id}
    return max(items, key=lambda item: (item.score, item.label in cited)).label


def entry_of(label: str, items: Sequence[EvidenceItem]) -> KnowledgeEntry:
    """Registro con la etiqueta dada.

    Raises:
        KeyError: Si la etiqueta no está entre la evidencia ofrecida.
    """
    for item in items:
        if item.label == label:
            return item.entry
    raise KeyError(label)


def evidence_text(entry: KnowledgeEntry) -> str:
    """Texto contra el que se verifica una frase: pregunta y respuesta del registro."""
    return f"{entry.question}\n{entry.answer}"


def literal_text(sentences: Sequence[str]) -> str:
    """Frases literales del registro, presentadas como información validada."""
    return LITERAL_TEMPLATE.format(answer=SENTENCE_SEPARATOR.join(sentences))
