"""Federal income tax estimate -- illustrative only, not tax advice.

Uses the `filing_status` field already on the profile (see cfo.db) to
estimate a marginal and effective federal tax rate from income logged in
this app. Deliberately narrow, by design, not by oversight:

- **Federal only.** No state, local, or FICA/payroll tax.
- **Standard deduction only.** No itemizing, no credits (child tax
  credit, EITC, etc.), no AMT, no NIIT, no qualified-dividend/capital-gains
  preferential rates -- ordinary-income brackets applied to everything.
- **"Income" is a rough estimate**, not a real return: it's the average
  of the last up-to-12 calendar months of transactions logged as `income`
  in this app, annualized (avg monthly x 12). It doesn't know about
  income this app was never told about (a spouse's separate income under
  MFS, side income not logged as a transaction) or pre-tax deductions
  (401(k), traditional IRA, HSA) that would lower actual taxable income
  below what's estimated here.

Tax year and bracket source are named below. These numbers do NOT update
themselves and need to be replaced by hand once a year -- see TAX_YEAR.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# IRS Rev. Proc. 2025-32 (2026 tax year), inflation-adjusted brackets and
# standard deductions. Verify against https://www.irs.gov before relying
# on these for anything real -- and update this whole block for the next
# tax year every fall when the IRS publishes the new Rev. Proc.
TAX_YEAR = 2026
TAX_YEAR_SOURCE = "IRS Rev. Proc. 2025-32"

# Each list is (rate, upper_bound_of_bracket_in_dollars), in ascending
# order; the last bracket's upper bound is infinity.
FEDERAL_BRACKETS: dict[str, list[tuple[float, float]]] = {
    "single": [
        (0.10, 12_400), (0.12, 50_400), (0.22, 105_700), (0.24, 201_775),
        (0.32, 256_225), (0.35, 640_600), (0.37, float("inf")),
    ],
    "mfj": [
        (0.10, 24_800), (0.12, 100_800), (0.22, 211_400), (0.24, 403_550),
        (0.32, 512_450), (0.35, 768_700), (0.37, float("inf")),
    ],
    "mfs": [
        (0.10, 12_400), (0.12, 50_400), (0.22, 105_700), (0.24, 201_775),
        (0.32, 256_225), (0.35, 384_350), (0.37, float("inf")),
    ],
    "hoh": [
        (0.10, 17_700), (0.12, 67_450), (0.22, 105_700), (0.24, 201_750),
        (0.32, 256_200), (0.35, 640_600), (0.37, float("inf")),
    ],
}

STANDARD_DEDUCTION: dict[str, float] = {
    "single": 16_100, "mfj": 32_200, "mfs": 16_100, "hoh": 24_150,
}

# Maps cfo.db.FILING_STATUSES to the bracket/deduction table above.
# Qualifying Surviving Spouse uses the same brackets as MFJ, per IRS rules.
_FILING_STATUS_KEY = {
    "Single": "single",
    "Married Filing Jointly": "mfj",
    "Married Filing Separately": "mfs",
    "Head of Household": "hoh",
    "Qualifying Surviving Spouse": "mfj",
}


@dataclass
class TaxEstimate:
    filing_status: str
    annual_income: float
    standard_deduction: float
    taxable_income: float
    estimated_tax: float
    marginal_rate: float
    effective_rate: float  # estimated_tax / annual_income


def estimate_annual_income(transactions: pd.DataFrame) -> float | None:
    """Average monthly income (from transactions logged as `income`) over
    up to the last 12 distinct calendar months present, annualized. None
    if there's no income data at all."""
    if transactions.empty:
        return None
    income = transactions[transactions["txn_type"] == "income"]
    if income.empty:
        return None
    income = income.copy()
    income["txn_date"] = pd.to_datetime(income["txn_date"])
    income["_month"] = income["txn_date"].dt.to_period("M")
    monthly = income.groupby("_month")["amount"].sum().sort_index().tail(12)
    return float(monthly.mean() * 12)


def estimate_federal_tax(
    annual_income: float,
    filing_status: str | None,
    brackets: dict[str, list[tuple[float, float]]] | None = None,
    standard_deductions: dict[str, float] | None = None,
) -> TaxEstimate | None:
    """Marginal-bracket federal tax estimate. None if filing_status isn't
    one this app can map to a bracket table (e.g. "Prefer not to say", or
    not set) or annual_income isn't positive. `brackets` and
    `standard_deductions` are overridable for testing; production callers
    should leave them as the module defaults."""
    if annual_income is None or annual_income <= 0 or not filing_status:
        return None
    key = _FILING_STATUS_KEY.get(filing_status)
    if key is None:
        return None

    brackets = brackets or FEDERAL_BRACKETS
    standard_deductions = standard_deductions or STANDARD_DEDUCTION
    bracket_table = brackets[key]
    std_deduction = standard_deductions[key]
    taxable_income = max(0.0, annual_income - std_deduction)

    tax = 0.0
    lower = 0.0
    marginal_rate = bracket_table[0][0]
    for rate, upper in bracket_table:
        if taxable_income <= lower:
            break
        amount_in_bracket = min(taxable_income, upper) - lower
        if amount_in_bracket > 0:
            tax += amount_in_bracket * rate
            marginal_rate = rate
        lower = upper

    effective_rate = tax / annual_income

    return TaxEstimate(
        filing_status=filing_status,
        annual_income=round(annual_income, 2),
        standard_deduction=std_deduction,
        taxable_income=round(taxable_income, 2),
        estimated_tax=round(tax, 2),
        marginal_rate=marginal_rate,
        effective_rate=round(effective_rate, 4),
    )
