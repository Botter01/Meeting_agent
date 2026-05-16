import streamlit as st
import requests
import json

BACKEND_URL = "http://backend:8000"

st.set_page_config(
    page_title="Meeting Agent",
    layout="centered",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0d0d;
    color: #e8e8e8;
}

.stApp {
    background-color: #0d0d0d;
}

h1, h2, h3 {
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: -0.02em;
}

.main-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.4rem;
    font-weight: 600;
    color: #f0f0f0;
    border-left: 4px solid #00e5a0;
    padding-left: 1rem;
    margin-bottom: 0.2rem;
}

.subtitle {
    color: #666;
    font-size: 0.9rem;
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 2rem;
    padding-left: 1.2rem;
}

.step-box {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #00e5a0;
    border-radius: 4px;
    padding: 0.6rem 1rem;
    margin: 0.4rem 0;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    color: #ccc;
    animation: fadeIn 0.3s ease;
}

.step-box.retry {
    border-left-color: #ffaa00;
    color: #ffaa00;
}

.step-box.done {
    border-left-color: #00e5a0;
    color: #00e5a0;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateX(-8px); }
    to   { opacity: 1; transform: translateX(0); }
}

.summary-card {
    background: #111;
    border: 1px solid #222;
    border-radius: 6px;
    padding: 1.4rem 1.6rem;
    font-size: 0.95rem;
    line-height: 1.7;
    white-space: pre-wrap;
    color: #ddd;
    margin-top: 0.5rem;
}

.task-card {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 6px;
    padding: 0.8rem 1.2rem;
    margin: 0.5rem 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
}

.task-name {
    font-weight: 600;
    color: #f0f0f0;
    flex: 1;
}

.task-meta {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #777;
}

.badge {
    padding: 2px 8px;
    border-radius: 3px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
}

.badge-high   { background: #2a0a0a; color: #ff6b6b; border: 1px solid #ff6b6b44; }
.badge-medium { background: #1f1500; color: #ffaa00; border: 1px solid #ffaa0044; }
.badge-low    { background: #0a1f12; color: #00e5a0; border: 1px solid #00e5a044; }

.stFileUploader > div {
    background: #111 !important;
    border: 1px dashed #333 !important;
    border-radius: 6px !important;
}

.stButton > button {
    background: #00e5a0 !important;
    color: #000 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 0.5rem 2rem !important;
    font-size: 0.9rem !important;
    transition: opacity 0.2s !important;
}

.stButton > button:hover {
    opacity: 0.85 !important;
}

.stButton > button:disabled {
    background: #1a1a1a !important;
    color: #444 !important;
}

hr {
    border-color: #1e1e1e !important;
    margin: 1.5rem 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Meeting Agent</div>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Töltsd fel a transzkriptet (.txt)",
    type=["txt"]
)

run_btn = st.button("Futtatás", disabled=uploaded is None)

if run_btn and uploaded is not None:
    st.markdown("---")
    st.markdown("### Folyamat:")

    log_placeholder = st.empty() 
    steps_rendered = []

    with requests.post(
        f"{BACKEND_URL}/run",
        files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")},
        stream=True,
        timeout=300,
    ) as resp:
        if resp.status_code != 200:
            st.error(f"Backend hiba: {resp.status_code} – {resp.text}")
        else:
            for line in resp.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                if not line.startswith("data: "):
                    continue

                payload = json.loads(line[6:])
                event   = payload.get("event")

                if event in ("status", "step"):
                    msg = payload.get("message", "")
                    node = payload.get("node", "")
                    cls = "retry" if node == "increment_retry" else "step-box"
                    steps_rendered.append(f'<div class="step-box {cls}">› {msg}</div>')
                    log_placeholder.markdown("".join(steps_rendered), unsafe_allow_html=True)

                elif event == "done":
                    steps_rendered.append('<div class="step-box done">✓ Kész!</div>')
                    log_placeholder.markdown("".join(steps_rendered), unsafe_allow_html=True)

                    summary = payload.get("summary", "")
                    items   = payload.get("approved_items", [])
                    retries = payload.get("retry_count", 0)

                    st.markdown("---")
                    st.markdown("Összefoglaló")
                    st.markdown(f'<div class="summary-card">{summary}</div>', unsafe_allow_html=True)

                    st.markdown("---")
                    st.markdown(f"Jóváhagyott action itemek  <span style='color:#555;font-size:0.8rem;font-family:monospace'>({len(items)} db, {retries} retry)</span>", unsafe_allow_html=True)

                    priority_badge = {
                        "High":   '<span class="badge badge-high">High</span>',
                        "Medium": '<span class="badge badge-medium">Medium</span>',
                        "Low":    '<span class="badge badge-low">Low</span>',
                    }

                    for item in items:
                        badge = priority_badge.get(item.get("priority", "Low"), "")
                        assignee = item.get("assignee", "–")
                        deadline = item.get("deadline", "–")
                        st.markdown(f"""
                        <div class="task-card">
                            <div class="task-name">{item.get('task','')}</div>
                            <div class="task-meta">{assignee} &nbsp;·&nbsp; {deadline}</div>
                            {badge}
                        </div>
                        """, unsafe_allow_html=True)

                elif event == "error":
                    st.error(payload.get("message", "Ismeretlen hiba"))