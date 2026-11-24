from pathlib import Path

import streamlit as st
from urllib.error import URLError
from sqlcipher3 import dbapi2 as sqlite3

from app.backend.agent import crear_agente_analista
from app.backend.history import HistoryStore
from app.backend.local_config import load_local_config, ollama_model
from app.backend.uploads import purge_expired_uploads


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHART_PATH = OUTPUT_DIR / "chart.png"

try:
    load_local_config(PROJECT_ROOT / ".env")
    history = HistoryStore()
    purge_expired_uploads(UPLOAD_DIR, history)
except (OSError, sqlite3.Error) as error:
    st.error(f"No se pudo mantener el historial/cargas locales: {error}")
    st.stop()

if not st.session_state.get("dataset_cargado", False):
    st.warning("No hay ningún archivo activo.")
    if st.button("Volver al inicio", use_container_width=True):
        st.switch_page("app/frontend/home.py")
    st.stop()

dataset_id = st.session_state.get("dataset_id")
if not dataset_id or st.session_state.get("active_dataset_id") != dataset_id:
    st.error("La conversación no tiene un CSV asociado válido. Vuelve a Inicio.")
    st.stop()

dataset_path = Path(st.session_state.get("ruta_archivo", "")).resolve()
try:
    dataset_path.relative_to(UPLOAD_DIR.resolve())
except ValueError:
    st.error("La ruta del CSV está fuera de la carpeta de cargas permitida.")
    st.stop()

if not dataset_path.is_file():
    st.error("El CSV asociado ya no está disponible. Retoma otra conversación o vuelve a subirlo.")
    st.stop()

conversation_id = st.session_state.get("conversation_id")
if not conversation_id:
    st.error("La conversación no está guardada correctamente. Retómala desde Inicio.")
    st.stop()

attachment = history.conversation_dataset(
    conversation_id,
    harness="streamlit",
)
if attachment is None or attachment.dataset_id != dataset_id:
    st.error("El historial no coincide con el CSV activo. Retoma la conversación desde Inicio.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

loaded_conversation_id = st.session_state.get("messages_loaded_conversation_id")
if loaded_conversation_id != conversation_id:
    st.session_state.messages = [
        {
            "role": "user" if event.event_type == "user_request" else "assistant",
            "content": event.content,
        }
        for event in history.conversation_events(
            conversation_id,
            harness="streamlit",
        )
        if event.event_type in {"user_request", "agent_response"}
    ]
    st.session_state.messages_loaded_conversation_id = conversation_id

if st.session_state.get("agent_executor") is None:
    try:
        st.session_state.agent_executor = crear_agente_analista(str(dataset_path))
    except (OSError, ValueError) as error:
        st.error(f"No se pudo preparar el analizador local: {error}")
        st.stop()

def enviar_sugerencia(texto: str) -> None:
    st.session_state.prompt_activo = texto


st.markdown(
    f"""
    <header class="ui-chat-header">
      <p class="ui-kicker">Conversación activa</p>
      <h1 class="ui-chat-title">{attachment.dataset_name}</h1>
      <p class="ui-status">Ollama local · {ollama_model()} · Retención 48 h</p>
    </header>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
col1.button(
    "Resumen",
    on_click=enviar_sugerencia,
    args=("Resume las estadísticas principales del CSV.",),
)
col2.button(
    "Valores nulos",
    on_click=enviar_sugerencia,
    args=("Indica cuántos valores nulos hay por columna.",),
)
col3.button(
    "Gráfico",
    on_click=enviar_sugerencia,
    args=("Genera un gráfico de barras con las variables principales.",),
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.form("chat-question", clear_on_submit=True, border=False):
    input_col, send_col = st.columns([12, 1], gap="small")
    input_usuario = input_col.text_input(
        "Escribe tu pregunta sobre el CSV...",
        placeholder="Escribe tu pregunta sobre el CSV...",
        label_visibility="collapsed",
    )
    enviar_pregunta = send_col.form_submit_button(
        "➤",
        type="primary",
        use_container_width=True,
        help="Enviar pregunta",
    )

if enviar_pregunta and input_usuario.strip():
    st.session_state.prompt_activo = input_usuario.strip()

if st.session_state.get("prompt_activo"):
    prompt_actual = st.session_state.prompt_activo
    st.session_state.prompt_activo = None

    try:
        purge_expired_uploads(UPLOAD_DIR, history)
        history.record_event(
            conversation_id=st.session_state.conversation_id,
            event_type="user_request",
            content=prompt_actual,
            harness="streamlit",
            model=ollama_model(),
            status="ok",
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        st.error(f"No se pudo guardar la petición localmente: {error}")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt_actual})
    with st.chat_message("user"):
        st.markdown(prompt_actual)

    with st.chat_message("assistant"):
        with st.spinner("Analizando en este equipo con Ollama..."):
            try:
                CHART_PATH.unlink(missing_ok=True)
                chat_history = [
                    (
                        "human" if message["role"] == "user" else "ai",
                        message["content"],
                    )
                    for message in st.session_state.messages[:-1][-20:]
                ]
                response = st.session_state.agent_executor.invoke(
                    {
                        "input": prompt_actual,
                        "chat_history": chat_history,
                    }
                )
                answer = response["output"]
            except (OSError, URLError, TimeoutError, ValueError) as error:
                try:
                    history.record_event(
                        conversation_id=st.session_state.conversation_id,
                        event_type="agent_response",
                        content=str(error),
                        harness="streamlit",
                        model=ollama_model(),
                        status="error",
                    )
                except (OSError, sqlite3.Error) as history_error:
                    st.error(f"También falló el registro local del error: {history_error}")
                st.error(f"Falló el análisis local: {error}")
            else:
                try:
                    history.record_event(
                        conversation_id=st.session_state.conversation_id,
                        event_type="agent_response",
                        content=answer,
                        harness="streamlit",
                        model=ollama_model(),
                        status="ok",
                    )
                except (OSError, sqlite3.Error) as error:
                    st.error(f"No se pudo guardar la respuesta en el historial: {error}")
                else:
                    st.markdown(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )
                    if CHART_PATH.is_file():
                        try:
                            history.record_event(
                                conversation_id=st.session_state.conversation_id,
                                event_type="agent_action",
                                content="Gráfico local generado",
                                harness="streamlit",
                                model=ollama_model(),
                                status="ok",
                            )
                        except (OSError, sqlite3.Error) as error:
                            st.error(f"El gráfico se generó, pero no se pudo auditar: {error}")
                        else:
                            st.image(CHART_PATH)
