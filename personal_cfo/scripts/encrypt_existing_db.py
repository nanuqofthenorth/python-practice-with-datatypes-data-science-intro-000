#!/usr/bin/env python3
"""One-time migration: encrypt an existing plaintext data/cfo.db in place.

Turning on DB_ENCRYPTION_KEY is NOT enough by itself for a database that
already exists and was created without it -- SQLCipher can't open a
plaintext file once a key is set (it tries to decrypt pages that were
never encrypted and fails). Run this once, with the new key already
exported, to convert an existing plaintext database before you start the
app with DB_ENCRYPTION_KEY set. A brand-new deployment that sets
DB_ENCRYPTION_KEY from the very first run never needs this -- there's no
plaintext database yet to convert.

Usage:
    DB_ENCRYPTION_KEY="your-new-key" python3 scripts/encrypt_existing_db.py

The original plaintext file is renamed to cfo.db.pre-encryption-backup
alongside the new encrypted cfo.db, not deleted -- keep it somewhere safe
until you've confirmed the app runs correctly against the encrypted copy,
then delete it yourself.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cfo import db, dbconn  # noqa: E402 -- must follow the sys.path insert above


def main() -> int:
    key = os.environ.get("DB_ENCRYPTION_KEY")
    if not key:
        print("Set DB_ENCRYPTION_KEY to the new key before running this script.", file=sys.stderr)
        return 1

    if not db.DB_PATH.exists():
        print(f"No existing database at {db.DB_PATH} -- nothing to migrate. "
              f"Just start the app with DB_ENCRYPTION_KEY set.")
        return 0

    # Refuse to run against a database that's already encrypted -- the
    # stdlib sqlite3 driver can't open one, so this check itself proves
    # it's still plaintext.
    try:
        probe = sqlite3.connect(db.DB_PATH)
        probe.execute("SELECT name FROM sqlite_master LIMIT 1")
        probe.close()
    except sqlite3.DatabaseError:
        print(f"{db.DB_PATH} does not look like a plaintext SQLite database -- "
              f"it may already be encrypted. Nothing to do.", file=sys.stderr)
        return 1

    encrypted_path = db.DB_PATH.with_name(db.DB_PATH.name + ".encrypting")
    if encrypted_path.exists():
        encrypted_path.unlink()

    # sqlite3.Connection.backup() requires both ends to be the same
    # driver -- it can't copy directly from a plain sqlite3 connection
    # into a sqlcipher3 one. Clone the schema (verbatim, from
    # sqlite_master, not db.SCHEMA -- an old database may not match
    # today's schema exactly) and copy every table's rows by hand instead.
    src_conn = sqlite3.connect(db.DB_PATH)
    dest_conn = dbconn.connect(encrypted_path)
    try:
        schema_rows = src_conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
        ).fetchall()
        for _name, create_sql in schema_rows:
            dest_conn.execute(create_sql)

        for table_name, _create_sql in schema_rows:
            columns = [row[1] for row in src_conn.execute(f"PRAGMA table_info({table_name})")]
            cols_sql = ", ".join(columns)
            placeholders = ", ".join("?" * len(columns))
            rows = src_conn.execute(f"SELECT {cols_sql} FROM {table_name}").fetchall()
            if rows:
                dest_conn.executemany(
                    f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})", rows
                )
        dest_conn.commit()
    finally:
        dest_conn.close()
        src_conn.close()

    backup_path = db.DB_PATH.with_name(db.DB_PATH.name + ".pre-encryption-backup")
    db.DB_PATH.rename(backup_path)
    encrypted_path.rename(db.DB_PATH)

    print(f"Done. {db.DB_PATH} is now encrypted with the key from DB_ENCRYPTION_KEY.")
    print(f"The original plaintext file is kept at {backup_path} -- "
          f"verify the app works, then delete it yourself when you're confident.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
