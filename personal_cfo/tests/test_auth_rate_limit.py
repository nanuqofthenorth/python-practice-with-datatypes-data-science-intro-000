"""Rate limiting on the shared-password gate (cfo/auth.py)."""
from __future__ import annotations

import time

import pytest

from cfo import auth


@pytest.fixture(autouse=True)
def clean_rate_limit_state():
    """Each test gets an empty slate -- these dicts are module-level,
    shared process-wide by design (see auth.py docstring)."""
    auth._failed_attempts.clear()
    auth._lockouts.clear()
    yield
    auth._failed_attempts.clear()
    auth._lockouts.clear()


def test_no_lockout_before_max_attempts():
    for _ in range(auth._MAX_ATTEMPTS - 1):
        auth._record_failed_attempt("1.2.3.4")
    assert auth._seconds_locked_out("1.2.3.4") == 0.0


def test_locks_out_after_max_attempts():
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt("1.2.3.4")
    assert auth._seconds_locked_out("1.2.3.4") > 0.0


def test_lockout_is_per_identifier():
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt("1.2.3.4")
    assert auth._seconds_locked_out("5.6.7.8") == 0.0


def test_successful_attempt_clears_lockout_state():
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt("1.2.3.4")
    assert auth._seconds_locked_out("1.2.3.4") > 0.0

    auth._record_successful_attempt("1.2.3.4")
    assert auth._seconds_locked_out("1.2.3.4") == 0.0
    assert "1.2.3.4" not in auth._failed_attempts


def test_repeated_lockouts_escalate_duration():
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt("1.2.3.4")
    first_lockout = auth._seconds_locked_out("1.2.3.4")

    # Force the first lockout to look expired, then trigger a second one.
    locked_until, strikes = auth._lockouts["1.2.3.4"]
    auth._lockouts["1.2.3.4"] = (time.time() - 1, strikes)
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt("1.2.3.4")
    second_lockout = auth._seconds_locked_out("1.2.3.4")

    assert second_lockout > first_lockout


def test_lockout_duration_is_capped():
    identifier = "1.2.3.4"
    for strike in range(10):
        for _ in range(auth._MAX_ATTEMPTS):
            auth._record_failed_attempt(identifier)
        locked_until, strikes = auth._lockouts[identifier]
        auth._lockouts[identifier] = (time.time() - 1, strikes)  # expire it for the next round
    for _ in range(auth._MAX_ATTEMPTS):
        auth._record_failed_attempt(identifier)
    assert auth._seconds_locked_out(identifier) <= auth._MAX_LOCKOUT_SECONDS


def test_format_duration_singular_and_plural():
    assert auth._format_duration(30) == "1 minute"
    assert auth._format_duration(90) == "2 minutes"
