"""cfo/dbconn.py -- optional encryption at rest via SQLCipher.

Runs in a subprocess per test (rather than monkeypatching os.environ and
reloading the module in-process) because dbconn picks its driver at
import time based on DB_ENCRYPTION_KEY -- a subprocess is the only way to
get a truly clean import for each key value without cross-test
contamination of the sqlite3/sqlcipher3 module choice.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

CFO_DIR = Path(__file__).resolve().parent.parent


def _run(code: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=CFO_DIR, capture_output=True, text=True, env=env,
    )


def test_unset_key_uses_plain_sqlite3(tmp_path, monkeypatch_env_without_key):
    result = _run(
        """
        from cfo import dbconn
        assert not dbconn.is_encryption_enabled()
        import sqlite3
        conn = dbconn.connect("%s")
        assert isinstance(conn, sqlite3.Connection)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()
        print("OK")
        """ % (tmp_path / "plain.db"),
        env=monkeypatch_env_without_key,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_set_key_encrypts_and_round_trips(tmp_path, base_env):
    pytest.importorskip("sqlcipher3", reason="optional dependency -- see requirements-encryption.txt")
    db_path = tmp_path / "enc.db"
    env = {**base_env, "DB_ENCRYPTION_KEY": "test-passphrase"}

    write_result = _run(
        """
        from cfo import dbconn
        assert dbconn.is_encryption_enabled()
        conn = dbconn.connect("%s")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO t (val) VALUES ('secret-value')")
        conn.commit()
        conn.close()
        print("WROTE")
        """ % db_path,
        env=env,
    )
    assert write_result.returncode == 0, write_result.stderr
    assert "WROTE" in write_result.stdout

    raw_bytes = db_path.read_bytes()
    assert b"secret-value" not in raw_bytes, "data must not be readable in the raw file bytes"
    assert raw_bytes[:16] != b"SQLite format 3\x00", "file must not have the plain SQLite header"

    read_result = _run(
        """
        from cfo import dbconn
        conn = dbconn.connect("%s")
        row = conn.execute("SELECT val FROM t").fetchone()
        assert row == ("secret-value",), row
        conn.close()
        print("READ-OK")
        """ % db_path,
        env=env,
    )
    assert read_result.returncode == 0, read_result.stderr
    assert "READ-OK" in read_result.stdout


def test_wrong_key_cannot_read_encrypted_db(tmp_path, base_env):
    pytest.importorskip("sqlcipher3", reason="optional dependency -- see requirements-encryption.txt")
    db_path = tmp_path / "enc2.db"
    write_env = {**base_env, "DB_ENCRYPTION_KEY": "right-key"}
    _run(
        """
        from cfo import dbconn
        conn = dbconn.connect("%s")
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        """ % db_path,
        env=write_env,
    )

    wrong_env = {**base_env, "DB_ENCRYPTION_KEY": "wrong-key"}
    result = _run(
        """
        from cfo import dbconn
        conn = dbconn.connect("%s")
        try:
            conn.execute("SELECT * FROM sqlite_master").fetchall()
            print("READ-SUCCEEDED-BAD")
        except dbconn.DatabaseError:
            print("CORRECTLY-REJECTED")
        """ % db_path,
        env=wrong_env,
    )
    assert "CORRECTLY-REJECTED" in result.stdout, result.stdout + result.stderr


def test_key_with_special_characters_is_handled_safely(tmp_path, base_env):
    """The key is interpolated into a PRAGMA statement (PRAGMA doesn't
    support bound parameters) -- must not break on a key containing a
    single quote."""
    pytest.importorskip("sqlcipher3", reason="optional dependency -- see requirements-encryption.txt")
    db_path = tmp_path / "enc3.db"
    tricky_key = "it's-a-tricky-key-with-'quotes'"
    env = {**base_env, "DB_ENCRYPTION_KEY": tricky_key}

    result = _run(
        """
        from cfo import dbconn
        conn = dbconn.connect("%s")
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        conn2 = dbconn.connect("%s")
        assert conn2.execute("SELECT * FROM t").fetchall() == [(1,)]
        print("OK")
        """ % (db_path, db_path),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
