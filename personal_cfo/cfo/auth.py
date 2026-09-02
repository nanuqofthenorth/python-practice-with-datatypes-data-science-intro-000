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

The password gate is rate-limited per client IP (5 wrong attempts locks
that IP out, doubling in duration on repeated abuse, up to an hour) --
see _record_failed_attempt() below. This matters once the app is
reachable over the internet rather than just localhost; Google Sign-In
doesn't need this, since Google already rate-limits its own login.
"""
from __future__ import annotations

import hmac
import os
import threading
import time

import streamlit as st

_SESSION_FLAG = "_authenticated"

# --------------------------------------------------------- rate limiting
# In-memory, per-process -- shared across every browser session hitting
# this server (that's the point: a session-scoped counter is trivially
# defeated by opening a new tab), but it resets on restart/redeploy and
# doesn't share state across multiple server instances if this app is
# ever scaled horizontally. Good enough for the single-instance hosting
# this app is actually built for; a real distributed rate limiter needs
# a shared store (Redis, a database table) this app doesn't otherwise need.
_RATE_LIMIT_LOCK = threading.Lock()
_failed_attempts: dict[str, list[float]] = {}
_lockouts: dict[str, tuple[float, int]] = {}  # identifier -> (locked_until, strikes)

_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60
_BASE_LOCKOUT_SECONDS = 5 * 60
_MAX_LOCKOUT_SECONDS = 60 * 60


def _client_identifier() -> str:
    """Best-effort per-client key for rate limiting -- the viewer's IP
    address if Streamlit can determine one (it reads this from the
    request, including any X-Forwarded-For a reverse proxy sets, which
    covers hosts like Render). Falls back to a single shared "unknown"
    bucket if not: still real rate limiting, just coarser -- everyone
    without a resolvable IP shares one limit rather than each being
    unlimited."""
    try:
        return st.context.ip_address or "unknown"
    except Exception:  # noqa: BLE001 -- context can be unavailable early in a run
        return "unknown"


def _seconds_locked_out(identifier: str) -> float:
    with _RATE_LIMIT_LOCK:
        locked_until, _strikes = _lockouts.get(identifier, (0.0, 0))
    return max(0.0, locked_until - time.time())


def _record_failed_attempt(identifier: str) -> None:
    now = time.time()
    with _RATE_LIMIT_LOCK:
        attempts = [t for t in _failed_attempts.get(identifier, []) if now - t < _WINDOW_SECONDS]
        attempts.append(now)
        if len(attempts) >= _MAX_ATTEMPTS:
            _, strikes = _lockouts.get(identifier, (0.0, 0))
            strikes += 1
            duration = min(_BASE_LOCKOUT_SECONDS * (2 ** (strikes - 1)), _MAX_LOCKOUT_SECONDS)
            _lockouts[identifier] = (now + duration, strikes)
            attempts = []
        _failed_attempts[identifier] = attempts


def _record_successful_attempt(identifier: str) -> None:
    with _RATE_LIMIT_LOCK:
        _failed_attempts.pop(identifier, None)
        _lockouts.pop(identifier, None)


def _format_duration(seconds: float) -> str:
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minute" + ("" if minutes == 1 else "s")


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
        identifier = _client_identifier()
        remaining = _seconds_locked_out(identifier)
        if remaining > 0:
            st.error(f"Too many incorrect attempts. Try again in {_format_duration(remaining)}.")
        else:
            with st.form("password_gate"):
                entered = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Unlock")
            if submitted:
                if hmac.compare_digest(entered, password):
                    _record_successful_attempt(identifier)
                    st.session_state[_SESSION_FLAG] = True
                    st.rerun()
                else:
                    _record_failed_attempt(identifier)
                    remaining = _seconds_locked_out(identifier)
                    if remaining > 0:
                        st.error(f"Too many incorrect attempts. Try again in {_format_duration(remaining)}.")
                    else:
                        st.error("Incorrect password.")

    st.stop()
