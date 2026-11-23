# Guion de verificación: escalamiento al profesional de salud (HU-16)

*Última actualización: 2026-11-22*

Rama `feat/hu-16-fase1-casos` (fases 1 a 5). Se prueba todo junto en el PC de pruebas antes de fusionar a `main`. Solo con usuarios y números de prueba del equipo.

## 1. Preparación
1. **Respalda la base:** la interfaz migra `data/cardio_materno.db` a la versión 4 al arrancar (tablas `clinical_cases`, `case_addresses` y `clinician_outbox`). No hay vuelta atrás automática.
   ```bash
   cp data/cardio_materno.db data/cardio_materno.antes-hu16.db
   ```
2. En `.env`:
   ```
   ESCALATION_MODE=activo
   ESCALATION_WINDOW_HOURS=24
   CLINICIAN_ACCESS_KEY=<una clave larga solo para la prueba>
   OUTBOX_POLL_SECONDS=3
   ```
3. `git pull` y reinicia `python run_web.py` (y, para la sección 4, `python run_whatsapp.py` con ngrok).
4. Abre dos ventanas: el chat en `http://127.0.0.1:8000` (la persona) y `http://127.0.0.1:8000/medico` (el profesional), con la clave.

Para mirar la base sin mostrar el número:
```bash
.venv/bin/python -c "import sqlite3; c = sqlite3.connect('data/cardio_materno.db'); print(c.execute('SELECT status, gap_count, notified FROM clinical_cases ORDER BY created_at DESC LIMIT 5').fetchall()); print('direcciones:', c.execute('SELECT count(*) FROM case_addresses').fetchone()[0]); print(c.execute('SELECT status, error_code FROM clinician_outbox ORDER BY id DESC LIMIT 5').fetchall())"
```

## 2. Chat web: casos, aprobar y modificar
Un chat nuevo por caso. Si una consulta sí encuentra evidencia y recibe respuesta, no es un error: prueba otra que la base no cubra (el informe de vacíos, `scripts/report_gaps.py`, da ejemplos).

| # | Acción | Qué debe pasar |
|---|---|---|
| 1 | Persona: `tengo diabetes gestacional, ¿cuántas unidades de insulina me pongo?` | En lugar de la abstención, el aviso de que un profesional revisa su consulta (con 123 y urgencias). En `/medico` aparece el caso |
| 2 | Persona, en el mismo chat: otra consulta sin evidencia | El recordatorio de que ya hay un profesional revisando. Sigue habiendo **un** caso, con 2 turnos sin respuesta |
| 3 | Persona, chat nuevo: `estoy embarazada y tengo un sangrado` | Solo el aviso de urgencia. **No** se abre un caso |
| 4 | Profesional: abre el caso del paso 1 → **Generar borrador** | Aparece un borrador marcado "sin respaldo de la base", sin dosis ni diagnóstico |
| 5 | Profesional: **Aprobar borrador** | La persona ve el texto como "Profesional de salud" (en unos segundos o al recargar). El caso sale de la lista |
| 6 | Otro caso: edita el borrador o escribe desde cero → **Enviar mi versión** | La persona recibe tu texto. Aprobar queda desactivado al editar |
| 7 | Persona, en el chat del paso 5: una pregunta normal | Responde el asistente, que tiene en cuenta lo que dijo el profesional |

## 3. Contacto directo (web)
| # | Acción | Qué debe pasar |
|---|---|---|
| 1 | Abre un caso nuevo y pulsa **Contacto directo** | La lista dice "en contacto" y aparece el chat del profesional |
| 2 | Profesional: `Hola, ¿desde cuándo tienes la molestia?` | La persona lo ve como "Profesional de salud" |
| 3 | Persona: `desde ayer` | **El asistente no responde.** El mensaje aparece en `/medico` en ≤ 5 s. Lo que el profesional estaba escribiendo no se borra |
| 4 | Persona: `estoy embarazada y tengo un sangrado` | El aviso de urgencia sale de inmediato, igual que sin contacto, y la alerta queda en la conversación |
| 5 | Profesional: **Cerrar contacto** | El caso sale de la lista. El siguiente mensaje de la persona lo responde el asistente |

## 4. WhatsApp (número de prueba de Meta)
Con `run_whatsapp.py` y ngrok funcionando, desde un número de prueba:

| # | Acción | Qué debe pasar |
|---|---|---|
| 1 | Escribe la consulta de insulina del caso 2.1 | Llega el aviso de espera. `direcciones: 1` en la consulta a la base |
| 2 | En `/medico`, el caso dice WhatsApp y tiene los botones activos → **Enviar mi versión** | En ≤ 5 s llega al teléfono `*Profesional de salud:* …` desde el número del proyecto. En la bandeja: `('enviado', '')` |
| 3 | Unos segundos después | `direcciones: 0`: el número se borró al cerrar el caso sin nada pendiente |
| 4 | Otra consulta sin evidencia → **Contacto directo** → escribe dos mensajes | Llegan al teléfono. Lo que responde la persona aparece en `/medico` y el bot no contesta |
| 5 | Desde el teléfono: `estoy embarazada y tengo un sangrado` | Llega el aviso de urgencia de inmediato |
| 6 | **Cerrar contacto** | `direcciones: 0` en la siguiente vuelta |
| 7 | **Ventana cerrada:** abre un caso desde el teléfono, detén `run_whatsapp.py` y vence el caso con el comando de abajo | Al recargar `/medico`, el caso desaparece (vencido). Al encender de nuevo el canal, `direcciones: 0` |

Para el paso 7:
```bash
.venv/bin/python -c "import sqlite3; c = sqlite3.connect('data/cardio_materno.db'); c.execute(\"UPDATE clinical_cases SET expires_at = '2000-01-01T00:00:00+00:00' WHERE status = 'pendiente'\"); c.commit()"
```

En los registros de `run_whatsapp.py` **no** debe aparecer el número de nadie.

## 5. Regresión
```bash
.venv/bin/python -m pytest -m live
```
Debe pasar igual que antes: las alarmas y las respuestas con evidencia no cambian. Con `ESCALATION_MODE=apagado`, el comportamiento es el de `main`.

## 6. Resultado
- Anota en cada caso si pasó y cuánto tardó en llegar el mensaje del profesional.
- Si algo falla, copia el mensaje, lo que se vio y la consulta a la base (sin números).
- Con el resultado, el equipo decide si se fusiona a `main` y si el filtro 2 debe correr durante el contacto (ADR 0022).
