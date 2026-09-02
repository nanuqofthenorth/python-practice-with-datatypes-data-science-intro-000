"""Opportunistic, no-extra-infrastructure database backups.

This is a *different* thing from db.backup_bytes(): that one is
tenant-scoped and user-triggered (someone clicking "Download backup" on
Settings gets only their own data). This module backs up the entire live
SQLite file -- every tenant -- as a disaster-recovery safety net once the
app is hosted somewhere with persistent storage and more than one
person's data in it. Nobody downloads these; they just sit on the same
disk as the live database, for you (the person running the server) to
pull if something goes wrong.

It runs opportunistically rather than on a real schedule: checked once
per page load (cheap -- one directory listing), it actually performs a
backup only if the most recent one is more than BACKUP_INTERVAL old. That
means an app nobody opens for a week doesn't get backed up for a week --
fine as a safety net layered on top of manual backups, not a substitute
for a real cron job if you need a guarantee. Most hosts (Render, Fly,
Railway included) charge extra for a separate cron service, which this
deliberately avoids requiring.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import db
from . import dbconn

BACKUP_DIR = db.DB_PATH.parent / "backups"
BACKUP_INTERVAL_SECONDS = 24 * 60 * 60  # once a day, at most
KEEP_LAST_N = 14  # roughly two weeks of daily backups


def maybe_run_backup() -> None:
    if not db.DB_PATH.exists():
        return  # nothing written yet
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(BACKUP_DIR.glob("cfo-*.db"))
    if existing and (time.time() - existing[-1].stat().st_mtime) < BACKUP_INTERVAL_SECONDS:
        return
    _run_backup(existing)


def _run_backup(existing: list[Path]) -> None:
    dest_path = BACKUP_DIR / f"cfo-{time.strftime('%Y%m%d-%H%M%S')}.db"
    # Second-resolution names collide if two backups ever land in the same
    # wall-clock second (never in normal ~24h-apart use, but cheap to make
    # impossible rather than assume).
    suffix = 1
    while dest_path.exists():
        suffix += 1
        dest_path = BACKUP_DIR / f"cfo-{time.strftime('%Y%m%d-%H%M%S')}-{suffix}.db"
    # SQLite's own online backup API, not a raw file copy -- safe to run
    # against a database that's actively being written to. Goes through
    # dbconn so this backup is encrypted the same as the live database
    # when DB_ENCRYPTION_KEY is set -- a plaintext copy sitting next to
    # an encrypted live file would defeat the point.
    src_conn = dbconn.connect(db.DB_PATH)
    dest_conn = dbconn.connect(dest_path)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()
    stale = existing[: max(0, len(existing) - (KEEP_LAST_N - 1))]
    for old_backup in stale:
        old_backup.unlink(missing_ok=True)
