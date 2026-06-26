import webbrowser
import streamlit as st
import streamlit.components.v1 as components

from config import is_configured, load_config
from db import init_db, add_node, add_edge
from graph import run_decay, graph_summary
from render import render_graph
from llm import converse

init_db()

st.set_page_config(page_title="Asterism", layout="wide", page_icon="✦")
st.markdown("""
<style>
body, .stApp { background-color: #050810; color: #e0e0e0; }
h1 { text-align: center; letter-spacing: 0.15em; color: #e0d7ff; }
.stTextInput > div > div > input,
.stSelectbox > div > div { background-color: #0d1117; color: #e0e0e0; }
.bubble-user { background: #12172b; border-radius: 12px; padding: 0.8rem 1rem; margin-bottom: 0.4rem; }
.bubble-ai { background: #1a1040; border-radius: 12px; padding: 0.8rem 1rem; margin-bottom: 0.4rem; border-left: 2px solid #4c1d95; }
.triple-tag { display: inline-block; background: #1e1b4b; color: #a78bfa; border-radius: 6px;
              padding: 2px 8px; font-size: 0.75rem; font-family: monospace; margin: 2px; }
.traversal-tag { font-size: 0.78rem; color: #7c3aed; font-family: monospace; }
iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)

if not is_configured():
    st.error("Asterism is not configured. Run `asterism init` in your terminal first.")
    st.stop()

# --- Sidebar ---
with st.sidebar:
    summary = graph_summary()
    st.metric("Nodes", summary["nodes"])
    st.metric("Edges", summary["edges"])

    if st.button("🔭 Open in Browser"):
        html_path = render_graph()
        webbrowser.open(f"file://{html_path}")

    if st.button("⏳ Run Decay"):
        run_decay()
        st.success("Decay applied.")
        st.rerun()

    with st.expander("Advanced"):
        with st.form("add_node_form"):
            node_label = st.text_input("Node label")
            node_type = st.selectbox("Type", ["concept", "entity", "event"])
            if st.form_submit_button("Add Node") and node_label.strip():
                add_node(node_label.strip(), node_type)
                st.success(f"Added: {node_label}")

        with st.form("add_edge_form"):
            src = st.text_input("Source")
            tgt = st.text_input("Target")
            if st.form_submit_button("Add Edge") and src.strip() and tgt.strip():
                add_edge(src.strip(), tgt.strip())
                st.success(f"Edge: {src} → {tgt}")

# --- Header ---
st.markdown("<h1>✦ Asterism</h1>", unsafe_allow_html=True)

# --- Session state ---
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Chat history display ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        css_class = "bubble-user" if msg["role"] == "user" else "bubble-ai"
        st.markdown(f'<div class="{css_class}">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("triples"):
            tags = "".join(
                f'<span class="triple-tag">{t["source"]} → {t["relationship"]} → {t["target"]}</span>'
                for t in msg["triples"]
            )
            st.markdown(tags, unsafe_allow_html=True)

# --- Chat input ---
user_input = st.chat_input("Talk to Asterism...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(f'<div class="bubble-user">{user_input}</div>', unsafe_allow_html=True)

    with st.spinner("Thinking..."):
        result = converse(user_input, st.session_state.conversation_history)

    st.session_state.conversation_history.append({"role": "user", "content": user_input})
    st.session_state.conversation_history.append({"role": "assistant", "content": result["response"]})

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["response"],
        "triples": result["triples_extracted"],
    })
    with st.chat_message("assistant"):
        st.markdown(f'<div class="bubble-ai">{result["response"]}</div>', unsafe_allow_html=True)
        if result["triples_extracted"]:
            tags = "".join(
                f'<span class="triple-tag">{t["source"]} → {t["relationship"]} → {t["target"]}</span>'
                for t in result["triples_extracted"]
            )
            st.markdown(tags, unsafe_allow_html=True)

    st.rerun()

# --- Constellation (always visible) ---
st.divider()
st.markdown("#### ✦ Constellation")
html_path = render_graph()
with open(html_path) as f:
    components.html(f.read(), height=560, scrolling=False)
