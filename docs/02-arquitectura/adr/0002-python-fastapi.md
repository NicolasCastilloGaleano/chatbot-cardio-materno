# ADR 0002: Python + FastAPI como stack backend

- **Estado:** Aceptado
- **Fecha:** 2026-10-09
- **Decisores:** equipo de desarrollo

## Contexto
Los lineamientos recomiendan .NET 10 por defecto, pero admiten alternativas justificadas según el reto. El núcleo de este reto es conversacional y de IA (LLM, RAG, procesamiento de lenguaje), y la propia guía muestra Python/FastAPI como microservicio de IA.

## Decisión
- Backend en **Python 3.12+** con **FastAPI** para la API y los webhooks (WhatsApp y Telegram).
- Calidad: **pytest**, **ruff** (lint y formato, con reglas de complejidad y docstrings) y **mypy --strict**.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| .NET 10 + microservicio Python de IA | Alineado al stack por defecto | Dos lenguajes y dos servicios para un MVP; duplica el esfuerzo |
| Node.js / NestJS | TypeScript de punta a punta | Ecosistema de IA/RAG menos maduro que Python |

## Consecuencias
- ✅ Acceso directo al ecosistema de IA (SDKs de LLM, embeddings, vector stores) y un solo lenguaje.
- ⚠️ El tipado es opcional en Python; se compensa con `mypy --strict` obligatorio.
- El equivalente a las piezas del stack por defecto (FluentValidation → Pydantic, Serilog → logging estructurado, Swagger → OpenAPI automático de FastAPI) se documentará al implementar.
