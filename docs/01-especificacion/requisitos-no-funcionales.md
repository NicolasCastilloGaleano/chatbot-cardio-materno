# Requisitos no funcionales

*Última actualización: 2026-10-09*

| ID | Categoría | Requisito | Verificación |
|---|---|---|---|
| RNF-01 | Seguridad clínica | La detección de alarmas no depende del LLM (reglas deterministas) | Pruebas unitarias del dominio |
| RNF-02 | Privacidad | No se envía PII al LLM; los datos personales se cifran en reposo | Pruebas + revisión de código |
| RNF-03 | Disponibilidad | Healthcheck `/health` en la API | Prueba de integración |
| RNF-04 | Rendimiento | Respuesta del bot en menos de TODO s (p95) | Medición en Telegram/WhatsApp |
| RNF-05 | Usabilidad / pertinencia cultural | Lenguaje sencillo y comunitario, validado con la Fundación (actividad 2.5) | Pruebas con usuarios |
| RNF-06 | Mantenibilidad | Arquitectura hexagonal; funciones ≤ 25 líneas; ruff/mypy sin errores | CI |
| RNF-07 | Portabilidad | Ejecutable en Docker | `docker compose up` |
| RNF-08 | Trazabilidad | Interacciones registradas de forma anonimizada para métricas | Revisión del modelo de datos |
| RNF-09 | Seguridad | Secretos en variables de entorno, HTTPS en el despliegue, validación de entradas | Revisión + CI |
