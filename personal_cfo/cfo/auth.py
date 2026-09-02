"""Optional login gate: a shared password, Google Sign-In, or both.

Off by default -- this stays a zero-config, run-it-yourself app unless you
opt in to at least one method:

- The PERSONAL_CFO_PASSWORD environment variable for a single shared
  password (see Settings for setup).
- Google Sign-In via Streamlit's own native `st.login()` (Authlib under
  the hood), enabled by adding real OAuth credentials to
  `.streamlit/secrets.toml` -- see `secrets.toml.example` and the Settings
  page for the exact steps. This is real Google Cloud infrastructure you
  register yourself; there's no credential we can hand you for it.

If both are configured, either one unlocks the app for that browser
session. They differ in what happens after: everyone who unlocks the app
via the shared password sees the same data (there's no way to tell them
apart), while each distinct Google account gets its own isolated data --
see cfo.db.current_user_id() and its "local" fallback for how that's
scoped.
"""
from __future__ import annotations

import hmac
import os

import streamlit as st

_SESSION_FLAG = "_authenticated"


def is_password_protected() -> bool:
    return bool(os.environ.get("PERSONAL_CFO_PASSWORD"))


def is_google_oauth_configured() -> bool:
    try:
        return bool(st.secrets.get("auth", {}).get("client_id"))
    except Exception:  # noqa: BLE001 -- no secrets.toml at all raises here; treat as "not configured"
        return False


def is_protected() -> bool:
    return is_password_protected() or is_google_oauth_configured()


def is_unlocked_by_password() -> bool:
    return bool(st.session_state.get(_SESSION_FLAG))


def _google_logged_in() -> bool:
    if not is_google_oauth_configured():
        return False
    return bool(getattr(st.user, "is_logged_in", False))


def current_google_identity() -> str | None:
    """A display label for the signed-in Google account, or None if not
    applicable (not configured, or not logged in via Google)."""
    if not _google_logged_in():
        return None
    return getattr(st.user, "email", None) or getattr(st.user, "name", None)


def current_google_user_id() -> str | None:
    """A stable per-account identifier for data scoping -- Google's OIDC
    `sub` claim, not email (an email can change hands or be renamed; `sub`
    can't). None if not applicable. This is the multi-tenancy key: see
    cfo.db.current_user_id(), which falls back to a single shared "local"
    tenant when nobody is signed in via Google, preserving today's
    single-user behavior for anyone not using OAuth."""
    if not _google_logged_in():
        return None
    sub = getattr(st.user, "sub", None)
    return f"google:{sub}" if sub else None


def check_authentication() -> None:
    """Call at the very top of every page, immediately after
    st.set_page_config and before anything else renders or any data is
    read. No-op unless a password or Google Sign-In is configured.
    Otherwise blocks the rest of the page (via st.stop()) until the user
    authenticates by whichever configured method -- either one satisfies
    the gate for this browser session."""
    password = os.environ.get("PERSONAL_CFO_PASSWORD")
    google_configured = is_google_oauth_configured()
    if not password and not google_configured:
        return
    if is_unlocked_by_password() or _google_logged_in():
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
    st.caption("This app is protected.")

    if google_configured:
        if st.button("Sign in with Google", type="primary"):
            st.login()
        if password:
            st.caption("or")

    if password:
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
