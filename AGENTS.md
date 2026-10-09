# AGENTS.md: reglas obligatorias del proyecto

Este archivo es la **fuente única de reglas** para cualquier agente de IA (Claude Code, Copilot, Cursor, etc.) y para las personas del equipo. Si una instrucción puntual contradice este archivo, **hay que preguntar antes de actuar**.

---

## 1. Contexto
- **Qué es:** un asistente de **teleorientación** (Res. 2654/2019) con IA en **salud cardiovascular (CV) y materno‑infantil (MI)** para comunidades de Caldas. Es el Objetivo Específico 2 del proyecto Minciencias 2025 y se desarrolla en Proyecto Integrador II (U. de Caldas).
- **Qué NO es:** no es un sistema de diagnóstico ni de prescripción, y no reemplaza al personal de salud.
- **Enfoque:** *spec‑driven*. La especificación en `docs/01-especificacion/` es la **fuente de verdad**. El código se deriva de ella y se verifica contra ella.
- **Canales, en orden:** 1) Consola → 2) Telegram (multiusuario) → 3) WhatsApp (prototipo final). Ver ADR 0003.
- **Stack:** Python 3.12+, FastAPI, pytest, ruff y mypy. Ver ADR 0002.

## 2. Arquitectura: hexagonal (puertos y adaptadores)
```
src/cardio_materno/
  domain/        Entidades, value objects, reglas clínicas DETERMINISTAS (signos de alarma, rutas)
  application/   Casos de uso, máquina de estados conversacional, PUERTOS (interfaces Protocol/ABC)
  adapters/
    inbound/     console, telegram, whatsapp, api (FastAPI): traducen el mensaje del canal → caso de uso
    outbound/    llm, rag, persistence, notifications: implementan los puertos
  bootstrap/     Composition root: arma las dependencias según la configuración
```
**Regla de dependencias (inviolable):** las dependencias van solo hacia adentro.
- `domain` no importa nada del proyecto ni librerías de infraestructura (FastAPI, SDKs, ORM, HTTP).
- `application` importa solo `domain`.
- `adapters` importa `application` y `domain`, nunca otro adaptador.
- Solo `bootstrap` conoce todo.

**Regla de seguridad clínica (ADR 0004):** la detección de **signos de alarma**, la **clasificación de riesgo** y la **ruta de atención** son reglas deterministas y probadas en `domain/`. El LLM **solo** interpreta el lenguaje natural y redacta las respuestas; **nunca decide** si hay alarma ni a dónde remitir.

## 3. Estándares de código (ver `docs/06-calidad/estandares-codigo.md`)
- **Funciones pequeñas con una sola responsabilidad**: idealmente ≤ 25 líneas, ≤ 5 parámetros y complejidad ≤ 7. Si una función "hace X **y** Y", hay que dividirla.
- **Type hints** en todo; `mypy --strict` debe pasar.
- **Docstrings estilo Google** en español para todo módulo, clase y función pública: qué hace, `Args`, `Returns` y `Raises`.
- **Identificadores en inglés**; documentación, docstrings y mensajes al usuario en **español**.
- Sin números ni textos mágicos: van como constantes con nombre o en configuración. Los textos al usuario van en plantillas.
- Errores explícitos con excepciones de dominio propias; nunca `except:` vacío.
- Logging estructurado sin datos personales.
- Inyección de dependencias por constructor, sin singletons globales.
- Toda lógica nueva lleva **pruebas** (unitarias en `tests/unit`; los flujos conversacionales, en `tests/conversational`).
- Hay que preferir cambios pequeños y revisables a cambios grandes.

## 4. Datos y privacidad (Ley 1581/2012)
- **Nunca** se envían al LLM datos personales identificables (nombre, documento, teléfono, dirección). Hay que anonimizar antes.
- **Nunca** se versionan secretos ni datos reales: los secretos van en `.env` y los datos de prueba deben ser sintéticos.
- La base de conocimiento (`knowledge/`) solo admite fuentes **citadas y validadas** por el equipo clínico.

## 5. Decisiones que NO se delegan a la IA
Arquitectura y stack, alcance y priorización del backlog, contenido clínico y umbrales de alarma, interpretación de la validación con usuarios, y riesgos éticos. La IA puede **proponer**; el equipo **decide** y lo registra en un ADR.

---

## 6. PROTOCOLO DE CIERRE DE TAREA (obligatorio en cada cambio)
Antes de dar por terminada **cualquier** tarea que modifique el repositorio:

1. **Código:** cumple la sección 3, las pruebas pasan y ruff/mypy no tienen errores (cuando ya exista tooling).
2. **Matriz de impacto:** revisar `docs/README.md` → *Matriz de impacto documental* y actualizar **cada** documento afectado (historias de usuario, flujos, BPMN, arquitectura, ADR, modelo de datos, trazabilidad, etc.).
3. **CHANGELOG.md:** agregar una entrada en `[Unreleased]` (Added / Changed / Fixed / Removed).
4. **Bitácora IA:** agregar una fila en `docs/05-ia/bitacora-verificacion-ia.md` con qué se generó con IA, la verificación pendiente o realizada y el riesgo.
5. **README:** actualizar la tabla de estado o las instrucciones si cambiaron.
6. **Resumen final al usuario:** listar los archivos de código y los **documentos actualizados**, y lo que quedó pendiente de verificación humana.

El hook `.claude/hooks/check_docs.py` **bloquea** el cierre si hay cambios en `src/`, `tests/` o `knowledge/` sin actualizar el CHANGELOG y la bitácora. El comando `/cerrar-tarea` guía este protocolo paso a paso.

## 7. Git
- Ramas: `feat/…`, `fix/…`, `docs/…`, `chore/…`. `main` siempre debe estar estable.
- Commits en formato [Conventional Commits](https://www.conventionalcommits.org/es/), en español (`feat(domain): agrega regla de alarma de preeclampsia`).
- No se hace commit ni push sin que el usuario lo pida.

## 8. Mantenimiento de este archivo
Si una tarea introduce una convención nueva (carpeta, patrón o herramienta), hay que **actualizar este AGENTS.md** en la misma tarea.
