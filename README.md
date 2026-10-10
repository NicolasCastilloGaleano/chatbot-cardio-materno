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
| Flujo conversacional clínico por **consola** | ⏳ Pendiente |
| Canal **Telegram** (pruebas multiusuario) | ⏳ Pendiente |
| Canal **WhatsApp** (prototipo final) | ⏳ Pendiente |

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
Chat por consola con Ollama (requiere Python 3.12+ y Ollama; **sin `pip install`**):
```powershell
ollama pull mistral-small3.1:24b
copy .env.example .env
python run_console.py
```
⚠️ Es un prototipo técnico **sin reglas de alarma** (riesgo R-07): solo para pruebas del equipo.

Guía completa, variables y solución de problemas: [docs/08-despliegue/instalacion.md](docs/08-despliegue/instalacion.md).

## Cómo contribuir
1. Leer [AGENTS.md](AGENTS.md). Aplica a personas y a agentes de IA.
2. Trabajar en ramas `feat/…`, `fix/…`, `docs/…` y usar [Conventional Commits](https://www.conventionalcommits.org/es/).
3. Antes de cerrar una tarea: cumplir la [Definition of Done](docs/00-gestion/definition-of-done.md) y la matriz de impacto de [docs/README.md](docs/README.md).

## Equipo
Investigación: Dolly Magnolia González Hoyos, PhD; Andrés Paolo Castaño, PhD; Carlos Alberto Ruiz, PhD. Desarrollo: equipo de Proyecto Integrador II: Nicolas Castillo Galeano, Juan Felipe Montanchez Botina, Santiago Silva Guarnizo.
