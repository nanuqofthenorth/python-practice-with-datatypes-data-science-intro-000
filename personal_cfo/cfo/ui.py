"""Small shared UI helpers so every page looks consistent."""
from __future__ import annotations

import os

import streamlit as st

from . import db
from .charts import STATUS
from .seed import seed_sample_data

APP_TITLE = "Personal CFO"
_SESSION_KEY = "anthropic_api_key"


def setup_page(page_title: str) -> None:
    st.set_page_config(page_title=f"{page_title} - {APP_TITLE}", layout="wide")
    db.init_db()
    with st.sidebar:
        st.markdown(f"### {APP_TITLE}")
        st.caption("Your finances, run like a business.")
        if not db.has_any_data():
            if st.button("Load sample data", use_container_width=True):
                seed_sample_data()
                st.rerun()
        st.divider()
        render_ai_settings()
        st.divider()


def get_api_key() -> str | None:
    return st.session_state.get(_SESSION_KEY) or os.environ.get("ANTHROPIC_API_KEY")


def is_ai_configured() -> bool:
    return bool(get_api_key())


def render_ai_settings() -> None:
    """API key status + an optional session-only override. This is the
    only place the app talks to a third party -- everything else stays
    local, so make the on/off state and cost explicit here."""
    with st.expander("AI Advisor setup", expanded=not is_ai_configured()):
        if os.environ.get("ANTHROPIC_API_KEY"):
            st.caption("Using `ANTHROPIC_API_KEY` from the environment.")
        elif st.session_state.get(_SESSION_KEY):
            st.caption("Using the key entered below (this session only).")
        else:
            st.caption(
                "Not configured. The Advisor and CFO Briefing send your financial data "
                "to Anthropic's API to generate answers -- everything else in this app "
                "stays local. Set `ANTHROPIC_API_KEY` before launching, or paste a key "
                "for just this session below."
            )
        key_input = st.text_input(
            "Anthropic API key (session only, not saved to disk)",
            type="password", key=f"{_SESSION_KEY}_input",
        )
        if key_input:
            st.session_state[_SESSION_KEY] = key_input


def stat_tile(label: str, value: str, help_text: str | None = None) -> None:
    st.metric(label, value, help=help_text)


def escape_markdown_dollars(text: str) -> str:
    """Streamlit's markdown renderer treats a `$...$` pair as inline LaTeX
    -- and financial text is full of dollar amounts, so two of them on one
    line (e.g. "$2,350" ... "$1,450") silently turns into a math/code span.
    Escape literal dollar signs before rendering any model-generated text."""
    return text.replace("$", "\\$")


_LEVEL_COLOR = {"good": STATUS["good"], "warning": STATUS["warning"], "watch": STATUS["warning"], "critical": STATUS["critical"], "action": STATUS["critical"]}
_LEVEL_LABEL = {"good": "On track", "warning": "Watch", "watch": "Watch", "critical": "Action needed", "action": "Action needed"}


def insight_badge(level: str) -> str:
    color = _LEVEL_COLOR.get(level, STATUS["good"])
    label = _LEVEL_LABEL.get(level, level.title())
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'padding:2px 9px;border-radius:999px;font-size:0.75rem;font-weight:600;">{label}</span>'
    )


def render_insights(insights: list[dict]) -> None:
    for item in insights:
        cols = st.columns([0.14, 0.86])
        with cols[0]:
            st.markdown(insight_badge(item["level"]), unsafe_allow_html=True)
        with cols[1]:
            st.markdown(escape_markdown_dollars(item["text"]))
