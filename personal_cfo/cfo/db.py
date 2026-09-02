"""SQLite persistence layer for the Personal CFO app.

One SQLite file holds every tenant's data, partitioned by `user_id`. Two
regimes:

- **No Google Sign-In configured** (the default): everyone who opens the
  app is the same implicit "local" tenant -- this is exactly today's
  single-user behavior, unchanged. An existing pre-multi-tenancy database
  migrates into this tenant automatically (see init_db()), with zero data
  loss and zero visible change for anyone not using OAuth.
- **Google Sign-In configured**: each signed-in Google account (keyed by
  its stable OIDC `sub`, not email -- see cfo.auth.current_google_user_id())
  is its own tenant with fully isolated data. A shared PERSONAL_CFO_PASSWORD
  does *not* provide this isolation -- it's one secret for whoever has it,
  with no way to tell people apart, so anyone unlocked only by the shared
  password lands in the "local" tenant alongside everyone else who did the
  same.

Every function below reads or writes exactly one tenant's rows. There is
deliberately no cross-tenant query anywhere in this module -- if you need
one (an admin view, say), it does not belong here without a lot more
thought.
"""
from __future__ import annotations

import os
import sqlite3  # noqa: F401 -- only for the sqlite3.Connection type hints below; connections themselves go through dbconn
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd

from . import dbconn

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cfo.db"

ASSET_CATEGORIES = ["Cash", "Investments", "Retirement", "Real Estate", "Other Asset"]
LIABILITY_CATEGORIES = ["Credit Card", "Student Loan", "Auto Loan", "Mortgage", "Other Liability"]

EXPENSE_CATEGORIES = [
    "Housing", "Utilities", "Groceries", "Dining", "Transportation",
    "Insurance", "Healthcare", "Debt Payments", "Entertainment",
    "Subscriptions", "Shopping", "Travel", "Childcare", "Other",
]
INCOME_CATEGORIES = ["Salary", "Freelance", "Investment Income", "Gifts", "Other Income"]

# A single-column UNIQUE(category)/UNIQUE(snapshot_date) would forbid two
# different tenants from both having a "Housing" budget or both snapshotting
# on the same date. Rather than a composite UNIQUE(user_id, ...) -- which
# SQLite can't retrofit onto an existing table via ALTER TABLE without a
# rebuild-and-copy migration -- "at most one per tenant" is enforced in
# Python (check-then-update-or-insert) for budgets and snapshots below, and
# the schema carries no UNIQUE constraint on those columns at all.
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('asset', 'liability')),
    category TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    interest_rate REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    snapshot_date TEXT NOT NULL,
    total_assets REAL NOT NULL,
    total_liabilities REAL NOT NULL,
    net_worth REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    txn_date TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    txn_type TEXT NOT NULL CHECK (txn_type IN ('income', 'expense')),
    amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    category TEXT NOT NULL,
    monthly_amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    balance REAL NOT NULL,
    apr REAL NOT NULL,
    min_payment REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    current_amount REAL NOT NULL DEFAULT 0,
    target_date TEXT
);

CREATE TABLE IF NOT EXISTS profile (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    age INTEGER,
    bio TEXT NOT NULL DEFAULT '',
    photo BLOB,
    photo_mime TEXT,
    linkedin_url TEXT,
    instagram_url TEXT,
    facebook_url TEXT,
    website_url TEXT,
    filing_status TEXT,
    updated_at TEXT NOT NULL
);
"""

# IRS filing status categories, not a blunt single/married binary --
# married-filing-jointly vs -separately has real, different tax
# implications, which is the whole reason this field exists.
FILING_STATUSES = [
    "Prefer not to say",
    "Single",
    "Married Filing Jointly",
    "Married Filing Separately",
    "Head of Household",
    "Qualifying Surviving Spouse",
]

# Columns added after the initial release, per table. CREATE TABLE IF NOT
# EXISTS is a no-op against a table that already exists, so an existing
# local database needs these added explicitly -- ALTER TABLE ADD COLUMN,
# skipped if the column is already there. Append future additions here
# rather than writing a new migration mechanism. Every pre-multi-tenancy
# table gets `user_id` backfilled to 'local', which is what makes an
# existing single-user database keep working unchanged: its data becomes
# tenant 'local', and current_user_id() resolves to 'local' for anyone not
# signed in via Google, so nothing about what they see changes.
_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "accounts": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "net_worth_snapshots": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "transactions": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "budgets": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "debts": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "goals": {"user_id": "TEXT NOT NULL DEFAULT 'local'"},
    "profile": {
        "linkedin_url": "TEXT", "instagram_url": "TEXT", "facebook_url": "TEXT",
        "website_url": "TEXT", "filing_status": "TEXT",
        "user_id": "TEXT NOT NULL DEFAULT 'local'",
    },
}


def current_user_id() -> str:
    """The tenant key every query in this module is scoped by. Google
    Sign-In (when configured and the viewer is signed in) gets a real,
    stable per-account id; everyone else shares the single 'local' tenant,
    which is exactly how this app behaved before multi-tenancy existed."""
    try:
        from . import auth
        return auth.current_google_user_id() or "local"
    except Exception:  # noqa: BLE001 -- auth module unavailable/misconfigured; fail to the safe single-tenant default
        return "local"


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = dbconn.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _rebuild_legacy_profile_table(conn: sqlite3.Connection) -> None:
    """The pre-multi-tenancy `profile` table was a true singleton --
    `id INTEGER PRIMARY KEY CHECK (id = 1)` -- which `ALTER TABLE ADD
    COLUMN` can't remove. Left in place, that CHECK constraint would
    reject outright any second tenant's profile row (both would need
    id = 1, and id is also the table's primary key). Detected by the
    presence of that legacy `id` column; rebuilds into the current schema
    (`user_id TEXT PRIMARY KEY`, no row-count limit), preserving every
    other column's data. A no-op against a database already on the
    current schema, or one with no profile table yet."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "profile" not in tables:
        return
    existing_columns = [row[1] for row in conn.execute("PRAGMA table_info(profile)")]
    if "id" not in existing_columns:
        return
    conn.execute("ALTER TABLE profile RENAME TO profile_legacy")
    conn.executescript(SCHEMA)  # recreates a fresh, id-less `profile` table
    copy_columns = [c for c in existing_columns if c != "id"]
    # This table was a true singleton pre-multi-tenancy -- at most one row,
    # unambiguously the 'local' tenant, whether or not a partial user_id
    # migration already ran on it.
    if "user_id" in copy_columns:
        copy_columns.remove("user_id")
    cols_sql = ", ".join(copy_columns)
    conn.execute(
        f"INSERT INTO profile (user_id, {cols_sql}) SELECT 'local', {cols_sql} FROM profile_legacy"
    )
    conn.execute("DROP TABLE profile_legacy")


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """Add any column in _COLUMN_MIGRATIONS that's missing from an
    already-existing table -- shared by init_db() (the live database) and
    restore_from_bytes() (an uploaded backup file, which may predate a
    later migration, including user_id itself)."""
    for table, columns in _COLUMN_MIGRATIONS.items():
        existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, col_type in columns.items():
            if column not in existing_columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db() -> None:
    with get_conn() as conn:
        _rebuild_legacy_profile_table(conn)
        conn.executescript(SCHEMA)
        _migrate_columns(conn)
        # profile predates multi-tenancy with `id INTEGER PRIMARY KEY CHECK
        # (id = 1)` as a true singleton; a migrated database still has that
        # old column sitting alongside the new user_id one. Harmless -- we
        # never reference `id` below -- but worth naming so it isn't a
        # mystery column to a future reader.


def _read(query: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


# ---------------------------------------------------------------- accounts
def list_accounts() -> pd.DataFrame:
    return _read("SELECT * FROM accounts WHERE user_id = ? ORDER BY kind, category, name", (current_user_id(),))


def add_account(name: str, kind: str, category: str, balance: float, interest_rate: float = 0.0) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (user_id, name, kind, category, balance, interest_rate, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (current_user_id(), name, kind, category, balance, interest_rate, date.today().isoformat()),
        )


def update_account_balance(account_id: int, balance: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (balance, date.today().isoformat(), account_id, current_user_id()),
        )


def delete_account(account_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM accounts WHERE id = ? AND user_id = ?", (account_id, current_user_id()))


def get_account(account_id: int) -> pd.Series | None:
    df = _read("SELECT * FROM accounts WHERE id = ? AND user_id = ?", (account_id, current_user_id()))
    return None if df.empty else df.iloc[0]


# --------------------------------------------------------- net worth history
def list_snapshots() -> pd.DataFrame:
    return _read(
        "SELECT * FROM net_worth_snapshots WHERE user_id = ? ORDER BY snapshot_date", (current_user_id(),)
    )


def record_snapshot(snapshot_date: str, total_assets: float, total_liabilities: float) -> None:
    net_worth = total_assets - total_liabilities
    user_id = current_user_id()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM net_worth_snapshots WHERE user_id = ? AND snapshot_date = ?",
            (user_id, snapshot_date),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE net_worth_snapshots SET total_assets = ?, total_liabilities = ?, net_worth = ? "
                "WHERE id = ?",
                (total_assets, total_liabilities, net_worth, existing[0]),
            )
        else:
            conn.execute(
                "INSERT INTO net_worth_snapshots "
                "(user_id, snapshot_date, total_assets, total_liabilities, net_worth) VALUES (?, ?, ?, ?, ?)",
                (user_id, snapshot_date, total_assets, total_liabilities, net_worth),
            )


# ------------------------------------------------------------- transactions
def list_transactions() -> pd.DataFrame:
    return _read(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY txn_date DESC, id DESC", (current_user_id(),)
    )


def add_transaction(txn_date: str, description: str, category: str, txn_type: str, amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (user_id, txn_date, description, category, txn_type, amount) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (current_user_id(), txn_date, description, category, txn_type, abs(amount)),
        )


def add_transactions_bulk(df: pd.DataFrame) -> int:
    """Insert many transactions at once. df must have columns:
    txn_date, description, category, txn_type, amount."""
    required = {"txn_date", "description", "category", "txn_type", "amount"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    stamped = df[["txn_date", "description", "category", "txn_type", "amount"]].copy()
    stamped.insert(0, "user_id", current_user_id())
    with get_conn() as conn:
        stamped.to_sql("transactions", conn, if_exists="append", index=False)
    return len(df)


def delete_transaction(txn_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (txn_id, current_user_id()))


def transaction_fingerprints() -> set[tuple[str, str, float]]:
    """(date, description, amount) tuples already in the ledger, used to
    flag likely-duplicate rows when importing a statement that overlaps
    a previous import."""
    df = _read("SELECT txn_date, description, amount FROM transactions WHERE user_id = ?", (current_user_id(),))
    if df.empty:
        return set()
    return {(r.txn_date, r.description.strip().lower(), round(r.amount, 2)) for r in df.itertuples()}


# ------------------------------------------------------------------ budgets
def list_budgets() -> pd.DataFrame:
    return _read("SELECT * FROM budgets WHERE user_id = ? ORDER BY category", (current_user_id(),))


def set_budget(category: str, monthly_amount: float) -> None:
    user_id = current_user_id()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM budgets WHERE user_id = ? AND category = ?", (user_id, category)
        ).fetchone()
        if existing:
            conn.execute("UPDATE budgets SET monthly_amount = ? WHERE id = ?", (monthly_amount, existing[0]))
        else:
            conn.execute(
                "INSERT INTO budgets (user_id, category, monthly_amount) VALUES (?, ?, ?)",
                (user_id, category, monthly_amount),
            )


def delete_budget(budget_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM budgets WHERE id = ? AND user_id = ?", (budget_id, current_user_id()))


# -------------------------------------------------------------------- debts
def list_debts() -> pd.DataFrame:
    return _read("SELECT * FROM debts WHERE user_id = ? ORDER BY balance DESC", (current_user_id(),))


def add_debt(name: str, balance: float, apr: float, min_payment: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO debts (user_id, name, balance, apr, min_payment) VALUES (?, ?, ?, ?, ?)",
            (current_user_id(), name, balance, apr, min_payment),
        )


def delete_debt(debt_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM debts WHERE id = ? AND user_id = ?", (debt_id, current_user_id()))


# -------------------------------------------------------------------- goals
def list_goals() -> pd.DataFrame:
    return _read(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY target_date IS NULL, target_date", (current_user_id(),)
    )


def add_goal(name: str, target_amount: float, current_amount: float, target_date: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO goals (user_id, name, target_amount, current_amount, target_date) VALUES (?, ?, ?, ?, ?)",
            (current_user_id(), name, target_amount, current_amount, target_date),
        )


def update_goal_progress(goal_id: int, current_amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE goals SET current_amount = ? WHERE id = ? AND user_id = ?",
            (current_amount, goal_id, current_user_id()),
        )


def delete_goal(goal_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM goals WHERE id = ? AND user_id = ?", (goal_id, current_user_id()))


# ------------------------------------------------------------------ profile
PROFILE_SOCIAL_FIELDS = ["linkedin_url", "instagram_url", "facebook_url", "website_url"]


def get_profile() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name, age, bio, photo, photo_mime, "
            "linkedin_url, instagram_url, facebook_url, website_url, filing_status, updated_at "
            "FROM profile WHERE user_id = ?",
            (current_user_id(),),
        ).fetchone()
    if row is None:
        return None
    return {
        "name": row[0], "age": row[1], "bio": row[2],
        "photo": row[3], "photo_mime": row[4],
        "linkedin_url": row[5], "instagram_url": row[6],
        "facebook_url": row[7], "website_url": row[8],
        "filing_status": row[9], "updated_at": row[10],
    }


def save_profile(
    name: str, age: int | None, bio: str, photo: bytes | None, photo_mime: str | None,
    social_links: dict[str, str] | None = None, filing_status: str | None = None,
) -> None:
    social_links = social_links or {}
    user_id = current_user_id()
    with get_conn() as conn:
        existing = conn.execute("SELECT user_id FROM profile WHERE user_id = ?", (user_id,)).fetchone()
        values = (
            name, age, bio, photo, photo_mime,
            social_links.get("linkedin_url") or None,
            social_links.get("instagram_url") or None,
            social_links.get("facebook_url") or None,
            social_links.get("website_url") or None,
            filing_status or None,
            date.today().isoformat(),
        )
        if existing:
            conn.execute(
                "UPDATE profile SET name = ?, age = ?, bio = ?, photo = ?, photo_mime = ?, "
                "linkedin_url = ?, instagram_url = ?, facebook_url = ?, website_url = ?, "
                "filing_status = ?, updated_at = ? WHERE user_id = ?",
                (*values, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO profile (name, age, bio, photo, photo_mime, linkedin_url, instagram_url, "
                "facebook_url, website_url, filing_status, updated_at, user_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*values, user_id),
            )


def clear_profile_photo() -> None:
    with get_conn() as conn:
        conn.execute("UPDATE profile SET photo = NULL, photo_mime = NULL WHERE user_id = ?", (current_user_id(),))


def has_any_data() -> bool:
    user_id = current_user_id()
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM accounts WHERE user_id = ?) + "
            "(SELECT COUNT(*) FROM transactions WHERE user_id = ?) + "
            "(SELECT COUNT(*) FROM debts WHERE user_id = ?) + "
            "(SELECT COUNT(*) FROM goals WHERE user_id = ?)",
            (user_id, user_id, user_id, user_id),
        )
        return cur.fetchone()[0] > 0


# --------------------------------------------------------- backup / restore
EXPECTED_TABLES = {"accounts", "transactions", "budgets", "debts", "goals", "net_worth_snapshots", "profile"}
_TENANT_TABLES = ["accounts", "net_worth_snapshots", "transactions", "budgets", "debts", "goals", "profile"]


def backup_bytes() -> bytes:
    """A consistent point-in-time snapshot of the *current tenant's data
    only* -- built via a filtered copy, not a raw copy of the live file,
    which would hand over every other tenant's data too on a multi-tenant
    (Google Sign-In) deployment. Encrypted the same as the live database
    when DB_ENCRYPTION_KEY is set -- a downloaded backup is exactly as
    sensitive as the live file, so it gets the same protection."""
    user_id = current_user_id()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "backup.db"
        with dbconn.connect(tmp_path) as out_conn:
            out_conn.executescript(SCHEMA)
            with get_conn() as src_conn:
                for table in _TENANT_TABLES:
                    # Intersect with the fresh out_conn schema so a legacy
                    # column still hanging around on the live db (e.g.
                    # profile's pre-multi-tenancy `id` primary key, kept by
                    # ALTER TABLE migrations rather than dropped) doesn't
                    # break the insert into a table that never had it.
                    src_columns = [row[1] for row in src_conn.execute(f"PRAGMA table_info({table})")]
                    dest_columns = [row[1] for row in out_conn.execute(f"PRAGMA table_info({table})")]
                    columns = [c for c in src_columns if c in dest_columns]
                    cols_sql = ", ".join(columns)
                    rows = src_conn.execute(f"SELECT {cols_sql} FROM {table} WHERE user_id = ?", (user_id,))
                    placeholders = ", ".join("?" * len(columns))
                    out_conn.executemany(f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})", rows)
        return tmp_path.read_bytes()


def validate_backup(file_bytes: bytes) -> tuple[bool, str]:
    """Sanity-check an uploaded file before it's allowed anywhere near the
    live database: must be a valid, uncorrupted SQLite database that looks
    like a Personal CFO backup specifically. If DB_ENCRYPTION_KEY is set,
    this expects the uploaded file to be encrypted with that same key
    (it's opened with dbconn.connect(), same as everything else) -- an
    unencrypted file, or one encrypted with a different key, fails here
    with "doesn't look like a valid SQLite database" rather than silently
    reading nothing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "candidate.db"
        tmp_path.write_bytes(file_bytes)
        try:
            conn = dbconn.connect(tmp_path)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                conn.close()
                return False, f"This file failed SQLite's integrity check ({integrity})."
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            conn.close()
        except dbconn.DatabaseError as exc:
            return False, f"This doesn't look like a valid SQLite database ({exc})."
    missing = EXPECTED_TABLES - tables
    if missing:
        return False, f"Missing expected tables ({sorted(missing)}) -- this doesn't look like a Personal CFO backup."
    return True, ""


def restore_from_bytes(file_bytes: bytes) -> None:
    """Caller must call validate_backup() first and only proceed on
    success. Replaces *only the current tenant's rows* with the backup's
    contents -- every other tenant sharing this database is untouched.
    (Single-tenant / no-Google-Sign-In deployments have exactly one
    tenant, 'local', so this is a full restore in that case, matching the
    original single-user behavior.)"""
    user_id = current_user_id()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "incoming.db"
        tmp_path.write_bytes(file_bytes)
        src_conn = dbconn.connect(tmp_path)
        # The uploaded file may predate a later migration -- including
        # user_id itself, for a backup taken before multi-tenancy existed.
        # Bring it up to the current schema first so every table is
        # guaranteed a user_id column (backfilled to 'local'), otherwise a
        # pre-multi-tenancy backup would silently restore nothing.
        _rebuild_legacy_profile_table(src_conn)
        src_conn.executescript(SCHEMA)
        _migrate_columns(src_conn)
        src_conn.commit()
        with get_conn() as conn:
            for table in _TENANT_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                dest_columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
                src_columns = [row[1] for row in src_conn.execute(f"PRAGMA table_info({table})")]
                # Only columns both databases actually have -- a legacy `id`
                # column on one side but not the other (the pre-multi-tenancy
                # `profile` table's old singleton primary key) shouldn't
                # break the insert. `id` itself is always dropped even when
                # both sides have it: it's a single AUTOINCREMENT counter
                # shared by every tenant in the live database, so an id from
                # the backup file can easily collide with an unrelated row
                # (any tenant's) that already holds it -- let SQLite assign
                # a fresh one instead, exactly as a brand-new INSERT would.
                columns = [c for c in src_columns if c in dest_columns and c != "id"]
                cols_sql = ", ".join(columns)
                user_id_idx = columns.index("user_id")
                rows = src_conn.execute(f"SELECT {cols_sql} FROM {table}").fetchall()
                placeholders = ", ".join("?" * len(columns))
                restamped = []
                for row in rows:
                    row = list(row)
                    row[user_id_idx] = user_id
                    restamped.append(tuple(row))
                if restamped:
                    conn.executemany(f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders})", restamped)
        src_conn.close()
