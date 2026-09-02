"""Sample data so a new user has something to explore immediately."""
from __future__ import annotations

import random
from datetime import date, timedelta

from . import db


def seed_sample_data() -> None:
    if db.has_any_data():
        return

    db.add_account("Checking", "asset", "Cash", 4200)
    db.add_account("Savings", "asset", "Cash", 12500)
    db.add_account("Brokerage", "asset", "Investments", 18300)
    db.add_account("401(k)", "asset", "Retirement", 42750)
    db.add_account("Honda Civic", "asset", "Other Asset", 9000)
    db.add_account("Visa Card", "liability", "Credit Card", 2350, interest_rate=22.99)
    db.add_account("Student Loan", "liability", "Student Loan", 15800, interest_rate=5.5)
    db.add_account("Auto Loan", "liability", "Auto Loan", 6200, interest_rate=6.9)

    today = date.today()
    accounts = db.list_accounts()
    random.seed(7)
    for months_ago in range(6, -1, -1):
        snap_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) if months_ago == 0 else today
        snap_date = _shift_months(today, -months_ago)
        drift = 1 - 0.012 * months_ago + random.uniform(-0.01, 0.01)
        total_assets = accounts.loc[accounts["kind"] == "asset", "balance"].sum() * drift
        total_liabilities = accounts.loc[accounts["kind"] == "liability", "balance"].sum() * (1 + 0.006 * months_ago)
        db.record_snapshot(snap_date.isoformat(), round(total_assets, 2), round(total_liabilities, 2))

    income_sources = [("Acme Corp Payroll", "Salary", 4200)]
    expense_plan = [
        ("Rent", "Housing", 1450), ("Electric & Gas", "Utilities", 110),
        ("Groceries", "Groceries", 480), ("Restaurants", "Dining", 220),
        ("Gas & Rideshare", "Transportation", 140), ("Car & Renters Insurance", "Insurance", 95),
        ("Pharmacy", "Healthcare", 60), ("Credit Card Payment", "Debt Payments", 200),
        ("Streaming Subscriptions", "Subscriptions", 35), ("Movies / Concerts", "Entertainment", 90),
        ("Clothing", "Shopping", 110),
    ]

    for months_ago in range(5, -1, -1):
        month_date = _shift_months(today, -months_ago)
        for desc, cat, amt in income_sources:
            db.add_transaction(month_date.replace(day=1).isoformat(), desc, cat, "income", amt + random.uniform(-100, 150))
        for desc, cat, base_amt in expense_plan:
            jitter = random.uniform(0.85, 1.2)
            day = min(28, random.randint(1, 27))
            db.add_transaction(month_date.replace(day=day).isoformat(), desc, cat, "expense", round(base_amt * jitter, 2))

    for cat, amt in [
        ("Housing", 1450), ("Utilities", 130), ("Groceries", 500), ("Dining", 180),
        ("Transportation", 150), ("Insurance", 95), ("Healthcare", 75), ("Debt Payments", 200),
        ("Subscriptions", 40), ("Entertainment", 100), ("Shopping", 100),
    ]:
        db.set_budget(cat, amt)

    db.add_debt("Visa Card", 2350, 22.99, 75)
    db.add_debt("Student Loan", 15800, 5.5, 180)
    db.add_debt("Auto Loan", 6200, 6.9, 240)

    db.add_goal("Emergency Fund", 15000, 12500, _shift_months(today, 6).isoformat())
    db.add_goal("Vacation", 3000, 800, _shift_months(today, 8).isoformat())
    db.add_goal("New Laptop", 1800, 1800, _shift_months(today, -1).isoformat())


def _shift_months(d: date, delta_months: int) -> date:
    month_index = d.month - 1 + delta_months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, 28)
    return date(year, month, day)
