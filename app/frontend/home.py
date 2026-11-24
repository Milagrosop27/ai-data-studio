import hashlib
import io
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlcipher3 import dbapi2 as sqlite3

from app.backend.history import HistoryStore
from app.backend.local_config import load_local_config, ollama_model
from app.backend.uploads import purge_expired_uploads


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
HERO_IMAGE = Path(__file__).resolve().parent / "assets" / "agent-workflow.svg"

try:
    load_local_config(PROJECT_ROOT / ".env")
    history = HistoryStore()
    purge_expired_uploads(UPLOAD_DIR, history)
except (OSError, sqlite3.Error) as error:
    st.error(f"No se pudo mantener el historial/cargas locales: {error}")
    st.stop()

for key, value in (
    ("dataset_cargado", False),
    ("ruta_archivo", None),
    ("dataset_id", None),
    ("conversation_id", None),
    ("messages", []),
    ("agent_executor", None),
    ("prompt_activo", None),
):
    if key not in st.session_state:
        st.session_state[key] = value

st.markdown(
    """
    <section class="ui-intro">
      <h1>Estudio de Datos IA</h1>
      <p>
        Analiza archivos CSV de forma privada: descubre patrones, formula preguntas
        y genera visualizaciones sin enviar tus datos a servicios externos.
      </p>
    </section>
    """,
    unsafe_allow_html=True,
)

col_left, col_right = st.columns([1.55, 0.72], gap="large")
with col_left:
    visual = st.container(border=True)
    with visual:
        st.image(str(HERO_IMAGE), use_container_width=True)

with col_right:
    upload = st.container(border=True)
    with upload:
        st.markdown(
            """
            <p class="ui-kicker">NUEVO ANÁLISIS</p>
            <h3>Subir archivo CSV</h3>
            <p class="ui-muted">
                Adjunta el archivo una sola vez. Podrás continuar esta conversación
                hasta por 48 horas.
            </p>
            """,
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Archivo CSV",
            type=["csv"],
            label_visibility="collapsed",
        )
        if uploaded_file:
            file_bytes = uploaded_file.getvalue()
            if len(file_bytes) > 10 * 1024 * 1024:
                st.error("El CSV supera el límite local de 10 MB.")
                st.stop()
            try:
                preview = pd.read_csv(io.BytesIO(file_bytes), sep=";")
                if len(preview.columns) == 1:
                    preview = pd.read_csv(io.BytesIO(file_bytes), sep=",")
            except (
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
                UnicodeDecodeError,
            ) as error:
                st.error(f"No se pudo leer el CSV: {error}")
                st.stop()
            if len(preview) > 100_000:
                st.error("El CSV supera el límite local de 100 000 filas.")
                st.stop()

            dataset_id = hashlib.sha256(file_bytes).hexdigest()
            dataset_path = UPLOAD_DIR / f"{dataset_id}.csv"
            try:
                if not dataset_path.exists():
                    dataset_path.write_bytes(file_bytes)
                if st.session_state.dataset_id != dataset_id:
                    conversation_id = uuid.uuid4().hex
                    history.attach_dataset(
                        conversation_id=conversation_id,
                        dataset_id=dataset_id,
                        dataset_name=Path(uploaded_file.name).name,
                    )
                    history.record_event(
                        conversation_id=conversation_id,
                        event_type="agent_action",
                        content="CSV asociado a una conversación local",
                        harness="streamlit",
                        model=ollama_model(),
                        status="ok",
                    )
                    st.session_state.conversation_id = conversation_id
                    st.session_state.dataset_id = dataset_id
                    st.session_state.active_dataset_id = dataset_id
                    st.session_state.messages = []
                    st.session_state.agent_executor = None
                    st.session_state.prompt_activo = None
                st.session_state.ruta_archivo = str(dataset_path)
                st.session_state.dataset_cargado = True
            except (OSError, sqlite3.Error, ValueError) as error:
                st.error(f"No se pudo conservar el CSV y asociarlo al historial: {error}")
                st.stop()

            st.success(
                f"{Path(uploaded_file.name).name}: "
                f"{preview.shape[0]} filas, {preview.shape[1]} columnas."
            )
            st.caption(
                "Archivo listo. Revisa el nombre y continúa con el análisis."
            )
            if st.button(
                "Iniciar análisis",
                type="primary",
                use_container_width=True,
                key="start-csv-analysis",
            ):
                st.switch_page("app/frontend/chat.py")
