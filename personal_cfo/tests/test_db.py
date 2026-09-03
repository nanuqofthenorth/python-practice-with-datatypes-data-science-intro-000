"""Multi-tenancy isolation, CRUD, and backup/restore for cfo/db.py."""
from __future__ import annotations

import sqlite3

import pytest


def test_cross_tenant_isolation(db, tenant):
    tenant.as_("google:AAA")
    db.add_account("A Checking", "asset", "Cash", 1000)
    account_a_id = int(db.list_accounts().iloc[0]["id"])

    tenant.as_("google:BBB")
    assert db.list_accounts().empty
    assert db.list_transactions().empty
    assert db.list_budgets().empty
    assert db.list_debts().empty
    assert db.list_goals().empty
    assert db.get_profile() is None
    assert db.list_snapshots().empty

    # Tenant B guessing tenant A's account id must not affect it.
    db.delete_account(account_a_id)
    db.update_account_balance(account_a_id, 99999)

    tenant.as_("google:AAA")
    accounts_a = db.list_accounts()
    assert len(accounts_a) == 1
    assert accounts_a.iloc[0]["balance"] == 1000


def test_add_account_returns_the_new_id(db, tenant):
    new_id = db.add_account("Checking", "asset", "Cash", 1000)
    assert isinstance(new_id, int)
    accounts = db.list_accounts()
    assert int(accounts.iloc[0]["id"]) == new_id
    assert accounts.iloc[0]["name"] == "Checking"


def test_update_account_edits_name_category_balance_and_rate(db, tenant):
    tenant.as_("local")
    db.add_account("Old Name", "liability", "Credit Card", 500, 19.99)
    account_id = int(db.list_accounts().iloc[0]["id"])

    db.update_account(account_id, "New Name", "Auto Loan", 750, 6.5)

    updated = db.list_accounts().iloc[0]
    assert updated["name"] == "New Name"
    assert updated["category"] == "Auto Loan"
    assert updated["balance"] == 750
    assert updated["interest_rate"] == 6.5


def test_update_account_cannot_touch_another_tenants_account(db, tenant):
    tenant.as_("google:AAA")
    db.add_account("A's Checking", "asset", "Cash", 1000)
    account_id = int(db.list_accounts().iloc[0]["id"])

    tenant.as_("google:BBB")
    db.update_account(account_id, "Hijacked", "Cash", 0, 0)

    tenant.as_("google:AAA")
    unchanged = db.list_accounts().iloc[0]
    assert unchanged["name"] == "A's Checking"
    assert unchanged["balance"] == 1000


def test_has_any_data_is_tenant_scoped(db, tenant):
    tenant.as_("google:AAA")
    db.add_account("Checking", "asset", "Cash", 500)
    assert db.has_any_data() is True

    tenant.as_("google:BBB")
    assert db.has_any_data() is False


def test_budget_and_snapshot_upsert_are_per_tenant(db, tenant):
    tenant.as_("google:AAA")
    db.set_budget("Groceries", 400)
    db.set_budget("Groceries", 450)  # update, not a second row
    assert len(db.list_budgets()) == 1
    assert db.list_budgets().iloc[0]["monthly_amount"] == 450

    db.record_snapshot("2026-01-01", 1000, 500)
    db.record_snapshot("2026-01-01", 1100, 500)  # same date, same tenant -> update
    assert len(db.list_snapshots()) == 1
    assert db.list_snapshots().iloc[0]["total_assets"] == 1100

    tenant.as_("google:BBB")
    db.set_budget("Groceries", 200)  # same category, different tenant -> independent row
    assert db.list_budgets().iloc[0]["monthly_amount"] == 200
    tenant.as_("google:AAA")
    assert db.list_budgets().iloc[0]["monthly_amount"] == 450


def test_backup_restore_round_trip_is_tenant_scoped(db, tenant):
    tenant.as_("google:AAA")
    db.add_account("A Checking", "asset", "Cash", 1000)
    db.save_profile("Alice", 30, "bio", None, None, {"linkedin_url": "alice"}, "Single")
    backup_a = db.backup_bytes()
    ok, reason = db.validate_backup(backup_a)
    assert ok, reason

    tenant.as_("google:BBB")
    db.add_account("Pre-existing", "asset", "Cash", 42)
    db.restore_from_bytes(backup_a)
    b_accounts = db.list_accounts()
    assert len(b_accounts) == 1
    assert b_accounts.iloc[0]["name"] == "A Checking"
    assert db.get_profile()["name"] == "Alice"

    tenant.as_("google:AAA")
    a_accounts = db.list_accounts()
    assert len(a_accounts) == 1
    assert a_accounts.iloc[0]["name"] == "A Checking", "restoring into tenant B must not affect tenant A"


def test_restore_does_not_collide_on_id_with_another_tenants_row(db, tenant):
    """Ids are one AUTOINCREMENT counter shared by every tenant sharing the
    live database -- a restore preserving the original id could collide
    with an unrelated row that already holds it."""
    tenant.as_("local")
    db.add_account("Local account taking id=1", "asset", "Cash", 111)
    assert int(db.list_accounts().iloc[0]["id"]) == 1

    tenant.as_("google:OTHER")
    db.add_account("Other tenant's own account", "asset", "Cash", 222)
    backup = db.backup_bytes()

    tenant.as_("local")
    db.restore_from_bytes(backup)  # would raise sqlite3.IntegrityError if ids collided
    assert db.list_accounts().iloc[0]["name"] == "Other tenant's own account"


_OLD_SCHEMA = """
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('asset', 'liability')), category TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0, interest_rate REAL NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
);
CREATE TABLE net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, snapshot_date TEXT NOT NULL UNIQUE,
    total_assets REAL NOT NULL, total_liabilities REAL NOT NULL, net_worth REAL NOT NULL
);
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, txn_date TEXT NOT NULL, description TEXT NOT NULL,
    category TEXT NOT NULL, txn_type TEXT NOT NULL CHECK (txn_type IN ('income', 'expense')), amount REAL NOT NULL
);
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL UNIQUE, monthly_amount REAL NOT NULL
);
CREATE TABLE debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, balance REAL NOT NULL,
    apr REAL NOT NULL, min_payment REAL NOT NULL
);
CREATE TABLE goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, target_amount REAL NOT NULL,
    current_amount REAL NOT NULL DEFAULT 0, target_date TEXT
);
CREATE TABLE profile (
    id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL DEFAULT '', age INTEGER,
    bio TEXT NOT NULL DEFAULT '', photo BLOB, photo_mime TEXT, linkedin_url TEXT, instagram_url TEXT,
    facebook_url TEXT, website_url TEXT, filing_status TEXT, updated_at TEXT NOT NULL
);
"""


def test_legacy_single_user_database_migrates_with_zero_data_loss(uninitialized_tenant):
    from cfo import db
    tenant = uninitialized_tenant
    conn = sqlite3.connect(db.DB_PATH)
    conn.executescript(_OLD_SCHEMA)
    conn.execute(
        "INSERT INTO accounts (name, kind, category, balance, interest_rate, updated_at) "
        "VALUES ('Old Checking', 'asset', 'Cash', 5000, 0, '2025-01-01')"
    )
    conn.execute("INSERT INTO profile (id, name, age, bio, updated_at) VALUES (1, 'Old User', 40, 'bio', '2025-01-01')")
    conn.commit()
    conn.close()

    db.init_db()  # the migration under test

    tenant.as_("local")
    accounts = db.list_accounts()
    assert len(accounts) == 1
    assert accounts.iloc[0]["name"] == "Old Checking"
    profile = db.get_profile()
    assert profile["name"] == "Old User"

    # A CHECK(id = 1) singleton table would reject a second tenant's
    # profile outright if the rebuild migration didn't run.
    tenant.as_("google:NEWUSER")
    db.save_profile("New User", 25, "new bio", None, None, {}, "Single")
    assert db.get_profile()["name"] == "New User"

    tenant.as_("local")
    assert db.get_profile()["name"] == "Old User", "legacy tenant's profile must be untouched"


def test_restoring_a_legacy_format_backup_does_not_lose_data(db, tenant):
    """A backup taken before multi-tenancy existed has none of the tables'
    user_id columns -- restore must still migrate it, not silently
    restore nothing."""
    import tempfile
    from pathlib import Path

    legacy_path = Path(tempfile.mkdtemp()) / "old-backup.db"
    conn = sqlite3.connect(legacy_path)
    conn.executescript(_OLD_SCHEMA)
    conn.execute(
        "INSERT INTO accounts (name, kind, category, balance, interest_rate, updated_at) "
        "VALUES ('Backed Up Checking', 'asset', 'Cash', 7777, 0, '2025-06-01')"
    )
    conn.commit()
    conn.close()
    legacy_bytes = legacy_path.read_bytes()

    ok, reason = db.validate_backup(legacy_bytes)
    assert ok, reason

    tenant.as_("local")
    db.restore_from_bytes(legacy_bytes)
    accounts = db.list_accounts()
    assert len(accounts) == 1
    assert accounts.iloc[0]["name"] == "Backed Up Checking"
