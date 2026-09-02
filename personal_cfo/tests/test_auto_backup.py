"""cfo/auto_backup.py -- opportunistic full-database disaster-recovery
backups, distinct from db.backup_bytes()'s tenant-scoped user backups."""
from __future__ import annotations

import os
import sqlite3
import time

from cfo import auto_backup


def _patch_backup_dir(monkeypatch, db):
    backup_dir = db.DB_PATH.parent / "backups"
    monkeypatch.setattr(auto_backup, "BACKUP_DIR", backup_dir)
    return backup_dir


def test_first_backup_is_created(db, tenant, monkeypatch):
    backup_dir = _patch_backup_dir(monkeypatch, db)
    db.add_account("Test", "asset", "Cash", 100)

    auto_backup.maybe_run_backup()

    backups = sorted(backup_dir.glob("cfo-*.db"))
    assert len(backups) == 1


def test_no_duplicate_backup_within_interval(db, tenant, monkeypatch):
    backup_dir = _patch_backup_dir(monkeypatch, db)
    db.add_account("Test", "asset", "Cash", 100)

    auto_backup.maybe_run_backup()
    auto_backup.maybe_run_backup()

    assert len(list(backup_dir.glob("cfo-*.db"))) == 1


def test_backup_runs_again_after_interval_elapses(db, tenant, monkeypatch):
    backup_dir = _patch_backup_dir(monkeypatch, db)
    db.add_account("Test", "asset", "Cash", 100)
    auto_backup.maybe_run_backup()

    [existing] = backup_dir.glob("cfo-*.db")
    stale_time = time.time() - auto_backup.BACKUP_INTERVAL_SECONDS - 10
    os.utime(existing, (stale_time, stale_time))

    auto_backup.maybe_run_backup()

    assert len(list(backup_dir.glob("cfo-*.db"))) == 2


def test_backup_file_contains_correct_data(db, tenant, monkeypatch):
    backup_dir = _patch_backup_dir(monkeypatch, db)
    db.add_account("Correct Data", "asset", "Cash", 100)
    auto_backup.maybe_run_backup()

    [backup_file] = backup_dir.glob("cfo-*.db")
    conn = sqlite3.connect(backup_file)
    rows = conn.execute("SELECT name FROM accounts").fetchall()
    conn.close()
    assert rows == [("Correct Data",)]


def test_rotation_keeps_only_the_last_n(db, tenant, monkeypatch):
    backup_dir = _patch_backup_dir(monkeypatch, db)
    db.add_account("Test", "asset", "Cash", 100)
    backup_dir.mkdir(parents=True, exist_ok=True)

    for i in range(auto_backup.KEEP_LAST_N + 5):
        fake = backup_dir / f"cfo-fake-{i:03d}.db"
        fake.write_bytes(b"fake")
        age = time.time() - (auto_backup.KEEP_LAST_N + 5 - i) * 3600
        os.utime(fake, (age, age))

    stale_time = time.time() - auto_backup.BACKUP_INTERVAL_SECONDS - 10
    [newest] = sorted(backup_dir.glob("cfo-*.db"))[-1:]
    os.utime(newest, (stale_time, stale_time))

    auto_backup.maybe_run_backup()

    assert len(list(backup_dir.glob("cfo-*.db"))) == auto_backup.KEEP_LAST_N


def test_no_backup_before_the_database_exists(tmp_path, monkeypatch):
    from cfo import db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "never-created.db")
    monkeypatch.setattr(auto_backup, "db", db_module)
    monkeypatch.setattr(auto_backup, "BACKUP_DIR", tmp_path / "backups")

    auto_backup.maybe_run_backup()

    assert not (tmp_path / "backups").exists()
