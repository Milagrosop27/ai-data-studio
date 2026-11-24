# Mi Primer Agente

*AI Data Studio* convierte un archivo CSV en una conversación privada para analizar datos con un modelo que se ejecuta localmente. Permite subir el archivo una sola vez, formular varias preguntas, continuar una conversación hasta 48 horas y borrar conversaciones desde el panel lateral.

El workspace ofrece dos flujos:

- **AI Data Studio:** carga CSV, estadística, chat local y gráficos.
- **Pi:** recibe instrucciones de mantenimiento sobre el workspace y usa Ollama.

## Estructura y responsabilidades

```text
mi_primer_agente/
├── app.py                       Entrypoint, navegación y conversaciones laterales
├── README.md                    Guía general y operación
├── AGENTS.md                    Reglas permanentes del agente
├── COMO_SE_HACEN_LAS_COSAS.md  Procedimientos internos
├── requirements.txt             Dependencias Python fijadas
├── .env.example                 Plantilla local sin secretos
├── .env                         Configuración local privada
├── app/
│   ├── backend/
│   │   ├── agent.py             Análisis CSV y llamada HTTP a Ollama
│   │   ├── history.py           Historial cifrado y retención
│   │   ├── history_key.py       Clave SQLCipher protegida por DPAPI
│   │   ├── local_config.py      Validación de Ollama local
│   │   └── uploads.py           Purga de archivos huérfanos
│   └── frontend/
│       ├── home.py              Validación y carga del CSV
│       ├── chat.py              Chat, gráficos y reanudación
│       ├── theme.py             Sistema visual compartido
│       └── assets/              Imagen local de presentación
├── data/uploads/                CSV asociados a conversaciones
├── output/
│   └── agent_history.sqlite3    Historial SQLCipher
├── scripts/
│   ├── history.py               Consulta y purga
│   ├── invoke_pi.py             Pi contra Ollama local
│   └── setup_venv.ps1           Entorno Python
├── tests/                       Seguridad, cifrado y retención
├── .agents/skills/              Skills fundacional y de mantenimiento
├── .streamlit/config.toml       Loopback y configuración web
├── .vscode/tasks.json           Tareas de VS Code
└── .venv/                       Entorno virtual local
```

`.env`, `.venv`, `.agent_runtime/`, `data/uploads/` y `output/` se mantienen locales y excluidos por Git.

## Requisitos

- Windows 10/11.
- Python 3.12 de 64 bits.
- Ollama para Windows.
- VS Code y PowerShell.
- Pi CLI y Node.js solo para el flujo Pi.
- BitLocker recomendado para datos sensibles.

## Instalación y arranque

```powershell
Copy-Item .env.example .env
.\scripts\setup_venv.ps1
ollama pull qwen3:1.7b
ollama list
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Sube el CSV desde Inicio. Las conversaciones válidas aparecen directamente debajo de **Panel de Análisis**. Al seleccionarlas se restauran el CSV, el chat y las respuestas anteriores. El icono de basura abre un modal con **Cancelar** y **Eliminar**.

Para Pi:

```powershell
.\.venv\Scripts\python.exe scripts\invoke_pi.py "Resume el workspace"
.\.venv\Scripts\python.exe scripts\invoke_pi.py --continue "Continúa la última conversación"
```

## Flujo interno

1. Inicio valida el CSV: máximo 10 MB y 100 000 filas.
2. Los bytes se identifican con SHA-256 y se guardan una sola vez en `data/uploads/`.
3. El backend crea una conversación y la vincula al hash y nombre del CSV.
4. pandas calcula columnas, nulos, totales, resumen numérico y una muestra de diez filas.
5. Streamlit envía esa información limitada y el historial reciente a Ollama por loopback.
6. Ollama genera texto. El modelo no tiene herramientas ni ejecuta código.
7. Las peticiones, respuestas y acciones se cifran en SQLite.
8. Cada actividad renueva la disponibilidad durante 48 horas.
9. El inicio, las cargas y el mantenimiento purgan registros y CSV huérfanos vencidos.

## Flujo externo

No hay proveedores externos en el flujo normal:

- Navegador → Streamlit en `127.0.0.1:8501`
- Streamlit/Pi → Ollama en `127.0.0.1:11434`
- Windows DPAPI → protección local de la clave SQLCipher

No se necesitan claves API para el funcionamiento local.

## Seguridad

- `.env` solo carga `OLLAMA_ENDPOINT` y `OLLAMA_MODEL`.
- No se necesitan API keys externas ni se heredan al proceso Pi.
- No publiques `.env`, `.venv`, CSV, historial ni `history-key.dpapi`.
- SQLCipher cifra el historial; DPAPI protege su clave.
- Los CSV no tienen cifrado propio y requieren BitLocker y ACL NTFS.
- El borrado lógico no garantiza borrado forense en SSD.
- Perder la clave DPAPI impide abrir el historial actual.

### Protección en Windows

1. Activa Cifrado de dispositivo/BitLocker y guarda la clave de recuperación fuera del proyecto.
2. Limita `output` y `data\uploads` a tu cuenta, Administradores y SYSTEM.
3. No desactives la herencia sin revisar las entradas necesarias.
4. No sincronices carpetas privadas con servicios de nube.

Comprobaciones sin mostrar datos:

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen
Get-NetTCPConnection -LocalPort 8501 -State Listen
Get-BitLockerVolume -MountPoint C:
icacls .\output
icacls .\data\uploads
```

## Beneficios

- **Inferencia local:** Ollama y Streamlit quedan limitados a `127.0.0.1`. Los CSV no se envían a proveedores remotos.
- **Sin ejecución de código generado:** el modelo recibe estadísticas y hasta diez filas de muestra; pandas y Matplotlib ejecutan operaciones locales predefinidas.
- **Continuidad real:** cada petición y respuesta se vincula al hash SHA-256 del CSV y a su conversación.
- **Retención estricta:** asociaciones y mensajes caducan después de 48 horas sin actividad.
- **Historial cifrado:** SQLite usa SQLCipher y la clave está protegida por Windows DPAPI.
- **Privacidad por capas:** loopback, ACL, BitLocker, cifrado del historial y claves fuera del workspace.
- **Control manual:** una conversación puede retomarse o eliminarse desde el menú lateral.

## Tecnologías

| Tecnología | Responsabilidad |
|---|---|
| Python 3.12 | Aplicación, análisis, pruebas y automatización |
| Ollama | Modelo local en `127.0.0.1:11434` |
| Qwen3 1.7B | Modelo local predeterminado |
| Gemma 3 1B | Modelo alternativo local compatible |
| Streamlit 1.42 | UI local, carga, chat y diálogo de confirmación |
| pandas | Lectura y validación CSV, estadísticas y valores nulos |
| Matplotlib | Generación local de gráficos |
| SQLCipher | Cifrado del historial SQLite |
| Windows DPAPI | Protección de la clave SQLCipher en la cuenta actual |
| Pi CLI | Operación asistida sobre el workspace |

Las versiones fijadas están en [requirements.txt](./requirements.txt).

## Documentación consultada

- [Ollama para Windows](https://ollama.com/download)
- [API de chat de Ollama](https://docs.ollama.com/api/chat)
- [Qwen3 1.7B](https://ollama.com/library/qwen3:1.7b)
- [Gemma 3](https://ollama.com/library/gemma3)
- [Streamlit](https://docs.streamlit.io/)
- [Diálogos de Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog)
- [SQLCipher para Python](https://pypi.org/project/sqlcipher3-binary/)
- [Pi CLI](https://github.com/earendil-works/pi)
- [Python venv](https://docs.python.org/3/library/venv.html)
- [BitLocker](https://learn.microsoft.com/windows/security/operating-system-security/data-protection/bitlocker/)

Para procedimientos internos consulta [COMO_SE_HACEN_LAS_COSAS.md](./COMO_SE_HACEN_LAS_COSAS.md), [AGENTS.md](./AGENTS.md) y [.agents/skills/](./.agents/skills/).
