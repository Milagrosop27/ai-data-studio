# Cómo se hacen las cosas

## Arquitectura local

| Componente | Ruta | Responsabilidad |
|---|---|---|
| Streamlit | `app.py`, `app/frontend/` | UI limitada a `127.0.0.1`; permite cargar y retomar conversaciones |
| Agente CSV | `app/backend/agent.py` | Envía preguntas y contexto estadístico limitado al Ollama local; no ejecuta código de modelo |
| Configuración | `app/backend/local_config.py` | Lee solo variables locales y rechaza endpoints/modelos remotos |
| Historial | `app/backend/history.py` | Guarda eventos y asocia cada conversación con el hash del CSV |
| Cargas | `app/backend/uploads.py` | Conserva los CSV ligados a conversaciones activas y purga huérfanos vencidos |
| Pi | `scripts/invoke_pi.py` | Invoca Ollama local, elimina claves/proxies del entorno hijo y limita herramientas a leer/editar/escribir |
| Mantenimiento | `scripts/history.py` | Consulta o purga historial y cargas vencidas |
| Configuración web | `.streamlit/config.toml` | Loopback, límite de 10 MB, protección XSRF y telemetría apagada |

El endpoint de Ollama se normaliza a `http://127.0.0.1:11434`; solo se aceptan nombres de modelos instalados localmente. El analizador usa pandas para calcular estadísticas y Matplotlib para gráficos. Ningún código generado por el modelo se ejecuta. El contexto enviado al modelo local contiene agregados estadísticos y hasta 10 filas de muestra.

## Carga y continuación

1. La carga CSV se guarda en `data/uploads/<sha256>.csv`; subir de nuevo los mismos bytes reutiliza el archivo.
2. SQLite asocia el hash y nombre del archivo a una conversación.
3. La actividad actualiza la expiración de la asociación y del historial. Las últimas 20 conversaciones aparecen debajo de Panel de Análisis y se pueden retomar desde ese menú lateral.
4. Después de 48 horas sin actividad se purgan eventos y asociaciones. Las cargas huérfanas de más de 48 horas se borran en el siguiente inicio, carga, consulta de chat o mantenimiento.
5. Las conversaciones antiguas que no tengan asociación a un CSV no son recuperables desde la UI.
6. El tachito lateral abre un diálogo modal. Solo Cancelar o confirmar Eliminar cambia el historial; si el CSV sigue usado por otra conversación, se conserva.

La base SQLite se guarda cifrada con SQLCipher y su clave aleatoria se protege con Windows DPAPI fuera del workspace. Los CSV se mantienen sin cifrado propio. Usa una cuenta Windows con contraseña, ACL restringidas y BitLocker. Perder la clave DPAPI impide leer el historial; conservarla en una copia requiere aplicar el mismo nivel de protección.

## Configuración y operación

- `.env.example` contiene únicamente `OLLAMA_ENDPOINT` y `OLLAMA_MODEL`; `.env` puede contener solo esas variables para la aplicación.
- No uses endpoints de nube ni claves API. El cargador de `.env` ignora cualquier otra variable y el proceso de Pi no hereda claves API ni proxies.
- Ollama debe escuchar en loopback. Verifica con `Get-NetTCPConnection -LocalPort 11434 -State Listen`.
- Streamlit se inicia localmente con `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1`.
- Ejecuta Pi con `.\.venv\Scripts\python.exe scripts\invoke_pi.py "petición"`; `--continue` incluye hasta 12 eventos recientes de Pi.

## Validación

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\history.py show --limit 50
.\.venv\Scripts\python.exe scripts\history.py purge
```

El historial puede contener texto privado; no lo copies en informes ni lo compartas.
