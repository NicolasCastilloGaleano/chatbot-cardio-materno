# Guía de prueba: fases 1 a 3 del plan de migración (PC de pruebas)

Prueba de la rama `feat/fase2-3-base-v2-y-etapas`, que incluye la fase 1 (MIG-01 a MIG-04), el modelo y el conversor de la base v2 (MIG-05 y MIG-06), su activación por `.env` (MIG-07), la evaluación (MIG-08) y la evidencia por etapas (MIG-09 a MIG-13, [ADR 0017](../02-arquitectura/adr/0017-estado-del-caso-y-evidencia-por-etapas.md)).

La base v2 **no reemplaza** la v1 en el repositorio (puertas P1 y P7 del [plan](../00-gestion/plan-migracion-rag2.md)): se convierte en `data/kb_v2/` (no versionado) y se activa con `.env`. Para volver a la v1 basta con comentar esas variables.

## 1. Preparar
```bash
git fetch origin
git checkout feat/fase2-3-base-v2-y-etapas
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # debe pasar todo (sin Ollama)
```

## 2. Comprobar primero la fase 1 con la base v1 (sin tocar `.env`)
```bash
.venv/bin/python -m pytest -m live     # sondas en vivo con la base actual
.venv/bin/python run_web.py            # guion de la fase 1 (ver la respuesta del chat del 2026-10-22)
```
Al arrancar, el RAG debe decir "Base de conocimiento: 1600 registros…". Si dice que **el archivo de la base cambió desde que se construyó el índice**, reconstruye el índice v1 con `.venv/bin/python run_build_kb_index.py` (es la verificación nueva por hash).

## 3. Convertir la base v2 y construir su índice
Copia `RAG_2.xlsx` al PC de pruebas (por ejemplo, a la carpeta del proyecto; no se versiona) y ejecuta:
```bash
.venv/bin/python scripts/convert_rag_xlsx.py RAG_2.xlsx data/kb_v2
```
Debe decir "Registros: 2304 · cuadros: 192", sin errores, con una advertencia de validación (B-019). Luego agrega al `.env`:
```bash
KB_ENTRIES_FILE=data/kb_v2/entries.jsonl
KB_CASES_FILE=data/kb_v2/cuadros.jsonl
KB_INDEX_DIR=data/kb_index_v2
SHOW_THREAD_DEBUG=true
```
y construye el índice v2 (unos minutos más que el de la v1):
```bash
.venv/bin/python run_build_kb_index.py
```

## 4. Medir antes de conversar (MIG-08)
```bash
.venv/bin/python scripts/evaluate_kb_v2.py alarmas
.venv/bin/python scripts/evaluate_kb_v2.py recuperacion
```
- `alarmas` no usa Ollama. En el PC de desarrollo ya mostró que frases **negadas** disparan urgencia ("no me he desmayado nunca…" → RN-CV-04, "no me ahogo ni nada" → RN-CV-02): es la evidencia para la puerta P2.
- `recuperacion` busca las preguntas de T1 y de verificación (384) sin su propio registro. Anota el **% de cuadro correcto primero** y los percentiles de similitud: con eso se recalibra `min_similarity` (hoy 0,50, calibrado con la base v1). Si muchos aciertos quedan por debajo del umbral, prueba con `RAG_MIN_SIMILARITY` en `.env`.

## 5. Guion con la base v2
`.venv/bin/python run_web.py` (o la consola). Al arrancar debe decir "… · 192 cuadros: evidencia por etapas". En cada respuesta revisa la línea `[cuadro: … · etapa … · vistas: …]` (consola) o la sección "Cuadro y etapa" (web).

| # | Mensaje | Qué se espera |
|---|---|---|
| 1 | "buenas, mi bebé de 2 meses llora todas las tardes y se pone durito del estómago" | Cuadro de llanto o cólico del lactante, **etapa T1**: preguntas que separan lo grave de lo leve + algo que hacer mientras responde. Termina en pregunta. **No** remite a urgencias |
| 2 | "ahorita está dormidito y lleva como dos semanas igual todas las tardes" | Mismo cuadro, **etapa T2** (aunque el mensaje sea corto, no hay abstención) |
| 3 | "tiene mes y medio y le doy solo teta, mi hermana dice que le dé aromática" | **Etapa T3** |
| 4 | "eso es todo" | **Verificación del cuadro**: le devuelve lo entendido y pregunta si está bien |
| 5 | "sí, así es" | Etapa de la **ruta base** del cuadro (autocuidado → `accion_inmediata`) |
| 6 | "¿y en qué me fijo para saber si ya es algo serio?" | Normalmente `vigilancia` |
| 7 | Sesión nueva: "son las siete y ya empezó otra vez, ¿qué hago ya?" | Salto por intención explícita: `accion_inmediata` (o T1 si la similitud no lo detecta; anótalo) |
| 8 | Sesión nueva: "me duele mucho el pecho y sudo frío" | **La alarma manda:** mensaje fijo 🚨 sin evidencia, igual que antes |
| 9 | Dentro de un caso: "¿quién ganó el partido?" | Mensaje fijo de alcance con pregunta de reenganche; el caso sigue en el siguiente mensaje |

Para cada turno anota: cuadro identificado (¿correcto?), etapa, si la respuesta terminó en pregunta, si usó texto literal (`[respaldo: … texto literal]`) y el tiempo.

## 6. Qué reportar
- Resultado de `pytest -m live` con la base v1 (paso 2).
- Salida de los dos modos de `evaluate_kb_v2.py`.
- La tabla del guion (paso 5), en especial cuadros equivocados, etapas saltadas y respuestas con texto literal.
- Con eso se decide: el umbral para la base v2 (MIG-07), y llevar al equipo las puertas P1, P2 y P7.

## Volver a la base v1
Comenta en `.env` las tres variables `KB_*` del paso 3. No hace falta reconstruir nada: el índice v1 sigue en `data/kb_index/`.
