"""scripts/encrypt_existing_db.py -- one-time plaintext-to-encrypted
migration for a database that already existed before DB_ENCRYPTION_KEY
was turned on."""
from __future__ import annotations

import subprocess
import sys
import sqlite3
import textwrap
from pathlib import Path

CFO_DIR = Path(__file__).resolve().parent.parent


def _run_script(db_path: Path, env: dict) -> subprocess.CompletedProcess:
    code = f"""
        import sys
        sys.path.insert(0, {str(CFO_DIR)!r})
        from pathlib import Path
        from cfo import db
        db.DB_PATH = Path({str(db_path)!r})
        import scripts.encrypt_existing_db as script
        script.db = db
        raise SystemExit(script.main())
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=CFO_DIR, capture_output=True, text=True, env=env,
    )


def test_migrates_plaintext_db_to_encrypted(tmp_path, base_env):
    db_path = tmp_path / "cfo.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, user_id TEXT, name TEXT, balance REAL)")
    conn.execute("INSERT INTO accounts (user_id, name, balance) VALUES ('local', 'Checking', 1234.5)")
    conn.commit()
    conn.close()

    env = {**base_env, "DB_ENCRYPTION_KEY": "new-key"}
    result = _run_script(db_path, env)
    assert result.returncode == 0, result.stderr + result.stdout

    backup_path = db_path.with_name(db_path.name + ".pre-encryption-backup")
    assert backup_path.exists(), "original plaintext file must be kept, not deleted"

    raw = db_path.read_bytes()
    assert b"Checking" not in raw
    assert raw[:16] != b"SQLite format 3\x00"

    read_result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(CFO_DIR)!r})
            from pathlib import Path
            from cfo import dbconn
            conn = dbconn.connect(Path({str(db_path)!r}))
            row = conn.execute("SELECT name, balance FROM accounts").fetchone()
            assert row == ("Checking", 1234.5), row
            print("OK")
        """)],
        cwd=CFO_DIR, capture_output=True, text=True, env=env,
    )
    assert read_result.returncode == 0, read_result.stderr
    assert "OK" in read_result.stdout

    # The pre-migration backup is untouched plaintext.
    backup_conn = sqlite3.connect(backup_path)
    assert backup_conn.execute("SELECT name FROM accounts").fetchall() == [("Checking",)]
    backup_conn.close()


def test_refuses_to_run_without_a_key(tmp_path, base_env):
    db_path = tmp_path / "cfo.db"
    sqlite3.connect(db_path).close()
    result = _run_script(db_path, base_env)
    assert result.returncode != 0


def test_no_op_when_no_database_exists_yet(tmp_path, base_env):
    db_path = tmp_path / "does-not-exist.db"
    env = {**base_env, "DB_ENCRYPTION_KEY": "new-key"}
    result = _run_script(db_path, env)
    assert result.returncode == 0
    assert not db_path.exists()
