# Prueba: responder e indagar (HU-13, paso 1.3)

Comprueba que, cuando la evidencia sirve pero no alcanza, la persona recibe una respuesta verificada y una sola pregunta para afinar el caso.

## Preparación
En el PC de pruebas, con `INQUIRY_MODE=activo` y `EVIDENCE_SELECTION_MODE=activo` en `.env`:

```bash
.venv/bin/python run_console.py
```

Antes de cada caso, cierra con `salir` y vuelve a abrir la consola, para empezar en un hilo nuevo.

## Casos
| Mensaje | Qué se espera | Línea de la consola |
|---|---|---|
| `tengo ardor en el pecho` | Si el selector deja frases: respuesta y una pregunta. Si no: solo preguntas, como antes | Modo `responder_e_indagar` o `indagar` |
| `me duele el brazo` | No menciona la aorta ni síntomas que no contaste. Respuesta y pregunta, o solo preguntas | Modo `responder_e_indagar` o `indagar` |
| `tengo la presión alta` | Sin cifras en la respuesta. Si hay pregunta, es una sola | Selector `parcial` si hay pregunta |
| `¿qué alimentos ayudan a controlar la presión arterial?` | Responde sin preguntas | Modo `responder` |
| `me arde el estómago, ¿qué hago?` | Responde sin preguntas, porque es un pedido directo | Modo `responder` |
| `estoy embarazada y estoy sangrando` | Solo el aviso de urgencia. Nunca una pregunta | Urgencia |

## Seguir el hilo
En `tengo ardor en el pecho`, si hubo pregunta, responde `desde ayer` y mira:
- el turno de indagación sube a 2;
- la siguiente respuesta no repite la misma pregunta ni la orientación ya dada;
- después de 3 turnos de indagación ya no se pregunta más.

## Qué anotar
- Si una pregunta repite lo que la persona ya contó o lo que el asistente acaba de decir.
- Si la pregunta afirma algo de salud. No debería.
- Los tiempos de cada turno. Este modo suma selección, redacción y pregunta en turnos que antes solo preguntaban.

## Después
Corre `pytest -m live` completo. Sin regresiones en alarmas, el paso 1.3 queda verificado.
