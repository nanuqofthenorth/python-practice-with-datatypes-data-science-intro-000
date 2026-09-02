"""SQLite persistence layer for the Personal CFO app.

Every user's data lives in a single local SQLite file. There is no
multi-tenancy or auth here by design -- this is a single-player,
run-it-yourself app.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cfo.db"

ASSET_CATEGORIES = ["Cash", "Investments", "Retirement", "Real Estate", "Other Asset"]
LIABILITY_CATEGORIES = ["Credit Card", "Student Loan", "Auto Loan", "Mortgage", "Other Liability"]

EXPENSE_CATEGORIES = [
    "Housing", "Utilities", "Groceries", "Dining", "Transportation",
    "Insurance", "Healthcare", "Debt Payments", "Entertainment",
    "Subscriptions", "Shopping", "Travel", "Childcare", "Other",
]
INCOME_CATEGORIES = ["Salary", "Freelance", "Investment Income", "Gifts", "Other Income"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('asset', 'liability')),
    category TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0,
    interest_rate REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_assets REAL NOT NULL,
    total_liabilities REAL NOT NULL,
    net_worth REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_date TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    txn_type TEXT NOT NULL CHECK (txn_type IN ('income', 'expense')),
    amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL UNIQUE,
    monthly_amount REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    balance REAL NOT NULL,
    apr REAL NOT NULL,
    min_payment REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount REAL NOT NULL,
    current_amount REAL NOT NULL DEFAULT 0,
    target_date TEXT
);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _read(query: str, params: tuple = ()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(query, conn, params=params)


# ---------------------------------------------------------------- accounts
def list_accounts() -> pd.DataFrame:
    return _read("SELECT * FROM accounts ORDER BY kind, category, name")


def add_account(name: str, kind: str, category: str, balance: float, interest_rate: float = 0.0) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (name, kind, category, balance, interest_rate, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, kind, category, balance, interest_rate, date.today().isoformat()),
        )


def update_account_balance(account_id: int, balance: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET balance = ?, updated_at = ? WHERE id = ?",
            (balance, date.today().isoformat(), account_id),
        )


def delete_account(account_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


def get_account(account_id: int) -> pd.Series | None:
    df = _read("SELECT * FROM accounts WHERE id = ?", (account_id,))
    return None if df.empty else df.iloc[0]


# --------------------------------------------------------- net worth history
def list_snapshots() -> pd.DataFrame:
    return _read("SELECT * FROM net_worth_snapshots ORDER BY snapshot_date")


def record_snapshot(snapshot_date: str, total_assets: float, total_liabilities: float) -> None:
    net_worth = total_assets - total_liabilities
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO net_worth_snapshots (snapshot_date, total_assets, total_liabilities, net_worth) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(snapshot_date) DO UPDATE SET "
            "total_assets = excluded.total_assets, "
            "total_liabilities = excluded.total_liabilities, "
            "net_worth = excluded.net_worth",
            (snapshot_date, total_assets, total_liabilities, net_worth),
        )


# ------------------------------------------------------------- transactions
def list_transactions() -> pd.DataFrame:
    return _read("SELECT * FROM transactions ORDER BY txn_date DESC, id DESC")


def add_transaction(txn_date: str, description: str, category: str, txn_type: str, amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (txn_date, description, category, txn_type, amount) "
            "VALUES (?, ?, ?, ?, ?)",
            (txn_date, description, category, txn_type, abs(amount)),
        )


def add_transactions_bulk(df: pd.DataFrame) -> int:
    """Insert many transactions at once. df must have columns:
    txn_date, description, category, txn_type, amount."""
    required = {"txn_date", "description", "category", "txn_type", "amount"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    with get_conn() as conn:
        df[["txn_date", "description", "category", "txn_type", "amount"]].to_sql(
            "transactions", conn, if_exists="append", index=False
        )
    return len(df)


def delete_transaction(txn_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))


def transaction_fingerprints() -> set[tuple[str, str, float]]:
    """(date, description, amount) tuples already in the ledger, used to
    flag likely-duplicate rows when importing a statement that overlaps
    a previous import."""
    df = _read("SELECT txn_date, description, amount FROM transactions")
    if df.empty:
        return set()
    return {(r.txn_date, r.description.strip().lower(), round(r.amount, 2)) for r in df.itertuples()}


# ------------------------------------------------------------------ budgets
def list_budgets() -> pd.DataFrame:
    return _read("SELECT * FROM budgets ORDER BY category")


def set_budget(category: str, monthly_amount: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO budgets (category, monthly_amount) VALUES (?, ?) "
            "ON CONFLICT(category) DO UPDATE SET monthly_amount = excluded.monthly_amount",
            (category, monthly_amount),
        )


def delete_budget(budget_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))


# -------------------------------------------------------------------- debts
def list_debts() -> pd.DataFrame:
    return _read("SELECT * FROM debts ORDER BY balance DESC")


def add_debt(name: str, balance: float, apr: float, min_payment: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO debts (name, balance, apr, min_payment) VALUES (?, ?, ?, ?)",
            (name, balance, apr, min_payment),
        )


def delete_debt(debt_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM debts WHERE id = ?", (debt_id,))


# -------------------------------------------------------------------- goals
def list_goals() -> pd.DataFrame:
    return _read("SELECT * FROM goals ORDER BY target_date IS NULL, target_date")


def add_goal(name: str, target_amount: float, current_amount: float, target_date: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO goals (name, target_amount, current_amount, target_date) VALUES (?, ?, ?, ?)",
            (name, target_amount, current_amount, target_date),
        )


def update_goal_progress(goal_id: int, current_amount: float) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE goals SET current_amount = ? WHERE id = ?", (current_amount, goal_id))


def delete_goal(goal_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))


def has_any_data() -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM accounts) + "
            "(SELECT COUNT(*) FROM transactions) + "
            "(SELECT COUNT(*) FROM debts) + "
            "(SELECT COUNT(*) FROM goals)"
        )
        return cur.fetchone()[0] > 0
