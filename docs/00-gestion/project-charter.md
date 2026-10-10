# Project Charter

*Última actualización: 2026-10-09*

## Identificación
| Campo | Valor |
|---|---|
| Proyecto marco | Herramienta tecnológica para la apropiación social del conocimiento en salud cardiovascular y materno‑infantil para el fortalecimiento de la salud familiar en comunidades de Caldas (Convocatoria Minciencias 2025) |
| Alcance de este repositorio | **Objetivo Específico 2**: aplicativo de software funcional (TRL 5), culturalmente pertinente, para apoyar la toma de decisiones en salud familiar |
| Curso | Proyecto Integrador II, Universidad de Caldas (ago–dic 2026) |
| Entidades aliadas | Fundación Soy Mujer en la Ciencia; Dirección Territorial de Salud de Caldas; Thynk Unlimited |
| Investigadores | Dolly Magnolia González Hoyos, PhD (salud materno‑infantil); Andrés Paolo Castaño, PhD (investigador principal); Carlos Alberto Ruiz, PhD |
| Equipo de desarrollo | Nicolas Castillo Galeano, Juan Felipe Montanchez Botina, Santiago Silva Guarnizo |

## Problema
Caldas presenta brechas en salud cardiovascular (las enfermedades CV causaron el 16,8 % de las muertes en 2024) y en salud materno‑infantil (mortalidad infantil de 10,6 por 1.000 nacidos vivos en 2024, con picos en áreas rurales y pobres). Las comunidades tienen acceso limitado a información confiable, oportuna y culturalmente pertinente sobre signos de alarma y rutas de atención.

## Objetivo del MVP
Un asistente conversacional de **teleorientación** que:
1. Orienta en lenguaje comunitario sobre salud CV y MI (actividad 2.2: modelo de lenguaje).
2. Identifica **signos de alarma** y genera **alertas** (actividad 2.4).
3. Direcciona a **rutas de atención oportunas** (actividad 2.4).
4. Opera por **WhatsApp** como canal final (actividad 2.3), validado antes en consola y Telegram.

## Actividades del Objetivo 2 (propuesta)
| Actividad | Responsable (propuesta) |
|---|---|
| 2.1 Diseño y desarrollo del aplicativo | Estudiante de Maestría – Telemedicina |
| 2.2 Entrenamiento y configuración del modelo de lenguaje | Andrés Paolo Castaño |
| 2.3 Implementación del flujo de atención por WhatsApp | Telemedicina |
| 2.4 Desarrollo de alertas y rutas de atención oportunas | Dolly Magnolia González Hoyos |
| 2.5 Validación cultural y técnica de las herramientas digitales | Fundación Soy Mujer en la Ciencia |

## Alcance
- **In scope:** orientación, detección de signos de alarma por reglas, direccionamiento a rutas, canales consola/Telegram/WhatsApp y registro anonimizado de interacciones para métricas.
- **Out of scope:** diagnóstico, prescripción, historia clínica, agendamiento real con IPS (TODO: confirmar) y app móvil nativa (TODO: confirmar con aliados).

## Criterios de éxito (TODO: acordar métricas con los aliados)
- El 100 % de los signos de alarma definidos por el equipo clínico se detectan en las pruebas de referencia.
- La validación con usuarios de la comunidad y expertos (actividad 2.5) arroja satisfacción ≥ TODO.
- El MVP está desplegado en un ambiente de pruebas (Docker).

## Restricciones
- Normativa: Res. 2654/2019 (telesalud y teleorientación) y Ley 1581/2012 (datos personales).
- No se ingresan datos personales a servicios de IA externos sin autorización.
- Calendario de 16 semanas (ver los lineamientos, §7).

## Firmas
TODO: firma de la entidad aliada y del docente.
