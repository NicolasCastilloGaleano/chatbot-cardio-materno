# Guion de verificación: orientación después del aviso de urgencia (B-034, paso 1)

*Última actualización: 2026-11-02*

Rama `feat/b-034-orientacion-urgencia`. Con `URGENT_GUIDANCE_MODE=activo` y el selector activo, después del aviso de una urgencia inmediata llega sola una orientación. En este paso solo funciona en la **consola**. La web y WhatsApp siguen en el paso 2.

## 1. Preparación
- En `.env`: `URGENT_GUIDANCE_MODE=activo` y `SHOW_THREAD_DEBUG=true`.
- `git pull` y arrancar `python run_console.py`.

## 2. Casos
Se reinicia la consola entre un caso y otro.

| # | Mensaje | Qué debe pasar |
|---|---|---|
| 1 | `estoy embarazada y estoy sangrando` | El aviso sale al instante. Después llega "Mientras llegas: …" con acciones del sangrado, nada de otra emergencia |
| 2 | `siento el pecho pesado cuando subo escaleras` | El aviso sale después del análisis, y luego la orientación si la base tiene algo verificado |
| 3 | `tengo un dolor de pecho muy fuerte y me falta el aire` | Igual: aviso primero. Si no hay contenido útil, no llega un segundo mensaje |
| 4 | Repetir el mensaje 1 en el mismo chat | Sale el aviso, sin una segunda orientación |

## 3. Qué anotar
- Cuánto tarda el aviso y cuánto la orientación (`[tiempos …]`).
- Si la orientación sirve y si corresponde a la emergencia.
- Si no llega el segundo mensaje, qué dijo el selector.

## 4. Resultado
- Si aparece una instrucción de otra emergencia o el aviso se retrasa, `URGENT_GUIDANCE_MODE` vuelve a `apagado`.
- Si sale bien, se sigue con la web y WhatsApp.
