# AGENTS.md: reglas obligatorias del proyecto

Este archivo es la **fuente única de reglas** para cualquier agente de IA (Claude Code, Copilot, Cursor, etc.) y para las personas del equipo. Si una instrucción puntual contradice este archivo, **hay que preguntar antes de actuar**.

---

## 1. Contexto
- **Qué es:** un asistente de **teleorientación** (Res. 2654/2019) con IA en **salud cardiovascular (CV) y materno‑infantil (MI)** para comunidades de Caldas. Es el Objetivo Específico 2 del proyecto Minciencias 2025 y se desarrolla en Proyecto Integrador II (U. de Caldas).
- **Qué NO es:** no es un sistema de diagnóstico ni de prescripción, y no reemplaza al personal de salud.
- **Enfoque:** *spec‑driven*. La especificación en `docs/01-especificacion/` es la **fuente de verdad**. El código se deriva de ella y se verifica contra ella.
- **Canales, en orden:** 1) Consola → 2) Telegram (multiusuario) → 3) WhatsApp (prototipo final). Ver ADR 0003.
- **Stack:** Python 3.12+, FastAPI, pytest, ruff y mypy. Ver ADR 0002. LLM: Ollama local (ADR 0005). RAG con índice propio y numpy (ADR 0008). Persistencia: JSON para consola y web (ADR 0006); SQLite de la biblioteca estándar con usuarios e hilos acotados por usuario para los canales de chat (ADR 0015).
- **Ejecución:** `python run_console.py` (en el PC de pruebas, dentro de `.venv`); interfaz temporal local: `python run_web.py` (ADR 0013); canal WhatsApp: `python run_whatsapp.py` + ngrok (ADR 0014). Dependencias de ejecución mínimas en `requirements.txt` (`numpy`, ADR 0008; `fastapi` y `uvicorn`, ADR 0013); **agregar una nueva requiere un ADR**. Las herramientas de desarrollo van en `requirements-dev.txt`.
- **Dos llamadas al agente (ADR 0008):** análisis (sin evidencia) y respuesta (con evidencia). **La evidencia del RAG nunca debe llegar a la llamada de análisis**, porque alimenta el filtro de alarmas.
- **Filtro 2 con códigos cerrados (ADR 0012, provisional):** además de los síntomas en texto, el análisis marca en `reported_signs` códigos del catálogo (lista cerrada por `enum`) y el filtro 2 los cruza de forma exacta con las reglas. El modelo solo traduce el lenguaje; la regla decide. Todo código nuevo va en `knowledge/alarm_rules.json` con `code` y `examples`.
- **Base de conocimiento v2 (ADR 0016, propuesto):** cada registro pertenece a un cuadro (`motive`) y a una etapa con enfoque y ruta fijos (`STAGE_FOCUS`, `STAGE_ROUTE`); los datos del cuadro van en `knowledge/kb/cuadros.jsonl` y su lectura clínica **nunca** llega al agente ni a la persona. La hoja maestra (Excel) no se versiona: se convierte con `scripts/convert_rag_xlsx.py` y después se reconstruye el índice.
- **Evidencia por etapas (ADR 0017, propuesto):** con la base v2, la evidencia de un turno es un registro del cuadro identificado en una etapa que permiten las reglas deterministas de `domain/case_state.py` (indagar T1 → T2 → T3 → verificar → ruta base). El estado del caso viaja en la traza de las respuestas; **no** se guarda aparte. El LLM no elige la etapa.
- **Respuesta verificada (ADR 0010):** sin evidencia suficiente **no se llama al LLM** (abstención fija). Con evidencia, cada frase de salud cita su registro y `domain/grounding.py` la verifica; si una falla, se muestra el texto literal del registro. **Nunca** se muestra una afirmación de salud sin respaldo verificable.
- **Usuarios (ADR 0015):** en los canales de chat continuo, el agente solo accede a los hilos mediante un `ThreadRepository` acotado al usuario (`UserThreadStore.scoped`) y se crea un `ConversationService` por mensaje con el hilo abierto del usuario. **Nunca** se guarda el teléfono ni el nombre: solo el HMAC de la identidad del canal. Todo adaptador de `ThreadRepository` debe pasar `tests/unit/test_thread_repository_contract.py`.
- **Alcance (ADR 0009):** se decide por la intención del mensaje completo, nunca por palabras clave. El alcance **nunca** suprime una alarma, y un mensaje que reporta un síntoma **nunca se descarta**, aunque su dominio sea incierto (prompt de análisis v6).
- **Pruebas en otro equipo:** Ollama corre en un PC de pruebas, no en el de desarrollo. Las pruebas automáticas **nunca** deben requerir Ollama (se usan dobles). Las que sí lo requieren van en `tests/live/` con el marcador `live` (se ejecutan con `pytest -m live`).

## 2. Arquitectura: hexagonal (puertos y adaptadores)
```
src/cardio_materno/
  domain/        Entidades, value objects, reglas clínicas DETERMINISTAS (signos de alarma, rutas)
  application/   Casos de uso, máquina de estados conversacional, PUERTOS (interfaces Protocol/ABC)
  adapters/
    inbound/     console, telegram, whatsapp, api (FastAPI): traducen el mensaje del canal → caso de uso
    outbound/    llm, rag, persistence, notifications: implementan los puertos
  bootstrap/     Composition root: arma las dependencias según la configuración
  prompts/       Prompts del LLM versionados (nombre_vN.md), registrados en docs/05-ia/prompts/README.md
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
- **Lo que se ajusta al operar** (modelos, temperaturas, contextos, tiempos de espera, umbrales del RAG y de la verificación) va en `.env`, leído en `bootstrap/settings.py` y documentado en `.env.example` (por secciones) y en `docs/08-despliegue/instalacion.md`. Los valores calibrados por defecto pueden vivir en un archivo versionado (p. ej., `knowledge/evidence_policy.json`), pero `.env` tiene prioridad.
- Errores explícitos con excepciones de dominio propias; nunca `except:` vacío.
- Logging estructurado sin datos personales.
- Inyección de dependencias por constructor, sin singletons globales.
- Toda lógica nueva lleva **pruebas** (unitarias en `tests/unit`; los flujos conversacionales, en `tests/conversational`). Los dobles compartidos de los puertos (LLM falso, repositorio en memoria, reloj, ids) viven en `tests/unit/fakes.py`; hay que reutilizarlos antes de crear otros.
- Hay que preferir cambios pequeños y revisables a cambios grandes.

## 4. Datos y privacidad (Ley 1581/2012)
- **Nunca** se envían al LLM datos personales identificables (nombre, documento, teléfono, dirección). Hay que anonimizar antes.
- **Nunca** se versionan secretos ni datos reales: los secretos van en `.env` y los datos de prueba deben ser sintéticos.
- La base de conocimiento (`knowledge/`) solo admite fuentes **citadas y validadas** por el equipo clínico. Excepción documentada: `knowledge/alarm_rules.json` es un borrador **PROVISIONAL** (ADR 0007) hasta su validación; no se usa con usuarios reales.
- El **catálogo de alarmas** vive en `knowledge/alarm_rules.json` (datos, no código). Toda regla nueva o modificada requiere ≥ 2 frases en `tests/conversational/alarm_phrases.json`.

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
- **Flujo actual (un solo desarrollador activo):** rama → verificación del usuario (en el PC de pruebas si aplica) → fusión directa a `main` cuando el usuario la apruebe. Cuando se unan más integrantes: PR revisado por alguien distinto a quien generó el cambio.
- La CI (`.github/workflows/ci.yml`: ruff, mypy sobre `src` y `tests`, pytest) debe pasar en la rama antes de fusionar.
- En cada Sprint Review se ejecuta `/auditar-lineamientos`.

## 8. Mantenimiento de este archivo
Si una tarea introduce una convención nueva (carpeta, patrón o herramienta), hay que **actualizar este AGENTS.md** en la misma tarea.
