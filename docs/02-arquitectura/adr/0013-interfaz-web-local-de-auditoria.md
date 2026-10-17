# ADR 0013: Interfaz web local para demostración y auditoría

- **Estado:** Aceptado para el prototipo técnico
- **Fecha:** 2026-10-12
- **Decisores:** equipo de desarrollo

## Contexto
Telegram y WhatsApp aún no están disponibles para demostrar el flujo. La consola ya ofrece información técnica, pero no una vista de chat adecuada para la sustentación ni una forma visual de inspeccionar la traza asociada a cada respuesta.

## Decisión
- Agregar una interfaz web local servida por FastAPI y Uvicorn, enlazada exclusivamente a `127.0.0.1`.
- Mantener la interfaz como adaptador de entrada: reutiliza `ConversationService`, el repositorio JSON y la base de conocimiento sin duplicar reglas ni llamadas al agente.
- Mostrar los datos persistidos de la traza y resolver sus referencias de evidencia para presentar el registro completo.
- Permitir explorar hilos guardados en modo de solo lectura. Al iniciar una sesión nueva se cierra el hilo activo.
- Agregar FastAPI y Uvicorn como dependencias de ejecución fijadas en `requirements.txt`; usar HTTPX solo en desarrollo para pruebas HTTP.

## Alternativas consideradas
| Alternativa | Pros | Contras |
|---|---|---|
| Web local con FastAPI | Reutiliza el stack previsto y ofrece una vista de chat accesible desde el navegador | Incorpora dependencias de ejecución y un adaptador adicional |
| Aplicación de escritorio | Ventana independiente del navegador | Requiere otra tecnología y empaquetado |
| Consola enriquecida | Menor cambio de arquitectura | No satisface la presentación visual solicitada |

## Consecuencias
- ✅ La misma aplicación resulta útil para sustentar, depurar y auditar turnos guardados.
- ✅ El núcleo conversacional y las reglas clínicas permanecen independientes del canal.
- ⚠️ El prototipo es de una sesión activa por proceso y no debe exponerse en una red ni usarse con usuarios reales.
- ⚠️ El historial de archivos JSON no está diseñado para acceso concurrente multiusuario.

## Actualización 2026-10-17 (revisión de la rama)
- El host y el puerto se configuran en `.env` (`WEB_HOST`, `WEB_PORT`), según la convención de AGENTS.md §3, y la configuración **rechaza cualquier host que no sea local**. Así, "solo en loopback" se garantiza por código.
- Se corrigieron tildes dañadas por doble codificación en 5 archivos Python, incluidos textos visibles para el usuario. Se agregó `tests/unit/test_text_encoding.py` para detectarlo en adelante.
