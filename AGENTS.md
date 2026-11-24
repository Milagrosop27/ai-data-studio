---
name: mi-primer-agente
description: Reglas para el agente local, el historial privado y los cambios seguros del workspace.
---

# Reglas del agente

- Responde en español, salvo que el usuario solicite otro idioma.
- Antes de cambiar archivos, inspecciona el estado actual y conserva los datos del usuario.
- Usa exclusivamente Ollama local en `127.0.0.1:11434`; no configures proveedores de nube ni endpoints remotos.
- Carga del `.env` solo `OLLAMA_MODEL` y `OLLAMA_ENDPOINT`. Nunca imprimas ni registres secretos.
- No ejecutes código generado por un modelo. El análisis CSV usa funciones locales explícitas.
- Conserva el historial y el CSV asociado por un máximo de 48 horas desde la última actividad.
- Trata `output/agent_history.sqlite3` como privado y cifrado con SQLCipher; protege `data/uploads/` con BitLocker y ACL de Windows porque los CSV no tienen cifrado propio.
- Mantén Streamlit y Ollama enlazados a loopback. No expongas sus servicios a la red.
- Marca `OK` solo los componentes realmente probados. No afirmes que los datos están cifrados si solo están en el disco local.
- Usa `.venv` y las skills versionadas en `.agents/skills/`.
