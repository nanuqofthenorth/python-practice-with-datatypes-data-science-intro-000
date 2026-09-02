from __future__ import annotations

import anthropic
import streamlit as st

from cfo import advisor
from cfo import db
from cfo.ui import escape_markdown_dollars, get_api_key, is_ai_configured, setup_page

setup_page("Advisor")

st.title("Ask Your CFO")
st.caption("Ask anything about your finances -- answers are grounded in the data you've entered in this app.")

if not is_ai_configured():
    st.info("Set up an Anthropic API key in the **AI Advisor setup** panel in the sidebar to use this page.")
    st.stop()

if not db.has_any_data():
    st.info("Add some accounts, transactions, or debts first (or load sample data from the sidebar) -- "
            "there's nothing to consult on yet.")
    st.stop()

snapshot = advisor.snapshot_json()
with st.expander("What data is sent to Claude"):
    st.caption("Exactly this JSON snapshot, plus your question, is sent to Anthropic's API on every question below.")
    st.json(snapshot)

st.session_state.setdefault("advisor_messages", [])

top = st.columns([3, 1])
with top[1]:
    if st.button("New conversation", use_container_width=True):
        st.session_state.advisor_messages = []
        st.rerun()

pending = st.session_state.pop("_pending_question", None)
prompt = st.chat_input("Ask about your finances...") or pending

if not st.session_state.advisor_messages and not prompt:
    st.markdown("**Try asking:**")
    starters = [
        "What should I prioritize with my extra cash this month?",
        "Am I on track for my goals? What would get me there faster?",
        "Should I pay down debt or keep investing right now?",
        "Where is my spending furthest off budget, and what should I do about it?",
    ]
    cols = st.columns(2)
    for i, starter in enumerate(starters):
        if cols[i % 2].button(starter, use_container_width=True, key=f"starter_{i}"):
            st.session_state["_pending_question"] = starter
            st.rerun()

for msg in st.session_state.advisor_messages:
    with st.chat_message(msg["role"]):
        st.markdown(escape_markdown_dollars(msg["content"]))

if prompt:
    st.session_state.advisor_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(escape_markdown_dollars(prompt))

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = advisor.ask_question(
                    get_api_key(), prompt, snapshot, history=st.session_state.advisor_messages[:-1]
                )
                st.markdown(escape_markdown_dollars(answer))
                st.session_state.advisor_messages.append({"role": "assistant", "content": answer})
            except Exception as exc:  # noqa: BLE001 -- surface any API failure to the user, don't crash the app
                if isinstance(exc, anthropic.AuthenticationError):
                    st.error("That API key was rejected. Check it in the sidebar.")
                elif isinstance(exc, anthropic.RateLimitError):
                    st.error("Rate limited by the Anthropic API -- try again in a moment.")
                elif isinstance(exc, anthropic.APIConnectionError):
                    st.error("Couldn't reach the Anthropic API -- check your network connection.")
                else:
                    st.error(f"The advisor hit an error: {exc}")
                st.session_state.advisor_messages.pop()
