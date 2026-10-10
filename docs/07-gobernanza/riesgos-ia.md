# Riesgos de los componentes de IA

*Última actualización: 2026-10-10*

Insumo para el Informe de gobernanza ética (Lineamientos §3.6).

| ID | Riesgo | Impacto | Mitigación | Estado |
|---|---|---|---|---|
| R-01 | El LLM no detecta un signo de alarma | Alto | Reglas deterministas + palabras clave como red de seguridad (ADR 0004) y pruebas golden | Diseñado |
| R-02 | El LLM inventa información clínica (alucinación) | Alto | RAG solo sobre contenido validado; guardrails; respuesta "no sé, consulte" | ⏳ |
| R-03 | El LLM emite un diagnóstico o una recomendación de medicamentos | Alto | Prompt con restricciones + filtro de salida + pruebas | ⏳ |
| R-04 | Sesgo lingüístico o cultural (no entiende expresiones locales) | Medio | Glosario comunitario y validación con la Fundación (actividad 2.5) | ⏳ |
| R-05 | Fuga de datos personales al proveedor del LLM | Alto | Anonimización previa; sin PII en los prompts ni en los logs. Con Ollama local los datos no salen del equipo (ADR 0005) | Mitigado en parte |
| R-06 | Dependencia del proveedor del LLM (costo o disponibilidad) | Medio | Puerto `LanguageModel` intercambiable; degradación a menús | Mitigado en parte: Ollama local (ADR 0005) |
| R-07 | El prototipo HU-00 conversa libremente con el LLM **sin reglas deterministas de alarma** (incumple temporalmente ADR 0004) | Alto | Solo para pruebas internas del equipo; el prompt de sistema remite a urgencias como mitigación parcial; no usar con usuarios reales hasta implementar HU-03/HU-04 | Aceptado temporalmente |
