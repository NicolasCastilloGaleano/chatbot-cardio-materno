# Chatbot Cardio‑Materno

Asistente de **teleorientación con IA** en **salud cardiovascular y materno‑infantil** para comunidades del departamento de Caldas (Colombia).

> Proyecto Integrador II, Universidad de Caldas. Corresponde al **Objetivo Específico 2** del proyecto *"Herramienta tecnológica para la apropiación social del conocimiento en salud cardiovascular y materno‑infantil"* (Convocatoria Minciencias 2025). Aliados: Fundación Soy Mujer en la Ciencia y Dirección Territorial de Salud de Caldas.

⚠️ **Aviso:** esta herramienta ofrece **orientación** (Res. 2654/2019) y **no reemplaza** la consulta médica ni hace diagnósticos.

## Estado
| Fase | Estado |
|---|---|
| Estructura, reglas y documentación base | ✅ Hecha |
| Especificación ejecutable v1 | ⏳ Pendiente |
| Chat libre por **consola** con Ollama (HU-00, prototipo técnico) | ✅ Hecho |
| **Hilos conversacionales** con respuesta JSON del agente (HU-06) | ✅ Hecho |
| **Alarmas deterministas** con doble filtro (HU-03/HU-04) | ✅ Hecho (técnico); reglas PROVISIONALES, falta la validación clínica |
| **Orientación con evidencia (RAG)**, separación análisis/respuesta y **respuesta verificada** (HU-02, ADR 0010) | ✅ Hecho (verificado en el PC de pruebas el 2026-10-12) |
| **Control de alcance** por intención (HU-07) | ✅ Hecho (verificado en el PC de pruebas el 2026-10-12) |
| **Filtro 2 con códigos cerrados** (B-015, ADR 0012, catálogo v0.5.0) | 🟡 Implementado para la demostración; pendiente de ratificación del equipo |
| **Latencia**: embedder en CPU, precalentamiento, configuración por etapa en `.env` y comparación de modelos (B-022, ADR 0011) | ✅ Hecho (ADR 0011 aceptado): análisis `mistral-small3.1:24b`, respuesta `qwen3:8b`; turno p50 de unos 46 s (la meta de 15 s queda pendiente) |
| **Interfaz web local de chat y auditoría** (HU-08 y HU-10, ADR 0013 y 0016): auditoría de los chats de todos los canales; se puede escribir en los de consola y web | ✅ Hecho (HU-10 verificada en el PC de pruebas el 2026-10-26) |
| **Indagación guiada por la evidencia** (HU-11, ADR 0017) | 🔄 Fase 2 (modo `observar`) en `main`; fase 3 (`activo`) y acompañamiento de la urgencia (B-030) implementados en `feat/hu-11-activo`, falta verificarlos en el PC |
| Flujo conversacional clínico por **consola** | ⏳ Pendiente |
| Canal **Telegram** (pruebas multiusuario) | ⏳ Pendiente |
| Canal **WhatsApp** (prototipo final, HU-09, ADR 0014 y 0015) | ✅ Hecho con el número de prueba de Meta (verificado el 2026-10-18). Antes de personas reales: consentimiento (HU-01), política de privacidad y token permanente |

**Pendientes de aprobación del equipo** (contenido clínico PROVISIONAL implementado para la demostración, ADR propuestos y elección del modelo): [docs/00-gestion/pendientes-aprobacion.md](docs/00-gestion/pendientes-aprobacion.md).

## Arquitectura en una línea
Monolito modular en **Python + FastAPI** con **arquitectura hexagonal (puertos y adaptadores)**. Los canales (consola, Telegram, WhatsApp) son adaptadores de entrada intercambiables. Las reglas clínicas de alarma son deterministas y el LLM solo interpreta y redacta. Ver [docs/02-arquitectura/arquitectura.md](docs/02-arquitectura/arquitectura.md).

## Mapa del repositorio
```
AGENTS.md / CLAUDE.md   Reglas obligatorias para agentes de IA y personas
docs/                   Documentación viva (ver docs/README.md y su matriz de impacto)
src/cardio_materno/     Código fuente (domain, application, adapters, bootstrap)
knowledge/              Base de conocimiento clínica curada para RAG
tests/                  unit / integration / conversational
scripts/                Utilidades de desarrollo
.claude/                Hooks y comandos de Claude Code que hacen cumplir las reglas
```

## Instalación y ejecución
PC de pruebas (Ubuntu + Ollama con `mistral-small3.1:24b` y `qwen3-embedding:8b`):
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python run_build_kb_index.py   # índice de la base de conocimiento (una vez)
.venv/bin/python run_console.py
# Interfaz web local de demostración: http://127.0.0.1:8000
.venv/bin/python run_web.py
# Canal WhatsApp (requiere la app de Meta, la sección 9 de .env y ngrok)
.venv/bin/python run_whatsapp.py
ngrok http --url=<tu-dominio>.ngrok-free.app 8001
```
⚠️ Prototipo técnico: las reglas de alarma son PROVISIONALES (R-09) y la base de conocimiento está validada solo para el prototipo (R-10). Solo para pruebas del equipo.

Guía completa, variables, guiones de prueba y solución de problemas: [docs/08-despliegue/instalacion.md](docs/08-despliegue/instalacion.md).

## Cómo contribuir
1. Leer [AGENTS.md](AGENTS.md). Aplica a personas y a agentes de IA.
2. Trabajar en ramas `feat/…`, `fix/…`, `docs/…` y usar [Conventional Commits](https://www.conventionalcommits.org/es/).
3. Antes de cerrar una tarea: cumplir la [Definition of Done](docs/00-gestion/definition-of-done.md) y la matriz de impacto de [docs/README.md](docs/README.md).

## Equipo
Investigación: Dolly Magnolia González Hoyos, PhD; Andrés Paolo Castaño, PhD; Carlos Alberto Ruiz, PhD. Desarrollo: equipo de Proyecto Integrador II: Nicolas Castillo Galeano, Juan Felipe Montanchez Botina, Santiago Silva Guarnizo.
