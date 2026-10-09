# ADR 0003: Canales progresivos (consola → Telegram → WhatsApp)

- **Estado:** Aceptado
- **Fecha:** 2026-10-09
- **Decisores:** equipo de desarrollo

## Contexto
El canal final es WhatsApp (actividad 2.3), pero exige una cuenta Business, plantillas aprobadas, un webhook público y tiene costos. Iterar el flujo conversacional directamente allí sería lento.

## Decisión
Implementar los canales como **adaptadores de entrada** en tres fases:
1. **Consola:** validar el flujo, los estados y las reglas de alarma de forma rápida y local. Es la base de las pruebas conversacionales.
2. **Telegram:** pruebas multiusuario reales con el equipo y los aliados (bot gratuito y fácil de configurar).
3. **WhatsApp (Cloud API):** prototipo final.

Los tres adaptadores convierten sus mensajes a un `IncomingMessage` común y usan el mismo caso de uso.

## Consecuencias
- ✅ El núcleo se valida antes de asumir la complejidad de WhatsApp, y cada canal añade poco código.
- ⚠️ WhatsApp impone restricciones propias (ventana de 24 h, plantillas, formato) que pueden requerir ajustes en la presentación de los mensajes. Esto se resolverá en su adaptador.
