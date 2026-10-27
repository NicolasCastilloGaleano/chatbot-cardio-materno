"""Pruebas en vivo de la respuesta verificada (HU-02, ADR 0010).

Arman el asistente completo con los modelos reales. Lo que garantiza el código (abstención sin
LLM, verificación de cada frase, texto literal) ya está probado con dobles; aquí se mide cómo
se comporta el modelo real y se comprueba que los incidentes del 2026-10-11 no se repiten.
Ejecutar en el PC de pruebas: `pytest -m live -s`.
"""

import os
from pathlib import Path

import pytest

from cardio_materno.application.conversation_service import ConversationService, TurnResult
from cardio_materno.application.grounded_reply import ABSTENTION_TEXT, UNAVAILABLE_TEXT
from cardio_materno.bootstrap.main import PROJECT_ROOT, build_service
from cardio_materno.bootstrap.settings import load_conversation_settings

pytestmark = pytest.mark.live

# Consejos que aparecieron en el guion sin estar en la base (2026-10-11).
INVENTED_ADVICE = ("jengibre", "manzanilla", "yogur", "almendra", "batata", "nueces")
QUESTIONS = [
    "¿por qué es importante controlar la presión si no me duele nada?",
    "¿qué puedo comer si tengo acidez en el embarazo?",
    "tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?",
    "estaba cocinando frijoles y empecé a sentir acidez, tengo 34 semanas, ¿es normal?",
]


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConversationService:
    """Asistente completo con los modelos reales; los hilos van a una carpeta temporal."""
    monkeypatch.setenv("THREADS_DIR", str(tmp_path))
    return build_service(load_conversation_settings(os.environ, PROJECT_ROOT))


def describe(question: str, result: TurnResult) -> str:
    """Línea del reporte: cómo se resolvió la respuesta."""
    trace = result.trace
    if trace is None or trace.grounding is None:
        kind = {ABSTENTION_TEXT: "abstención", UNAVAILABLE_TEXT: "RAG no disponible"}.get(
            result.reply, "sin redacción"
        )
    else:
        check = trace.grounding
        kind = f"{check.supported}/{check.total} frases" + (" · literal" if check.literal else "")
        kind += "".join(f"\n    descartada: {sentence}" for sentence in check.dropped)
    return f"{question} → {kind}\n    {result.reply}"


@pytest.mark.parametrize("question", QUESTIONS)
def test_reply_never_contains_invented_advice(service: ConversationService, question: str) -> None:
    result = service.send(question)

    print(describe(question, result))
    assert not any(word in result.reply.lower() for word in INVENTED_ADVICE)
