"""Verificación determinista del respaldo de una respuesta en la evidencia (HU-02, ADR 0010).

El LLM redacta la respuesta frase por frase y cada frase de salud cita su registro. Estas
reglas comprueban, sin el LLM, que cada frase citada esté respaldada por el texto de ese
registro: casi todas sus palabras con contenido y todos sus números deben aparecer en él.
Las frases sin cita solo se aceptan si no pueden contener afirmaciones de salud.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from cardio_materno.domain.alarms import normalize_text

WORD_PATTERN = re.compile(r"[a-z]+|\d+")
NUMBER_PATTERN = re.compile(r"\d+")
REFUSAL_PATTERN = re.compile(r"\bno (puedo|podemos|es posible) (ayudar|orientar|responder|hablar)")
QUESTION_MARK = "?"


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

# Remitir a urgencias nunca minimiza un riesgo: estas palabras y números no cuentan en contra
# del respaldo de una frase citada ("acude de inmediato a urgencias o llama al 123").
REFERRAL_WORDS = word_set(
    """
    urgencias urgencia emergencias emergencia linea llama llamar acude acudir inmediato
    inmediata inmediatamente servicio cercano cercana centro salud atencion
    """
)
SAFE_NUMBERS = frozenset({"123"})


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
    """

    min_support: float = 0.6
    max_free_sentences: int = 2
    max_free_words: int = 20
    min_word_chars: int = 4
    stem_chars: int = 5


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
    stems = content_stems(sentence, policy) - _stems_of(REFERRAL_WORDS, policy)
    if not stems:
        return 1.0
    return len(stems & content_stems(evidence_text, policy)) / len(stems)


def is_supported(sentence: str, evidence_text: str, policy: GroundingPolicy) -> bool:
    """True si la frase citada está respaldada por el texto del registro que cita.

    Las palabras de remisión a urgencias y la línea 123 no cuentan en contra.
    """
    if not numbers_in(sentence) - SAFE_NUMBERS <= numbers_in(evidence_text):
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


def _stems_of(words: Iterable[str], policy: GroundingPolicy) -> frozenset[str]:
    """Raíces de una lista de palabras."""
    return frozenset(word[: policy.stem_chars] for word in words)
