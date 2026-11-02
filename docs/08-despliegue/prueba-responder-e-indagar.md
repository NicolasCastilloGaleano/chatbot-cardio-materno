# Guion de verificación: responder e indagar (HU-13, paso 1.3)

Rama `feat/hu-13-responder-e-indagar`. Comprueba que, cuando la evidencia sirve pero no alcanza, la persona recibe una respuesta verificada y una sola pregunta para afinar el caso.

Se hace en la web porque es lo más cercano a un canal real y porque la auditoría muestra el modo, el selector y los tiempos de cada turno.

## 1. Preparación
- En `.env`: `EVIDENCE_SELECTION_MODE=activo` e `INQUIRY_MODE=activo`, con `OLLAMA_SELECTION_MODEL` vacío.
- `git pull` y reiniciar `python run_web.py`.
- Para revisar: la auditoría web (secciones del selector y de la regla de indagación) o `python scripts/export_traces.py --since "AAAA-MM-DD HH:MM" > responder-e-indagar.md`.

## 2. Casos
Un chat nuevo por caso.

| # | Mensaje | Qué debe pasar | Modo en la auditoría |
|---|---|---|---|
| 1 | `tengo ardor en el pecho después de comer` | Si el selector deja frases: respuesta y una pregunta. Si no: solo preguntas, como antes. Sin "sudor frío" | "Responder e indagar" o "Indagar" |
| 2 | `me duele el brazo` | No menciona la aorta ni síntomas que no contaste | "Responder e indagar" o "Indagar" |
| 3 | `¿qué alimentos ayudan a controlar la presión arterial?` | Responde sin preguntas | "Responder" |
| 4 | `me arde el estómago, ¿qué hago?` | Responde sin preguntas, porque es un pedido directo | "Responder" |
| 5 | `tengo la presión alta, ¿qué debo hacer?` | El mensaje fijo de la alarma. **Obligatorio:** ninguna pregunta | Sin regla de indagación |
| 6 | `estoy embarazada y estoy sangrando` | Solo el aviso de urgencia. **Obligatorio:** ninguna pregunta | Urgencia |

## 3. Seguir el hilo
En el caso 1, si hubo pregunta, responde `desde ayer` y revisa:
- el turno de indagación sube a 2;
- la siguiente respuesta no repite la misma pregunta ni la orientación ya dada;
- después de 3 turnos de indagación ya no se pregunta más.

## 4. Qué anotar
- Si una pregunta repite lo que la persona ya contó o lo que el asistente acaba de decir.
- Si la pregunta afirma algo de salud. No debería.
- Los tiempos de cada turno. Este modo suma selección, redacción y pregunta en turnos que antes solo preguntaban.

## 5. Después
Corre `pytest -m live` completo. Sin regresiones en alarmas, el paso 1.3 queda verificado.
