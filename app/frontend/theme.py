import streamlit as st


THEME_CSS = """
<style>
:root {
    --ink: #ecf4ff;
    --muted: #9badc7;
    --panel: rgba(14, 24, 42, 0.92);
    --panel-strong: #111e34;
    --line: rgba(146, 175, 214, 0.14);
    --accent: #56d5ff;
    --accent-strong: #20a9dc;
    --success: #75e6b5;
    --danger: #ff7f96;
}

.stApp {
    background:
        radial-gradient(circle at 82% 8%, rgba(42, 169, 214, 0.12), transparent 24rem),
        radial-gradient(circle at 12% 90%, rgba(91, 92, 214, 0.10), transparent 28rem),
        #07101e;
    color: var(--ink);
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stToolbar"],
#MainMenu,
footer {
    visibility: hidden;
}

[data-testid="stSidebar"] {
    background: rgba(7, 14, 27, 0.96);
    border-right: 1px solid var(--line);
    min-width: 280px;
    max-width: 320px;
}

[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    padding-top: 0.8rem;
}

[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
    border-radius: 12px;
    margin: 0.12rem 0;
    color: var(--muted);
}

[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {
    background: linear-gradient(90deg, rgba(86, 213, 255, 0.16), rgba(86, 213, 255, 0.04));
    color: var(--ink);
    box-shadow: inset 3px 0 0 var(--accent);
}

.block-container {
    max-width: 1480px;
    min-height: calc(100vh - 1.2rem);
    padding-top: 1.1rem;
    padding-bottom: 1.1rem;
}

h1, h2, h3, p, label, span {
    color: var(--ink);
}

.stMarkdown p {
    color: var(--muted);
}

.stButton > button {
    border: 1px solid var(--line);
    border-radius: 11px;
    min-height: 42px;
    background: rgba(18, 33, 55, 0.82);
    color: var(--ink);
    font-weight: 650;
    transition: 160ms ease;
}

.stButton > button:hover {
    border-color: rgba(86, 213, 255, 0.52);
    background: rgba(30, 58, 88, 0.92);
    color: #ffffff;
    transform: translateY(-1px);
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    border: 0;
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    color: #05101d;
    box-shadow: 0 10px 30px rgba(32, 169, 220, 0.18);
}

[data-testid="stFileUploader"] {
    border: 1px dashed rgba(86, 213, 255, 0.28);
    border-radius: 18px;
    background: rgba(11, 24, 42, 0.68);
    padding: 0.7rem;
}

[data-testid="stFileUploaderDropzone"] {
    border: 0;
    background: transparent;
    min-height: 175px;
}

[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small {
    font-size: 0;
}

[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none;
}

[data-testid="stFileUploader"] button {
    font-size: 0;
}

[data-testid="stFileUploader"] button::after {
    content: "Seleccionar archivos";
    font-size: 0.84rem;
}

.ui-intro {
    min-height: 118px;
    border: 1px solid var(--line);
    border-radius: 18px;
    margin-bottom: 1rem;
    padding: 1.15rem 1.45rem;
    background: linear-gradient(135deg, rgba(19, 48, 78, 0.96), rgba(13, 31, 54, 0.92));
}

.ui-intro h1 {
    margin: 0 0 0.42rem;
    font-size: clamp(1.75rem, 2.5vw, 2.25rem);
    color: #f7fbff;
}

.ui-intro p {
    max-width: 980px;
    margin: 0;
}

[data-testid="stTextInput"] input {
    border: 1px solid var(--line);
    border-radius: 16px;
    background: rgba(12, 23, 40, 0.96);
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.22);
    color: var(--ink);
    min-height: 42px;
}

[data-testid="stChatMessage"] {
    border: 1px solid var(--line);
    border-radius: 16px;
    background: rgba(13, 25, 43, 0.74);
    margin-bottom: 0.55rem;
}

[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 1rem;
}

[role="dialog"] {
    border: 1px solid var(--line);
    border-radius: 20px;
    background: #101c30;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.48);
}

.ui-hero {
    min-height: 275px;
    border: 1px solid var(--line);
    border-radius: 24px;
    padding: 2.2rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow: hidden;
    background:
        linear-gradient(145deg, rgba(16, 38, 64, 0.96), rgba(8, 23, 40, 0.94));
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.16);
}

.ui-kicker {
    color: var(--accent) !important;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.ui-hero h1,
.ui-chat-title {
    margin: 0.35rem 0 0.7rem;
    color: #f7fbff;
    line-height: 1.04;
    letter-spacing: -0.035em;
}

.ui-hero h1 {
    max-width: 620px;
    font-size: clamp(2.25rem, 4vw, 3.45rem);
}

.ui-muted {
    color: var(--muted) !important;
}

.ui-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
}

.ui-badge {
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: 0.42rem 0.72rem;
    background: rgba(86, 213, 255, 0.06);
    color: #bddff1;
    font-size: 0.78rem;
}

.ui-upload-card,
.ui-chat-header,
.ui-status-card {
    border: 1px solid var(--line);
    border-radius: 20px;
    background: var(--panel);
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

.ui-upload-card {
    min-height: 420px;
    padding: 1.6rem;
}

.ui-upload-card h3,
.ui-chat-header h1 {
    margin-bottom: 0.35rem;
}

.ui-chat-header {
    padding: 1.35rem 1.45rem;
    margin-bottom: 1rem;
}

.ui-chat-title {
    font-size: clamp(1.7rem, 3vw, 2.4rem);
}

.ui-status {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    color: var(--success) !important;
    font-size: 0.82rem;
}

.ui-status::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 14px rgba(117, 230, 181, 0.72);
}

@media (max-width: 760px) {
    .block-container {
        padding: 1.2rem 0.8rem 2rem;
    }
    .ui-hero,
    .ui-upload-card {
        min-height: auto;
        padding: 1.35rem;
    }
    .ui-hero h1 {
        font-size: 2.35rem;
    }
}
</style>
"""


def inject_theme():
    st.markdown(THEME_CSS, unsafe_allow_html=True)
