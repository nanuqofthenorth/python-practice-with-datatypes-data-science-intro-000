"""cfo/calculations.py -- pure functions, no db/Streamlit needed."""
from __future__ import annotations

import pandas as pd
import pytest

from cfo import calculations as calc


def _accounts(rows):
    return pd.DataFrame(rows, columns=["kind", "category", "balance"])


def _debts(rows):
    return pd.DataFrame(rows, columns=["name", "balance", "apr", "min_payment"])


def _goals(rows):
    return pd.DataFrame(rows, columns=["name", "target_amount", "current_amount", "target_date"])


def test_net_worth_summary_empty():
    assert calc.net_worth_summary(pd.DataFrame(columns=["kind", "balance"])) == {
        "total_assets": 0.0, "total_liabilities": 0.0, "net_worth": 0.0,
    }


def test_net_worth_summary_computes_correctly():
    accounts = _accounts([("asset", "Cash", 1000), ("liability", "Credit Card", 300)])
    result = calc.net_worth_summary(accounts)
    assert result == {"total_assets": 1000.0, "total_liabilities": 300.0, "net_worth": 700.0}


def test_debt_payoff_avalanche_prioritizes_highest_apr():
    debts = _debts([
        ("High APR", 1000, 24.0, 25),
        ("Low APR", 1000, 5.0, 25),
    ])
    result = calc.simulate_debt_payoff(debts, extra_monthly_payment=200, strategy="avalanche")
    assert result.payoff_month_by_debt["High APR"] < result.payoff_month_by_debt["Low APR"]


def test_debt_payoff_snowball_prioritizes_smallest_balance():
    debts = _debts([
        ("Small Balance", 200, 10.0, 25),
        ("Large Balance", 2000, 10.0, 25),
    ])
    result = calc.simulate_debt_payoff(debts, extra_monthly_payment=200, strategy="snowball")
    assert result.payoff_month_by_debt["Small Balance"] < result.payoff_month_by_debt["Large Balance"]


def test_debt_payoff_empty_debts_returns_zeroed_result():
    result = calc.simulate_debt_payoff(_debts([]))
    assert result.months_to_debt_free == 0
    assert result.total_interest_paid == 0.0
    assert result.schedule.empty


def test_debt_payoff_eventually_reaches_zero():
    debts = _debts([("Card", 500, 20.0, 50)])
    result = calc.simulate_debt_payoff(debts, extra_monthly_payment=0)
    assert result.months_to_debt_free > 0
    last_month = result.schedule[result.schedule["month"] == result.schedule["month"].max()]
    assert (last_month["balance"] <= 0.01).all()


def test_goal_required_monthly_contribution_no_target_date():
    assert calc.goal_required_monthly_contribution(1000, 200, None) is None


def test_goal_required_monthly_contribution_already_funded():
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=365)).isoformat()
    assert calc.goal_required_monthly_contribution(1000, 1200, future) == 0.0


def test_health_score_no_data_yields_none():
    empty = pd.DataFrame()
    score = calc.calculate_health_score(
        net_worth={}, cash_flow=pd.DataFrame(columns=["income", "expenses", "savings_rate"]),
        budget_df=pd.DataFrame(), debts=pd.DataFrame(), goals=pd.DataFrame(), accounts=pd.DataFrame(),
    )
    assert score.score is None
    assert score.components == []


def test_health_score_no_debt_does_not_score_100_with_no_accounts_either():
    """Regression: 'no debt = 100' must not fire on a genuinely empty app
    -- it should only apply once there's at least some account data."""
    score = calc.calculate_health_score(
        net_worth={}, cash_flow=pd.DataFrame(columns=["income", "expenses", "savings_rate"]),
        budget_df=pd.DataFrame(), debts=pd.DataFrame(), goals=pd.DataFrame(),
        accounts=pd.DataFrame(columns=["kind", "category", "balance"]),
    )
    assert not any(c.name == "Debt Health" for c in score.components)


def test_health_score_high_savings_rate_scores_well():
    cash_flow = pd.DataFrame([{"month": "2026-01", "income": 5000, "expenses": 3500, "net": 1500, "savings_rate": 0.30}])
    score = calc.calculate_health_score(
        net_worth={"net_worth": 10000}, cash_flow=cash_flow, budget_df=pd.DataFrame(),
        debts=pd.DataFrame(), goals=pd.DataFrame(), accounts=pd.DataFrame(),
    )
    savings_component = next(c for c in score.components if c.name == "Savings Rate")
    assert savings_component.score == 100.0  # 30% >= the 20% target, clamped at 100


def test_generate_insights_flags_negative_savings_rate():
    cash_flow = pd.DataFrame([{"month": "2026-01", "income": 3000, "expenses": 4000, "net": -1000, "savings_rate": -0.33}])
    insights = calc.generate_insights(
        net_worth={"net_worth": 5000}, cash_flow=cash_flow, budget_df=pd.DataFrame(),
        debts=pd.DataFrame(), goals=pd.DataFrame(),
    )
    assert any(i["level"] == "critical" and "more than you earned" in i["text"] for i in insights)


def _txn(txn_date, description, category, amount, txn_type="expense"):
    return {"txn_date": txn_date, "description": description, "category": category, "amount": amount, "txn_type": txn_type}


def test_detect_recurring_transactions_finds_monthly_series():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "Netflix", "Subscriptions", 15.49),
        _txn("2026-02-04", "Netflix", "Subscriptions", 15.49),
        _txn("2026-03-02", "Netflix", "Subscriptions", 15.49),
        _txn("2026-01-15", "One-off gadget", "Shopping", 89.00),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3)
    assert len(result) == 1
    assert result.iloc[0]["description"] == "Netflix"
    assert result.iloc[0]["occurrences"] == 3


def test_detect_recurring_transactions_requires_min_occurrences():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "Gym", "Entertainment", 40.00),
        _txn("2026-02-04", "Gym", "Entertainment", 40.00),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3)
    assert result.empty


def test_detect_recurring_transactions_tolerates_small_amount_variance():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "Electric Co", "Utilities", 100.00),
        _txn("2026-02-04", "Electric Co", "Utilities", 108.00),
        _txn("2026-03-02", "Electric Co", "Utilities", 95.00),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3, amount_tolerance_pct=0.15)
    assert len(result) == 1


def test_detect_recurring_transactions_rejects_large_amount_variance():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "Random Store", "Shopping", 20.00),
        _txn("2026-02-04", "Random Store", "Shopping", 150.00),
        _txn("2026-03-02", "Random Store", "Shopping", 30.00),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3, amount_tolerance_pct=0.15)
    assert result.empty


def test_detect_recurring_transactions_skips_widely_spaced_coincidences():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "Coincidence Store", "Shopping", 50.00),
        _txn("2026-05-04", "Coincidence Store", "Shopping", 50.00),
        _txn("2026-09-02", "Coincidence Store", "Shopping", 50.00),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3)
    assert result.empty


def test_detect_recurring_transactions_ignores_income():
    transactions = pd.DataFrame([
        _txn("2026-01-01", "Paycheck", "Salary", 4000, txn_type="income"),
        _txn("2026-02-01", "Paycheck", "Salary", 4000, txn_type="income"),
        _txn("2026-03-01", "Paycheck", "Salary", 4000, txn_type="income"),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3)
    assert result.empty


def test_detect_recurring_transactions_case_and_whitespace_insensitive():
    transactions = pd.DataFrame([
        _txn("2026-01-03", "  Spotify  ", "Subscriptions", 11.99),
        _txn("2026-02-04", "spotify", "Subscriptions", 11.99),
        _txn("2026-03-02", "SPOTIFY", "Subscriptions", 11.99),
    ])
    result = calc.detect_recurring_transactions(transactions, min_occurrences=3)
    assert len(result) == 1


def test_detect_recurring_transactions_empty_input():
    result = calc.detect_recurring_transactions(pd.DataFrame(columns=["txn_date", "description", "category", "amount", "txn_type"]))
    assert result.empty


def test_generate_insights_empty_state_has_a_fallback():
    insights = calc.generate_insights(
        net_worth={}, cash_flow=pd.DataFrame(columns=["income", "expenses", "savings_rate"]),
        budget_df=pd.DataFrame(), debts=pd.DataFrame(), goals=pd.DataFrame(),
    )
    assert len(insights) == 1
    assert insights[0]["level"] == "good"
