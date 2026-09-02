"""Small shared UI helpers so every page looks consistent."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import streamlit as st

from . import auth
from . import calendar_export as cal
from . import db
from .charts import STATUS
from .seed import seed_sample_data

APP_TITLE = "Personal CFO"
_SESSION_KEY = "anthropic_api_key"


def is_dark_theme() -> bool:
    """Whether the viewer currently has dark mode active -- Streamlit's own
    Light/Dark/System picker lives in its built-in menu (top right) with no
    app code needed for the UI chrome itself. Plotly figures don't follow
    that automatically, though (they're static JSON, not themed CSS), so
    every chart builder in cfo.charts takes the result of this as a `dark`
    argument."""
    try:
        return st.context.theme.type == "dark"
    except Exception:  # noqa: BLE001 -- theme context can be unavailable early in a run
        return False


def setup_page(page_title: str) -> None:
    st.set_page_config(page_title=f"{page_title} - {APP_TITLE}", layout="wide")
    auth.check_authentication()
    db.init_db()
    with st.sidebar:
        st.markdown(f"### {APP_TITLE}")
        st.caption("Your finances, run like a business.")
        render_profile_snippet()
        if not db.has_any_data():
            if st.button("Load sample data", use_container_width=True):
                seed_sample_data()
                st.rerun()
        st.divider()
        render_ai_settings()
        st.divider()
        render_account_status()


def render_profile_snippet() -> None:
    profile = db.get_profile()
    if not profile or not profile.get("name"):
        st.caption("No profile yet -- set one up on the Profile page.")
        return
    cols = st.columns([1, 3])
    with cols[0]:
        if profile.get("photo"):
            st.image(profile["photo"], width=44)
    with cols[1]:
        st.markdown(f"**{profile['name']}**")


def render_account_status() -> None:
    """Only shown once some form of login is configured -- nothing to
    report otherwise."""
    if not auth.is_protected():
        return
    identity = auth.current_google_identity()
    if identity:
        st.caption(f"Signed in as {identity}")
        if st.button("Log out", use_container_width=True):
            st.logout()
    elif auth.is_unlocked_by_password():
        st.caption("Unlocked with password.")


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


ACTIONABLE_LEVELS = {"warning", "critical", "watch", "action"}


def _item_title(item: dict) -> str:
    return item.get("title") or item.get("text", "")


def _item_detail(item: dict) -> str:
    return item.get("detail") or item.get("text", "")


def _calendar_buttons_for_item(item: dict, key: str) -> None:
    event = cal.CalendarEvent(title=_item_title(item)[:120], description=_item_detail(item))
    ics_bytes = cal.build_ics([event])
    btn_cols = st.columns([1, 1, 2])
    with btn_cols[0]:
        st.download_button(
            "Add to Calendar", ics_bytes, file_name=f"{cal.slugify(event.title)}.ics",
            mime="text/calendar", key=f"{key}_ics", use_container_width=True,
        )
    with btn_cols[1]:
        st.link_button("Google Calendar", cal.google_calendar_link(event), use_container_width=True)


def render_action_items(items: list[dict], key_prefix: str = "item", show_calendar_buttons: bool = True) -> None:
    """Render insights or CFO Briefing items -- both are {level, text} or
    {level, title, detail} dicts. Actionable levels (warning/critical from
    rule-based insights, watch/action from the AI briefing) get a small
    Add to Calendar row so a recommendation can become a real reminder."""
    for i, item in enumerate(items):
        level = item.get("level", "good")
        has_title = bool(item.get("title"))
        with st.container(border=has_title):
            cols = st.columns([0.14, 0.86])
            with cols[0]:
                st.markdown(insight_badge(level), unsafe_allow_html=True)
            with cols[1]:
                detail = escape_markdown_dollars(_item_detail(item))
                if has_title:
                    st.markdown(f"**{escape_markdown_dollars(item['title'])}**  \n{detail}")
                else:
                    st.markdown(detail)
                if show_calendar_buttons and level in ACTIONABLE_LEVELS:
                    _calendar_buttons_for_item(item, key=f"{key_prefix}_{i}")


def render_insights(insights: list[dict]) -> None:
    """Back-compat alias -- prefer render_action_items for new code."""
    render_action_items(insights, key_prefix="insight")


def bulk_calendar_download_button(
    items: list[dict], key: str, label: str = "Add all action items to calendar"
) -> None:
    """One .ics bundling every actionable item across whatever lists are
    passed in (rule-based insights + AI briefing, typically) -- staggered
    a day apart so the reminders don't all land on top of each other."""
    actionable = [item for item in items if item.get("level") in ACTIONABLE_LEVELS]
    if not actionable:
        return
    events = []
    for i, item in enumerate(actionable):
        start = (datetime.now() + timedelta(days=i + 1)).replace(hour=9, minute=0, second=0, microsecond=0)
        events.append(cal.CalendarEvent(title=_item_title(item)[:120], description=_item_detail(item), start=start))
    ics_bytes = cal.build_ics(events, calendar_name="Personal CFO Action Items")
    st.download_button(
        f"{label} ({len(events)})", ics_bytes, file_name="personal-cfo-action-items.ics",
        mime="text/calendar", key=key,
    )
