"""Verificación determinista del respaldo de una respuesta en la evidencia (HU-02, ADR 0010).

El LLM redacta la respuesta frase por frase y cada frase de salud cita su registro. Estas
reglas comprueban, sin el LLM, que cada frase citada esté respaldada por el texto de ese
registro: casi todas sus palabras con contenido y todos sus números deben aparecer en él.
Las frases de remisión ("acude a urgencias o llama al 123") no tienen excepción desde el
2026-10-26: se respaldan como cualquier otra. Los avisos de urgencia de las alarmas no pasan
por aquí, porque los compone la política de alarmas y no el agente. Las frases sin cita solo
se aceptan si no pueden contener afirmaciones de salud.

Cuando hay que mostrar el texto literal de un registro, solo se muestran sus frases
pertinentes a la consulta (B-028): las que comparten términos con ella y, siempre, las que
tienen un aviso de atención.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from cardio_materno.domain.alarms import normalize_text

WORD_PATTERN = re.compile(r"[a-z]+|\d+")
NUMBER_PATTERN = re.compile(r"\d+")
REFUSAL_PATTERN = re.compile(r"\bno (puedo|podemos|es posible) (ayudar|orientar|responder|hablar)")
QUESTION_MARK = "?"
# Marcadores de los ejemplos del prompt ("[N]", "[lo que describió la persona]").
PLACEHOLDER_PATTERN = re.compile(r"\[[^\]]*\]")
SPACES_PATTERN = re.compile(r"\s{2,}")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
# Avisos de atención (texto sin tildes): una frase del registro con alguno se muestra siempre
# en el texto literal, para no ocultar una remisión (B-028). Pendiente de revisión clínica.
ATTENTION_MARKERS = (
    "urgenc",
    "emergenc",
    "inmediat",
    "123",
    "acud",
    "personal de salud",
    "centro de salud",
    "servicio de salud",
)


def word_set(text: str) -> frozenset[str]:
    """Conjunto de palabras de un texto separado por espacios (listas de vocabulario)."""
    return frozenset(text.split())


# Palabras frecuentes sin contenido de salud: no cuentan para medir el respaldo.
STOPWORDS = word_set(
    """
    para como pero porque esto esta este estos estas esos esas aquel cuando donde desde hasta
    sobre entre tambien ademas puedo podemos posible puede puedes pueden podria podrias debe
    debes deben deberias tiene tienes tienen tener hace haces hacer cual cuales cuanto cuanta
    cuantos cuantas algo alguna alguno algunas algunos cada bien solo sino aunque mientras
    antes despues ahora luego siempre nunca segun ellos ellas usted ustedes nuestro nuestra
    eres estan estar estoy sera seran haya hayas muchas muchos mucho mucha poco poca pocos
    pocas otro otra otros otras mismo misma todo toda todos todas nada veces forma manera
    caso casos tipo cosa cosas parte importante recomendable recuerda recordar conviene
    """
)

# Palabras de cortesía y empatía que una frase sin cita puede usar.
CONVERSATIONAL_WORDS = word_set(
    """
    hola gracias entiendo comprendo lamento preocupacion pregunta preguntas consulta
    escribir escribirme contarme cuentame contar ayudarte ayudar orientarte orientar
    acompanarte servicio aqui gusto cuidate saludo saludos tranquila tranquilo
    """
)


@dataclass(frozen=True)
class GroundingPolicy:
    """Parámetros de la verificación (archivo `knowledge/evidence_policy.json`).

    Attributes:
        min_support: Fracción mínima de palabras con contenido de la frase que deben estar
            en el registro citado.
        max_free_sentences: Máximo de frases sin cita que se conservan.
        max_free_words: Longitud máxima (en palabras) de una frase sin cita.
        min_word_chars: Longitud mínima de una palabra para contar como contenido.
        stem_chars: Letras iniciales que se comparan (raíz simple: "embarazada" ≈ "embarazo").
        literal_min_overlap: Raíces que una frase del texto literal debe compartir con la
            consulta para mostrarse (B-028).
        max_inquiry_sentences: Máximo de frases de un turno de indagación (HU-11).
    """

    min_support: float = 0.6
    max_free_sentences: int = 2
    max_free_words: int = 20
    min_word_chars: int = 4
    stem_chars: int = 5
    literal_min_overlap: int = 1
    max_inquiry_sentences: int = 3


def content_stems(text: str, policy: GroundingPolicy) -> frozenset[str]:
    """Raíces de las palabras con contenido de un texto (sin tildes, sin palabras vacías)."""
    words = WORD_PATTERN.findall(normalize_text(text))
    return frozenset(
        word[: policy.stem_chars]
        for word in words
        if len(word) >= policy.min_word_chars and word not in STOPWORDS and not word.isdigit()
    )


def numbers_in(text: str) -> frozenset[str]:
    """Números que aparecen en un texto."""
    return frozenset(NUMBER_PATTERN.findall(text))


def support_ratio(sentence: str, evidence_text: str, policy: GroundingPolicy) -> float:
    """Fracción de las palabras con contenido de la frase que aparecen en la evidencia.

    Returns:
        Un valor entre 0 y 1 (1 si la frase no tiene palabras con contenido).
    """
    stems = content_stems(sentence, policy)
    if not stems:
        return 1.0
    return len(stems & content_stems(evidence_text, policy)) / len(stems)


def is_supported(sentence: str, evidence_text: str, policy: GroundingPolicy) -> bool:
    """True si la frase citada está respaldada por el texto del registro que cita.

    Todos sus números deben estar en el registro, incluida la línea 123.
    """
    if not numbers_in(sentence) <= numbers_in(evidence_text):
        return False
    return support_ratio(sentence, evidence_text, policy) >= policy.min_support


def is_allowed_without_citation(sentence: str, user_text: str, policy: GroundingPolicy) -> bool:
    """True si una frase sin cita no puede contener afirmaciones de salud.

    Se acepta si es corta y además es una pregunta sin números, usa solo palabras de cortesía,
    o dice que no puede ayudar con algo usando solo palabras de cortesía o del mensaje de la
    persona ("sobre el partido no puedo ayudarte").
    """
    if len(sentence.split()) > policy.max_free_words:
        return False
    stems = content_stems(sentence, policy)
    if sentence.rstrip().endswith(QUESTION_MARK):
        return not numbers_in(sentence)
    allowed = _stems_of(CONVERSATIONAL_WORDS, policy)
    if stems <= allowed:
        return True
    is_refusal = REFUSAL_PATTERN.search(normalize_text(sentence)) is not None
    return is_refusal and stems <= allowed | content_stems(user_text, policy)


def is_allowed_inquiry_sentence(
    sentence: str, said_numbers: frozenset[str], policy: GroundingPolicy
) -> bool:
    """True si la frase puede ir en un turno de indagación (HU-11, ADR 0017).

    Se acepta una pregunta corta cuyos números ya dijo la persona, o una frase corta que solo
    use palabras de cortesía. Así el turno nunca afirma nada de salud.
    """
    if len(sentence.split()) > policy.max_free_words:
        return False
    if not numbers_in(sentence) <= said_numbers:
        return False
    if sentence.rstrip().endswith(QUESTION_MARK):
        return True
    return content_stems(sentence, policy) <= _stems_of(CONVERSATIONAL_WORDS, policy)


def verify_inquiry(
    sentences: Iterable[str], user_texts: Iterable[str], policy: GroundingPolicy
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separa, en orden, las frases de indagación que se muestran y las que se descartan.

    Args:
        sentences: Frases que redactó el agente.
        user_texts: Mensajes de la persona en el hilo (sus números se aceptan).
        policy: Parámetros de la verificación (incluye el máximo de frases).

    Returns:
        Las frases aceptadas (hasta el máximo) y las descartadas.
    """
    said: frozenset[str] = frozenset().union(*(stated_numbers(text) for text in user_texts))
    kept: list[str] = []
    dropped: list[str] = []
    for sentence in sentences:
        room = len(kept) < policy.max_inquiry_sentences
        allowed = room and is_allowed_inquiry_sentence(sentence, said, policy)
        (kept if allowed else dropped).append(sentence)
    return tuple(kept), tuple(dropped)


def has_question(sentences: Iterable[str]) -> bool:
    """True si alguna frase es una pregunta."""
    return any(sentence.rstrip().endswith(QUESTION_MARK) for sentence in sentences)


def split_sentences(text: str) -> tuple[str, ...]:
    """Frases de un texto, cortadas después de un punto, un cierre de pregunta o exclamación."""
    return tuple(part.strip() for part in SENTENCE_BOUNDARY.split(text) if part.strip())


def has_attention_notice(sentence: str) -> bool:
    """True si la frase tiene un aviso de atención (urgencias, línea 123, personal de salud)."""
    normalized = normalize_text(sentence)
    return any(marker in normalized for marker in ATTENTION_MARKERS)


def pertinent_sentences(
    answer: str, query_text: str, policy: GroundingPolicy
) -> tuple[tuple[str, ...], int]:
    """Frases del registro que se muestran en el texto literal (B-028).

    Se muestran, en su orden y sin cambios, las frases que comparten al menos
    `literal_min_overlap` raíces con la consulta y, además, las que tienen un aviso de
    atención. Si ninguna comparte raíces con la consulta, se muestra el registro completo.

    Args:
        answer: Respuesta del registro.
        query_text: Consulta de búsqueda y mensaje de la persona.
        policy: Parámetros de la verificación.

    Returns:
        Las frases que se muestran y el total de frases del registro.
    """
    sentences = split_sentences(answer)
    query_stems = content_stems(query_text, policy)
    on_topic = {
        s
        for s in sentences
        if len(content_stems(s, policy) & query_stems) >= policy.literal_min_overlap
    }
    if not on_topic:
        return sentences, len(sentences)
    shown = tuple(s for s in sentences if s in on_topic or has_attention_notice(s))
    return shown, len(sentences)


def _stems_of(words: Iterable[str], policy: GroundingPolicy) -> frozenset[str]:
    """Raíces de una lista de palabras."""
    return frozenset(word[: policy.stem_chars] for word in words)


# Números escritos con palabras (sin "un/una", demasiado frecuentes como artículo).
NUMBER_WORDS = {
    "dos": "2",
    "tres": "3",
    "cuatro": "4",
    "cinco": "5",
    "seis": "6",
    "siete": "7",
    "ocho": "8",
    "nueve": "9",
    "diez": "10",
    "once": "11",
    "doce": "12",
    "quince": "15",
    "veinte": "20",
    "treinta": "30",
    "cuarenta": "40",
}


def stated_numbers(text: str) -> frozenset[str]:
    """Números de un texto, escritos con cifras o con palabras ("ocho meses" → "8")."""
    words = WORD_PATTERN.findall(normalize_text(text))
    spelled = {NUMBER_WORDS[word] for word in words if word in NUMBER_WORDS}
    return numbers_in(text) | spelled


def unstated_details(symptoms: Iterable[str], user_texts: Iterable[str]) -> tuple[str, ...]:
    """Síntomas con números que la persona no escribió o con marcadores del prompt.

    Sirve para detectar que el análisis inventó, arrastró o copió un dato (incidente del
    2026-10-11: "34 semanas" copiado de un ejemplo del prompt; comparación de modelos del
    2026-10-12: "desde hace [N] días"). Solo se marca para auditar: el síntoma sigue
    revisándose con las reglas de alarma.

    Args:
        symptoms: Síntomas reportados por el análisis.
        user_texts: Mensajes de la persona en el hilo (incluido el actual).

    Returns:
        Los síntomas que contienen algún número que no aparece en los mensajes.
    """
    said: frozenset[str] = frozenset().union(*(stated_numbers(text) for text in user_texts))
    return tuple(
        symptom
        for symptom in symptoms
        if has_placeholder(symptom) or not stated_numbers(symptom) <= said
    )


def has_placeholder(text: str) -> bool:
    """True si el texto trae un marcador de los ejemplos del prompt, como "[N]"."""
    return PLACEHOLDER_PATTERN.search(text) is not None


def remove_placeholders(text: str) -> str:
    """Quita los marcadores copiados de los ejemplos del prompt."""
    return SPACES_PATTERN.sub(" ", PLACEHOLDER_PATTERN.sub("", text)).strip(" ,:;")
