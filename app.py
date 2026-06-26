import streamlit as st
import streamlit.components.v1 as components

from db import init_db, add_node, add_edge
from graph import run_decay
from render import render_graph
import llm

init_db()

st.set_page_config(page_title="Asterism", layout="wide", page_icon="✦")
st.markdown("""
<style>
body, .stApp { background-color: #0a0f1a; color: #e0e0e0; }
.stTextInput > div > div > input,
.stSelectbox > div > div { background-color: #111827; color: #e0e0e0; }
.bubble { background: #1a1f2e; border-radius: 12px; padding: 1rem; margin-bottom: 0.5rem; }
.traversal-tag { font-size: 0.8rem; color: #a78bfa; font-family: monospace; }
iframe { border: none !important; }
</style>
""", unsafe_allow_html=True)

st.title("✦ Asterism")

# --- Sidebar ---
with st.sidebar:
    st.header("Graph Editor")

    with st.form("add_node_form"):
        st.subheader("Add Node")
        node_label = st.text_input("Label")
        node_type = st.selectbox("Type", ["concept", "entity", "event"])
        if st.form_submit_button("Add Node") and node_label.strip():
            add_node(node_label.strip(), node_type)
            st.success(f"Added: {node_label}")

    with st.form("add_edge_form"):
        st.subheader("Add Edge")
        src = st.text_input("Source label")
        tgt = st.text_input("Target label")
        if st.form_submit_button("Add Edge") and src.strip() and tgt.strip():
            add_edge(src.strip(), tgt.strip())
            st.success(f"Edge: {src} → {tgt}")

    if st.button("⏳ Run Decay"):
        run_decay()
        st.success("Decay applied.")

    st.button("🔄 Refresh Graph")

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(f'<div class="bubble">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("traversals"):
            st.markdown("**Traversals:**")
            for t in msg["traversals"]:
                st.markdown(f'<span class="traversal-tag">→ {t[0]} → {t[1]}</span>', unsafe_allow_html=True)

# --- Chat input ---
user_input = st.chat_input("Ask Asterism...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(f'<div class="bubble">{user_input}</div>', unsafe_allow_html=True)

    with st.spinner("Thinking..."):
        result = llm.query(user_input)

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["response"],
        "traversals": result["traversals"],
    })
    with st.chat_message("assistant"):
        st.markdown(f'<div class="bubble">{result["response"]}</div>', unsafe_allow_html=True)
        if result["traversals"]:
            st.markdown("**Traversals:**")
            for t in result["traversals"]:
                st.markdown(f'<span class="traversal-tag">→ {t[0]} → {t[1]}</span>', unsafe_allow_html=True)

# --- Graph render ---
st.divider()
html_path = render_graph()
with open(html_path, "r") as f:
    graph_html = f.read()
components.html(graph_html, height=620, scrolling=False)
