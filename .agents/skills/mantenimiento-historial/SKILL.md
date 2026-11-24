---
name: mantenimiento-historial
description: "Use when reviewing, querying, auditing, or cleaning agent conversation history and runtime status; enforce the 48-hour maximum retention."
---

# Skill de mantenimiento: historial, CSV y auditoría

1. El historial privado está en `output/agent_history.sqlite3`; no lo publiques ni compartas.
2. Las peticiones y respuestas, asociaciones de CSV y cargas relacionadas expiran tras 48 horas sin actividad.
3. El inicio, el chat y `python scripts/history.py purge` eliminan eventos caducados y cargas huérfanas de más de 48 horas.
4. Retomar una conversación actualiza su actividad; la carga asociada debe existir y coincidir con su hash.
5. Consulta solo lo necesario con `python scripts/history.py show --limit 50`. No copies contenido privado en informes.
6. Verifica timestamps, `harness`, `model` y `status`; una configuración local no prueba por sí sola que Ollama responda.
7. Ejecuta `python -m unittest discover -s tests -v` tras cambios de mantenimiento.

## Classification

Clasificación: skill de mantenimiento para la operación y auditoría posterior.
