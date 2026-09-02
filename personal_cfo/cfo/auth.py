"""Optional password gate.

Off by default -- this stays a zero-config, run-it-yourself app unless you
opt in. Set the PERSONAL_CFO_PASSWORD environment variable before
launching to require a password once per browser session before anything
else renders.

This is a single shared password, not a user-accounts system -- it exists
to close the gap between "meant to run on localhost" and "someone runs
this somewhere reachable over a network," not to support multiple people
with separate logins.
"""
from __future__ import annotations

import hmac
import os

import streamlit as st

_SESSION_FLAG = "_authenticated"


def is_password_protected() -> bool:
    return bool(os.environ.get("PERSONAL_CFO_PASSWORD"))


def check_authentication() -> None:
    """Call at the very top of every page, immediately after
    st.set_page_config and before anything else renders or any data is
    read. No-op if PERSONAL_CFO_PASSWORD isn't set. Otherwise blocks the
    rest of the page (via st.stop()) until the correct password is
    entered for this browser session."""
    password = os.environ.get("PERSONAL_CFO_PASSWORD")
    if not password:
        return
    if st.session_state.get(_SESSION_FLAG):
        return

    # Streamlit auto-renders the multipage nav (every page name) in the
    # sidebar before page code runs, regardless of st.stop() below -- no
    # data leak, since every page is independently gated, but there's no
    # reason to show page names on what should read as a login screen.
    st.markdown(
        "<style>[data-testid='stSidebarNav'] { display: none; }</style>",
        unsafe_allow_html=True,
    )
    st.title("Personal CFO")
    st.caption("This app is password protected.")
    with st.form("password_gate"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted:
        if hmac.compare_digest(entered, password):
            st.session_state[_SESSION_FLAG] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
