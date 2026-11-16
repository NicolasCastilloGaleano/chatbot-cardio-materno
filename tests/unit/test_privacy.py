"""Minimización de identificadores en el texto de la persona (datos sintéticos)."""

import pytest

from cardio_materno.domain.privacy import redact_identifiers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mi celular es 3104567890", "mi celular es [teléfono]"),
        ("llámeme al +57 310 456 7890 por favor", "llámeme al [teléfono] por favor"),
        ("el fijo es 606 885 1234", "el fijo es [teléfono]"),
        ("escríbame a maria.perez+salud@correo.com.co", "escríbame a [correo]"),
        ("mi cédula es 1.053.812.345 y me duele", "mi cédula [documento] y me duele"),
        ("CC: 30312456", "CC [documento]"),
        ("vivo en la calle 12 # 34-56 de Manizales", "vivo en la [dirección] de Manizales"),
        ("Cra. 23 No 45-67, tengo presión alta", "[dirección], tengo presión alta"),
        ("Hola, me llamo María del Carmen Ríos", "Hola, me llamo [nombre]"),
        ("mi nombre es Juan y tengo 30 semanas", "mi nombre es [nombre] y tengo 30 semanas"),
        ("anote 1053812345", "anote [número]"),
        ("mi celular es 300 000 0001. Tengo fiebre", "mi celular es [teléfono]. Tengo fiebre"),
        ("llámeme al 3104567890.", "llámeme al [teléfono]."),
    ],
)
def test_identifiers_are_replaced_by_fixed_marks(text: str, expected: str) -> None:
    assert redact_identifiers(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "tengo la presión en 180/110 desde ayer",
        "tengo 34 semanas y el bebé pesa 2.300 gramos",
        "la glucosa me salió en 250 y las plaquetas en 150.000",
        "el niño tiene 39,5 de fiebre hace 3 días",
        "me llamo la atención que se me hinchan los pies",
        "soy hipertensa y tomo losartán de 50 mg cada 12 horas",
        "nació en 2026 y tiene 2 meses",
        "tengo 3 hijos y 65 años",
    ],
)
def test_health_figures_are_never_touched(text: str) -> None:
    assert redact_identifiers(text) == text


def test_several_identifiers_in_one_message() -> None:
    text = "Me llamo Ana Gómez, cédula 30312456, cel 3001234567: me duele el pecho"
    assert redact_identifiers(text) == (
        "Me llamo [nombre], cédula [documento], cel [teléfono]: me duele el pecho"
    )
