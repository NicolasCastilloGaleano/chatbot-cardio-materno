"""Minimización de datos personales en el texto de la persona (Ley 1581/2012, AGENTS.md §4).

Reemplaza por una marca fija los identificadores que alguien puede escribir sin que se le
pidan: teléfono, correo, documento, dirección y nombre declarado. Se aplica antes de las
alarmas, del modelo de lenguaje y del guardado, así que el identificador nunca sale del
turno. Es una regla determinista y conservadora: no toca cifras de salud (presión, semanas,
peso, glucosa) porque solo reconoce formatos de identificador.

Los patrones son una primera versión técnica; su alcance lo revisa el responsable de
protección de datos (ver `docs/07-gobernanza/proteccion-datos.md`).
"""

import re

PHONE_MARK = "[teléfono]"
EMAIL_MARK = "[correo]"
DOCUMENT_MARK = "[documento]"
ADDRESS_MARK = "[dirección]"
NAME_MARK = "[nombre]"
NUMBER_MARK = "[número]"

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celular colombiano (10 dígitos que empiezan por 3) o fijo nacional (60 + indicativo + 7),
# con o sin +57 y con espacios, puntos o guiones entre grupos. Puede ir seguido del punto
# final de la frase, pero no de más cifras.
PHONE_PATTERN = re.compile(
    r"(?<![\d.])(?:\+?57[\s.-]?)?(?:3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}|60\d[\s.-]?\d{3}[\s.-]?\d{4})(?!\d|\.\d)"
)
# Documento anunciado por su nombre: "cédula 1.053.812.345", "CC: 30312456", "TI 1054…".
DOCUMENT_PATTERN = re.compile(
    r"(?i)\b(c[eé]dula(?:\s+de\s+ciudadan[ií]a)?|c\.?\s?c\.?|documento(?:\s+de\s+identidad)?"
    r"|tarjeta\s+de\s+identidad|t\.?\s?i\.?|nuip|pasaporte|registro\s+civil)"
    r"(\s*(?:n[uú]mero|no\.?|n[°º]|#|:|es))*\s*\d[\d.\s]{4,13}\d"
)
# Dirección urbana: "calle 12 # 34-56", "Cra. 23 No 45-67".
ADDRESS_PATTERN = re.compile(
    r"(?i)\b(?:calle|cll|cl|carrera|cra|kra|kr|avenida|av|transversal|tv|diagonal|dg)\.?\s*"
    r"\d+\s?[a-z]?(?:\s?bis)?\s*(?:#|n[°ºo]\.?|n[uú]mero)\s*\d+\s?[a-z]?(?:\s*-\s*\d+)?"
)
# Nombre que la persona declara. El nombre debe empezar con mayúscula para no confundir
# "me llamo la atención…" con un nombre.
NAME_PATTERN = re.compile(
    r"((?i:me\s+llamo|mi\s+nombre\s+es)\s+)"
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de\s+|del\s+|de\s+la\s+)?[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3}"
)
# Cualquier otra cifra larga (7 dígitos o más, con o sin puntos de miles): ningún dato de
# salud de la conversación tiene ese tamaño y sí lo tienen los documentos y los teléfonos.
LONG_NUMBER_PATTERN = re.compile(r"(?<![\d.,])(?:\d{7,12}|\d{1,3}(?:\.\d{3}){2,3})(?![\d.,]*\d)")


def redact_identifiers(text: str) -> str:
    """Reemplaza los identificadores personales del texto por marcas fijas.

    Args:
        text: Mensaje tal como lo escribió la persona.

    Returns:
        El mismo mensaje sin teléfonos, correos, documentos, direcciones ni nombres
        declarados. Un texto sin identificadores se devuelve igual.
    """
    redacted = EMAIL_PATTERN.sub(EMAIL_MARK, text)
    redacted = DOCUMENT_PATTERN.sub(lambda match: f"{match.group(1)} {DOCUMENT_MARK}", redacted)
    redacted = PHONE_PATTERN.sub(PHONE_MARK, redacted)
    redacted = ADDRESS_PATTERN.sub(ADDRESS_MARK, redacted)
    redacted = NAME_PATTERN.sub(lambda match: f"{match.group(1)}{NAME_MARK}", redacted)
    return LONG_NUMBER_PATTERN.sub(NUMBER_MARK, redacted)
