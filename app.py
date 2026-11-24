from pathlib import Path

import streamlit as st
from sqlcipher3 import dbapi2 as sqlite3

st.set_page_config(
    page_title="AI Data Studio",
    page_icon="⚡",
    layout="wide",
)

from app.backend.history import HistoryStore
from app.backend.local_config import load_local_config, ollama_model
from app.backend.uploads import purge_expired_uploads
from app.frontend.theme import inject_theme

PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

inject_theme()

try:
    load_local_config(PROJECT_ROOT / ".env")
    history = HistoryStore()
    purge_expired_uploads(UPLOAD_DIR, history)
except (OSError, sqlite3.Error) as error:
    st.error(f"No se pudo iniciar el almacenamiento local: {error}")
    st.stop()

home_page = st.Page("app/frontend/home.py", title="Inicio", icon="⚡")
chat_page = st.Page("app/frontend/chat.py", title="Panel de Análisis", icon="💬")

pg = st.navigation([home_page, chat_page])


def retomar_conversacion(selected):
    dataset_path = UPLOAD_DIR / f"{selected.dataset_id}.csv"
    dataset = history.conversation_dataset(
        selected.conversation_id,
        harness="streamlit",
    )
    if dataset is None or not dataset_path.is_file():
        st.sidebar.error("El CSV ya no está disponible.")
        return

    try:
        history.record_event(
            conversation_id=selected.conversation_id,
            event_type="agent_action",
            content="Conversación retomada desde el menú lateral",
            harness="streamlit",
            model=ollama_model(),
            status="ok",
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        st.sidebar.error(f"No se pudo retomar la conversación: {error}")
        return

    st.session_state.conversation_id = selected.conversation_id
    st.session_state.dataset_id = selected.dataset_id
    st.session_state.active_dataset_id = selected.dataset_id
    st.session_state.ruta_archivo = str(dataset_path)
    st.session_state.dataset_cargado = True
    st.session_state.agent_executor = None
    st.session_state.prompt_activo = None
    st.session_state.messages_loaded_conversation_id = None
    st.session_state.messages = []
    st.switch_page("app/frontend/chat.py")


pg.run()

def solicitar_borrado(item):
    st.session_state.pending_delete = item


def cancelar_borrado():
    st.session_state.pending_delete = None


def confirmar_borrado():
    item = st.session_state.get("pending_delete")
    if item is None:
        return
    try:
        dataset_id = history.delete_conversation(
            item.conversation_id,
            harness="streamlit",
        )
        if dataset_id is not None:
            active_dataset_ids = history.active_dataset_ids()
            if dataset_id not in active_dataset_ids:
                (UPLOAD_DIR / f"{dataset_id}.csv").unlink(missing_ok=True)

        if st.session_state.get("conversation_id") == item.conversation_id:
            st.session_state.conversation_id = None
            st.session_state.dataset_id = None
            st.session_state.active_dataset_id = None
            st.session_state.ruta_archivo = None
            st.session_state.dataset_cargado = False
            st.session_state.agent_executor = None
            st.session_state.prompt_activo = None
            st.session_state.messages = []
            st.session_state.messages_loaded_conversation_id = None
        st.session_state.pending_delete = None
        if st.session_state.get("conversation_id") is None:
            st.switch_page("app/frontend/home.py")
        else:
            st.rerun()
    except (OSError, sqlite3.Error, ValueError) as error:
        st.sidebar.error(f"No se pudo borrar la conversación: {error}")


@st.dialog("Eliminar conversación")
def confirmar_eliminacion_dialog():
    item = st.session_state.get("pending_delete")
    if item is None:
        cancelar_borrado()
        st.rerun()
        return

    st.markdown(
        "Se eliminarán las peticiones y respuestas de esta conversación. "
        "El CSV asociado se conservará si todavía pertenece a otra conversación activa."
    )
    st.markdown(f"¿Seguro que deseas eliminar **{item.dataset_name}**?")

    dialog_columns = st.columns(2)
    dialog_columns[0].button(
        "Cancelar",
        key="cancel-delete-conversation",
        on_click=cancelar_borrado,
        use_container_width=True,
    )
    dialog_columns[1].button(
        "Eliminar",
        key="confirm-delete-conversation",
        on_click=confirmar_borrado,
        type="primary",
        use_container_width=True,
    )


pending_delete = st.session_state.get("pending_delete")
if pending_delete is not None:
    confirmar_eliminacion_dialog()

recent = history.recent_conversations(harness="streamlit", limit=20)
for item in recent:
    row = st.sidebar.columns([4, 1])
    row[0].button(
        item.dataset_name,
        key=f"nav-conversation-{item.conversation_id}",
        on_click=retomar_conversacion,
        args=(item,),
        use_container_width=True,
    )
    row[1].button(
        "🗑",
        key=f"delete-conversation-{item.conversation_id}",
        on_click=solicitar_borrado,
        args=(item,),
        use_container_width=True,
        help=f"Eliminar conversación {item.dataset_name}",
    )