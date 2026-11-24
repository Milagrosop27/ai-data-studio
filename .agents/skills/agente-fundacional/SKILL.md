---
name: agente-fundacional
description: "Use when initializing this workspace, preparing its Python .venv, configuring Pi, or connecting Gemma through a verified API endpoint."
---

# Skill fundacional: entorno y agente local

1. Mantén dependencias en `.venv`; en Windows usa `.\scripts\setup_venv.ps1`. No recrees el entorno existente sin autorización.
2. Usa exclusivamente Ollama local en `127.0.0.1:11434` y un modelo que aparezca en `ollama list`.
3. El `.env` solo carga `OLLAMA_MODEL` y `OLLAMA_ENDPOINT`; el cargador rechaza endpoints no locales e ignora claves de proveedores externos.
4. Streamlit no usa proveedores remotos ni ejecuta código generado. No vuelvas a añadir `PythonREPLTool` ni llamadas de red a modelos externos.
5. Cada CSV se vincula a una conversación por hash y permanece disponible mientras la conversación tenga actividad en las últimas 48 horas.
6. Ejecuta `python -m unittest discover -s tests -v` después de cambios al historial, cargas o arranque.

## Classification

Clasificación: skill fundacional para inicializar Python, Pi, Ollama y el flujo local.
