"""cfo/tax.py -- federal tax estimate math.

Uses a small, hand-verifiable synthetic bracket table for the marginal-tax
algorithm tests, decoupled from whether the real IRS figures baked into
FEDERAL_BRACKETS are precisely accurate -- that's a fact about the world
to verify against irs.gov, not something a unit test can assert. A couple
of tests below do exercise the real module-level table, but only to check
internal consistency (e.g. brackets are ascending), not dollar amounts.
"""
from __future__ import annotations

import pandas as pd
import pytest

from cfo import tax

# A tiny synthetic table: 10% up to 1,000; 20% up to 3,000; 30% above.
_TEST_BRACKETS = {"single": [(0.10, 1_000), (0.20, 3_000), (0.30, float("inf"))]}
_TEST_DEDUCTIONS = {"single": 500}


def _estimate(income, filing_status="Single"):
    return tax.estimate_federal_tax(income, filing_status, brackets=_TEST_BRACKETS, standard_deductions=_TEST_DEDUCTIONS)


def test_zero_or_negative_income_returns_none():
    assert _estimate(0) is None
    assert _estimate(-100) is None


def test_none_filing_status_returns_none():
    assert tax.estimate_federal_tax(50_000, None) is None


def test_unmapped_filing_status_returns_none():
    assert tax.estimate_federal_tax(50_000, "Prefer not to say") is None


def test_income_entirely_within_first_bracket():
    # income 1,000 -> taxable 500 (after 500 deduction) -> all in the 10% bracket
    result = _estimate(1_000)
    assert result.taxable_income == 500
    assert result.estimated_tax == pytest.approx(50.0)
    assert result.marginal_rate == 0.10


def test_income_spanning_two_brackets():
    # income 2,500 -> taxable 2,000 -> 1,000*10% + 1,000*20% = 100 + 200 = 300
    result = _estimate(2_500)
    assert result.taxable_income == 2_000
    assert result.estimated_tax == pytest.approx(300.0)
    assert result.marginal_rate == 0.20


def test_income_spanning_all_three_brackets():
    # income 4_500 -> taxable 4_000 -> 1,000*10% + 2,000*20% + 1,000*30%
    # = 100 + 400 + 300 = 800
    result = _estimate(4_500)
    assert result.taxable_income == 4_000
    assert result.estimated_tax == pytest.approx(800.0)
    assert result.marginal_rate == 0.30


def test_effective_rate_is_of_gross_income_not_taxable_income():
    result = _estimate(2_500)
    assert result.effective_rate == pytest.approx(300.0 / 2_500, abs=0.0005)


def test_income_below_standard_deduction_owes_nothing():
    result = _estimate(200)  # below the 500 deduction
    assert result.taxable_income == 0
    assert result.estimated_tax == 0.0


def test_real_bracket_table_is_internally_consistent():
    """Not a check of dollar-accuracy against the IRS (a unit test can't
    verify that) -- just that whatever numbers are configured don't
    contain an obvious transcription bug: ascending, positive, and every
    filing status ends in the top 37% bracket at infinity."""
    for status, brackets in tax.FEDERAL_BRACKETS.items():
        upper_bounds = [b[1] for b in brackets]
        assert upper_bounds == sorted(upper_bounds), f"{status} brackets must be ascending"
        assert brackets[-1][1] == float("inf")
        assert brackets[-1][0] == 0.37
        rates = [b[0] for b in brackets]
        assert rates == sorted(rates), f"{status} rates must be ascending"
        assert status in tax.STANDARD_DEDUCTION


def test_qualifying_surviving_spouse_uses_mfj_brackets():
    income = 90_000
    qss = tax.estimate_federal_tax(income, "Qualifying Surviving Spouse")
    mfj = tax.estimate_federal_tax(income, "Married Filing Jointly")
    assert qss.estimated_tax == mfj.estimated_tax
    assert qss.standard_deduction == mfj.standard_deduction


def _income_txn(month_date, amount):
    return {"txn_date": month_date, "description": "Paycheck", "category": "Salary", "txn_type": "income", "amount": amount}


def test_estimate_annual_income_averages_and_annualizes():
    transactions = pd.DataFrame([
        _income_txn("2026-01-15", 4000),
        _income_txn("2026-02-15", 5000),
        _income_txn("2026-03-15", 6000),
    ])
    result = tax.estimate_annual_income(transactions)
    assert result == pytest.approx((4000 + 5000 + 6000) / 3 * 12)


def test_estimate_annual_income_ignores_expenses():
    transactions = pd.DataFrame([
        _income_txn("2026-01-15", 4000),
        {"txn_date": "2026-01-20", "description": "Rent", "category": "Housing", "txn_type": "expense", "amount": 1500},
    ])
    result = tax.estimate_annual_income(transactions)
    assert result == pytest.approx(4000 * 12)


def test_estimate_annual_income_none_when_no_income():
    transactions = pd.DataFrame([
        {"txn_date": "2026-01-20", "description": "Rent", "category": "Housing", "txn_type": "expense", "amount": 1500},
    ])
    assert tax.estimate_annual_income(transactions) is None


def test_estimate_annual_income_empty_input():
    assert tax.estimate_annual_income(pd.DataFrame(columns=["txn_date", "txn_type", "amount"])) is None


def test_estimate_annual_income_caps_at_last_12_months():
    rows = [_income_txn(f"{2024 + m // 12}-{m % 12 + 1:02d}-01", 1000 + m) for m in range(18)]
    transactions = pd.DataFrame(rows)
    result = tax.estimate_annual_income(transactions)
    last_12_avg = sum(1000 + m for m in range(6, 18)) / 12
    assert result == pytest.approx(last_12_avg * 12)
