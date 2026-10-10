# Protección de datos personales

*Última actualización: 2026-10-10*

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

## Pendientes
- TODO: texto del aviso de privacidad validado por los aliados.
- TODO: política de retención y eliminación.
- TODO: autorización de los aliados si alguna vez se usan datos reales con servicios de IA.
