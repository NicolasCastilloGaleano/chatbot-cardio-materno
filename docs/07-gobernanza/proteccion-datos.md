# Protección de datos personales

*Última actualización: 2026-10-17*

Marco: **Ley 1581 de 2012** (Habeas Data), Decreto 1377 de 2013 y **Res. 2654 de 2019** (telesalud). Los datos de salud son **datos sensibles**.

## Principios aplicados
- **Consentimiento** explícito al inicio de la conversación (RN-01), registrado con fecha.
- **Minimización:** solo se guarda lo necesario. El identificador del canal se guarda como hash.
- **Anonimización** del texto antes de enviarlo al LLM y antes de guardarlo para métricas.
- **Seguridad:** cifrado en reposo de los campos sensibles, secretos en `.env` y HTTPS.
- **Sin datos reales** en el repositorio ni en las pruebas (solo datos sintéticos).

## Almacenamiento actual (HU-06)
- Los hilos se guardan en `data/threads/*.json` con el **texto completo** de los mensajes, que puede contener datos de salud. La carpeta está en `.gitignore` y **no se versiona**.
- Solo se usan **datos ficticios** en las pruebas; no se ingresan datos reales de personas.
- El prompt v2 pide que el resumen no incluya datos personales (nombre, documento, dirección, teléfono). Esto no es una garantía: falta la anonimización automática.

## RAG (HU-02)
- La consulta de búsqueda (mensaje + resumen + síntomas) se envía al modelo de embeddings de **Ollama local**; no sale del equipo.
- La base de conocimiento no contiene datos personales.
- La `trace` de cada respuesta incluye los síntomas reportados (datos de salud) y se guarda con el hilo, en `data/threads/`, que no se versiona.

## Interfaz web local (HU-08, ADR 0013)
- La interfaz muestra **todas** las conversaciones guardadas en `data/threads/`, con su texto completo y sus trazas, que son datos de salud. **No tiene autenticación.**
- Por eso solo puede escuchar en la propia máquina: `WEB_HOST` admite únicamente `127.0.0.1`, `localhost` o `::1`, y cualquier otra dirección impide arrancar (`bootstrap/settings.py::load_web_settings`).
- Es para demostración y depuración con datos ficticios. **No se expone en una red ni se usa con usuarios reales.** Antes de un piloto harían falta autenticación, cifrado y control de acceso por persona.

## Pendientes
- TODO: texto del aviso de privacidad validado por los aliados.
- TODO: política de retención y eliminación.
- TODO: autorización de los aliados si alguna vez se usan datos reales con servicios de IA.
