"""SQLite connection helper: encryption at rest, opt-in and off by default.

Set the DB_ENCRYPTION_KEY environment variable and every connection this
app opens (the live database, backups, restores) transparently switches
from the stdlib sqlite3 driver to SQLCipher (via the sqlcipher3 package),
which encrypts the database file page-by-page -- the file on disk is
unreadable without the key, not just access-controlled. Leave it unset
and nothing changes: same stdlib sqlite3 driver this app always used.

This is the standard, correct way to do this. Application-level
encryption of the whole file doesn't work here -- SQLite needs true
random-access reads and writes into the file as it runs, which a
transparently-encrypted-blob approach can't support without effectively
reimplementing what SQLCipher already does at the page level.

Why opt-in rather than always-on: it's a real operational tradeoff, not a
strict improvement. Lose the key and the data is unrecoverable -- by
design, since anything else would be a backdoor -- so turning this on
also means being disciplined about storing DB_ENCRYPTION_KEY somewhere
durable (your host's secret manager, not a note to self). Matches this
app's pattern for every other optional feature: password protection,
Google Sign-In, and the AI Advisor are all off until you opt in.
"""
from __future__ import annotations

import os
from pathlib import Path

_ENCRYPTION_KEY = os.environ.get("DB_ENCRYPTION_KEY") or None

if _ENCRYPTION_KEY:
    try:
        from sqlcipher3 import dbapi2 as _driver
    except ImportError as exc:
        raise ImportError(
            "DB_ENCRYPTION_KEY is set, but the sqlcipher3 package isn't installed. "
            "Install it with: pip3 install -r requirements-encryption.txt "
            "(it's not part of the base requirements.txt since its wheels aren't "
            "available for every platform). If you don't actually want encryption "
            "at rest, unset DB_ENCRYPTION_KEY instead."
        ) from exc
else:
    import sqlite3 as _driver

Error = _driver.Error
DatabaseError = _driver.DatabaseError


def is_encryption_enabled() -> bool:
    return _ENCRYPTION_KEY is not None


def connect(path: str | Path):
    """Drop-in replacement for sqlite3.connect() -- returns a connection
    on the stdlib driver, or on SQLCipher with the key already applied,
    depending on whether DB_ENCRYPTION_KEY is set. Every direct
    sqlite3.connect() call in this app (db.py, auto_backup.py) should go
    through this instead."""
    conn = _driver.connect(path)
    if _ENCRYPTION_KEY:
        # PRAGMA doesn't support bound parameters (`?`) -- the key has to
        # be interpolated into the statement text. It comes from an
        # environment variable the deploying operator sets themselves,
        # not remote input, but it's escaped like any embedded string
        # regardless.
        escaped_key = _ENCRYPTION_KEY.replace("'", "''")
        conn.execute(f"PRAGMA key = '{escaped_key}'")
    return conn
