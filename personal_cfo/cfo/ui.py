"""Small shared UI helpers so every page looks consistent."""
from __future__ import annotations

import streamlit as st

from . import db
from .charts import STATUS
from .seed import seed_sample_data

APP_TITLE = "Personal CFO"


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


def stat_tile(label: str, value: str, help_text: str | None = None) -> None:
    st.metric(label, value, help=help_text)


def insight_badge(level: str) -> str:
    color = STATUS.get(level, STATUS["good"])
    label = {"good": "On track", "warning": "Watch", "critical": "Action needed"}.get(level, level.title())
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
            st.markdown(item["text"])
