"""Financial calculations: the "CFO brain" of the app.

Pure functions over pandas DataFrames / plain values -- no Streamlit or
database imports here, so this module is easy to reason about and test
independently of the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

import pandas as pd


# ------------------------------------------------------------- net worth
def net_worth_summary(accounts: pd.DataFrame) -> dict:
    if accounts.empty:
        return {"total_assets": 0.0, "total_liabilities": 0.0, "net_worth": 0.0}
    total_assets = accounts.loc[accounts["kind"] == "asset", "balance"].sum()
    total_liabilities = accounts.loc[accounts["kind"] == "liability", "balance"].sum()
    return {
        "total_assets": float(total_assets),
        "total_liabilities": float(total_liabilities),
        "net_worth": float(total_assets - total_liabilities),
    }


# --------------------------------------------------------------- cash flow
def monthly_cash_flow(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame indexed by month (YYYY-MM) with income, expenses,
    net, and savings_rate columns."""
    if transactions.empty:
        return pd.DataFrame(columns=["month", "income", "expenses", "net", "savings_rate"])

    df = transactions.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df["month"] = df["txn_date"].dt.to_period("M").astype(str)

    grouped = df.groupby(["month", "txn_type"])["amount"].sum().unstack(fill_value=0)
    grouped = grouped.reindex(columns=["income", "expense"], fill_value=0)
    grouped = grouped.rename(columns={"expense": "expenses"})
    grouped["net"] = grouped["income"] - grouped["expenses"]
    grouped["savings_rate"] = grouped.apply(
        lambda r: (r["net"] / r["income"]) if r["income"] > 0 else 0.0, axis=1
    )
    grouped = grouped.reset_index().sort_values("month")
    return grouped


def current_month_key() -> str:
    return date.today().strftime("%Y-%m")


def spending_by_category(transactions: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    if transactions.empty:
        return pd.DataFrame(columns=["category", "amount"])
    df = transactions.copy()
    df["txn_date"] = pd.to_datetime(df["txn_date"])
    df = df[df["txn_type"] == "expense"]
    if month:
        df = df[df["txn_date"].dt.to_period("M").astype(str) == month]
    out = df.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
    return out


# ------------------------------------------------------------------ budget
def budget_vs_actual(budgets: pd.DataFrame, transactions: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    month = month or current_month_key()
    actual = spending_by_category(transactions, month=month).rename(columns={"amount": "actual"})
    if budgets.empty:
        merged = actual.copy()
        merged["budgeted"] = 0.0
    else:
        merged = budgets[["category", "monthly_amount"]].rename(columns={"monthly_amount": "budgeted"}).merge(
            actual, on="category", how="outer"
        )
    merged["actual"] = merged.get("actual", 0.0)
    merged["budgeted"] = merged.get("budgeted", 0.0)
    merged[["actual", "budgeted"]] = merged[["actual", "budgeted"]].fillna(0.0)
    merged["variance"] = merged["budgeted"] - merged["actual"]
    merged["pct_used"] = merged.apply(
        lambda r: (r["actual"] / r["budgeted"]) if r["budgeted"] > 0 else float("nan"), axis=1
    )
    return merged.sort_values("actual", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------- debt payoff
@dataclass
class DebtPayoffResult:
    schedule: pd.DataFrame  # month, debt name, balance
    payoff_month_by_debt: dict = field(default_factory=dict)
    months_to_debt_free: int = 0
    total_interest_paid: float = 0.0


def simulate_debt_payoff(
    debts: pd.DataFrame,
    extra_monthly_payment: float = 0.0,
    strategy: Literal["avalanche", "snowball"] = "avalanche",
    max_months: int = 600,
) -> DebtPayoffResult:
    """Simulate paying off a set of debts.

    Every debt gets its minimum payment each month. Any extra budget is
    thrown at one debt at a time: avalanche = highest APR first,
    snowball = smallest balance first. Once a debt is paid off, its
    minimum payment is freed up and rolls into the extra pool.
    """
    if debts.empty:
        return DebtPayoffResult(schedule=pd.DataFrame(columns=["month", "debt", "balance"]))

    balances = {row["name"]: float(row["balance"]) for _, row in debts.iterrows()}
    aprs = {row["name"]: float(row["apr"]) / 100.0 for _, row in debts.iterrows()}
    min_payments = {row["name"]: float(row["min_payment"]) for _, row in debts.iterrows()}

    order_key = (lambda n: -aprs[n]) if strategy == "avalanche" else (lambda n: balances[n])

    rows = []
    payoff_month_by_debt: dict[str, int] = {}
    total_interest = 0.0
    month = 0

    rows.extend({"month": 0, "debt": n, "balance": b} for n, b in balances.items())

    while any(b > 0.01 for b in balances.values()) and month < max_months:
        month += 1
        extra_pool = extra_monthly_payment
        active = [n for n, b in balances.items() if b > 0.01]

        for name in active:
            monthly_rate = aprs[name] / 12
            interest = balances[name] * monthly_rate
            total_interest += interest
            balances[name] += interest

        freed_min_payments = sum(min_payments[n] for n in balances if balances[n] <= 0.01 and n not in payoff_month_by_debt)

        for name in sorted(active, key=order_key):
            if balances[name] <= 0.01:
                continue
            payment = min(min_payments[name], balances[name])
            balances[name] -= payment

        target_order = sorted(active, key=order_key)
        pool = extra_pool
        for name in target_order:
            if pool <= 0:
                break
            if balances[name] <= 0.01:
                continue
            paydown = min(pool, balances[name])
            balances[name] -= paydown
            pool -= paydown

        for name, bal in balances.items():
            if bal <= 0.01 and name not in payoff_month_by_debt:
                payoff_month_by_debt[name] = month
                balances[name] = 0.0

        rows.extend({"month": month, "debt": n, "balance": max(b, 0.0)} for n, b in balances.items())

    months_to_debt_free = max(payoff_month_by_debt.values()) if payoff_month_by_debt else 0
    schedule = pd.DataFrame(rows)
    return DebtPayoffResult(
        schedule=schedule,
        payoff_month_by_debt=payoff_month_by_debt,
        months_to_debt_free=months_to_debt_free,
        total_interest_paid=round(total_interest, 2),
    )


# ------------------------------------------------------------------- goals
def months_between(start: date, end: date) -> int:
    return max((end.year - start.year) * 12 + (end.month - start.month), 0)


def goal_required_monthly_contribution(target_amount: float, current_amount: float, target_date: str | None) -> float | None:
    if not target_date:
        return None
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    remaining_months = max(months_between(date.today(), target), 1)
    remaining_amount = max(target_amount - current_amount, 0)
    return remaining_amount / remaining_months


# ---------------------------------------------------------------- insights
def generate_insights(
    net_worth: dict,
    cash_flow: pd.DataFrame,
    budget_df: pd.DataFrame,
    debts: pd.DataFrame,
    goals: pd.DataFrame,
) -> list[dict]:
    """Rule-based, deterministic financial insights. Each insight is a dict
    with keys: level ('good' | 'warning' | 'critical'), text."""
    insights: list[dict] = []

    if not cash_flow.empty:
        latest = cash_flow.iloc[-1]
        rate = latest["savings_rate"]
        if latest["income"] == 0:
            insights.append({"level": "warning", "text": "No income recorded for the latest month -- add transactions to get an accurate picture."})
        elif rate < 0:
            insights.append({"level": "critical", "text": f"You spent more than you earned last month (net {latest['net']:,.0f}). Expenses exceeded income."})
        elif rate < 0.10:
            insights.append({"level": "warning", "text": f"Savings rate is {rate:.0%}, below the commonly recommended 20% target."})
        elif rate < 0.20:
            insights.append({"level": "warning", "text": f"Savings rate is {rate:.0%} -- solid, but there's room to reach the 20% benchmark."})
        else:
            insights.append({"level": "good", "text": f"Savings rate is {rate:.0%}, at or above the 20% benchmark. Nice work."})

    if not budget_df.empty:
        over = budget_df[(budget_df["budgeted"] > 0) & (budget_df["actual"] > budget_df["budgeted"])]
        for _, row in over.iterrows():
            insights.append({
                "level": "warning",
                "text": f"Over budget in {row['category']} by ${row['actual'] - row['budgeted']:,.0f} this month.",
            })

    if not debts.empty:
        high_apr = debts[debts["apr"] >= 15]
        if not high_apr.empty:
            worst = high_apr.sort_values("apr", ascending=False).iloc[0]
            insights.append({
                "level": "critical" if worst["apr"] >= 20 else "warning",
                "text": f"{worst['name']} carries a {worst['apr']:.1f}% APR -- prioritize paying this down (avalanche method) before other goals.",
            })
        total_debt = debts["balance"].sum()
        if net_worth.get("net_worth", 0) < 0:
            insights.append({"level": "critical", "text": f"Net worth is negative (${net_worth['net_worth']:,.0f}) with ${total_debt:,.0f} in tracked debt."})

    if not goals.empty:
        for _, g in goals.iterrows():
            if g["target_amount"] <= 0:
                continue
            pct = g["current_amount"] / g["target_amount"]
            if pct >= 1:
                insights.append({"level": "good", "text": f"Goal '{g['name']}' is fully funded!"})
            elif g["target_date"]:
                needed = goal_required_monthly_contribution(g["target_amount"], g["current_amount"], g["target_date"])
                if needed is not None:
                    insights.append({
                        "level": "warning" if pct < 0.5 else "good",
                        "text": f"Goal '{g['name']}' is {pct:.0%} funded -- needs about ${needed:,.0f}/month to hit its target date.",
                    })

    if not insights:
        insights.append({"level": "good", "text": "Add accounts, transactions, and debts to start getting personalized insights."})

    return insights


# ---------------------------------------------------------- health score
@dataclass
class HealthComponent:
    name: str
    score: float  # 0-100
    weight: float  # relative weight before renormalization
    detail: str


@dataclass
class HealthScore:
    score: float | None  # 0-100, or None if there's no data to score yet
    label: str
    components: list[HealthComponent] = field(default_factory=list)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def calculate_health_score(
    net_worth: dict,
    cash_flow: pd.DataFrame,
    budget_df: pd.DataFrame,
    debts: pd.DataFrame,
    goals: pd.DataFrame,
    accounts: pd.DataFrame,
) -> HealthScore:
    """A single 0-100 "on track" gauge, built from five equally-legible
    components. Each component is scored independently on its own 0-100
    scale and only included if there's enough data to compute it; the
    remaining weights are renormalized so the overall score is never
    diluted by a component that simply has no data yet."""
    components: list[HealthComponent] = []

    if not cash_flow.empty:
        rate = float(cash_flow.iloc[-1]["savings_rate"])
        score = 0.0 if rate <= 0 else _clamp(rate / 0.20 * 100)
        components.append(HealthComponent(
            "Savings Rate", score, 0.30, f"{rate:.0%} of income saved last month (target 20%)."
        ))

    if not budget_df.empty:
        budgeted_rows = budget_df[budget_df["budgeted"] > 0]
        total_budgeted = budgeted_rows["budgeted"].sum()
        if total_budgeted > 0:
            total_actual = budgeted_rows["actual"].sum()
            ratio = total_actual / total_budgeted
            score = _clamp(100 - max(0.0, ratio - 1) * 200)
            components.append(HealthComponent(
                "Budget Adherence", score, 0.20,
                f"Spent {ratio:.0%} of this month's budget across tracked categories."
            ))

    if debts.empty and not accounts.empty:
        components.append(HealthComponent("Debt Health", 100.0, 0.20, "No tracked debt."))
    elif not debts.empty:
        total_balance = debts["balance"].sum()
        avg_apr = (debts["apr"] * debts["balance"]).sum() / total_balance if total_balance > 0 else 0.0
        score = _clamp(100 - avg_apr * 3)
        components.append(HealthComponent(
            "Debt Health", score, 0.20, f"Balance-weighted average APR of {avg_apr:.1f}% across debts."
        ))

    if not accounts.empty and not cash_flow.empty:
        cash_balance = accounts.loc[
            (accounts["kind"] == "asset") & (accounts["category"] == "Cash"), "balance"
        ].sum()
        avg_monthly_expenses = cash_flow["expenses"].tail(3).mean()
        if avg_monthly_expenses > 0:
            months_covered = cash_balance / avg_monthly_expenses
            score = _clamp(months_covered / 6 * 100)
            components.append(HealthComponent(
                "Emergency Fund", score, 0.15,
                f"{months_covered:.1f} months of expenses in cash (target 6)."
            ))

    if not goals.empty:
        fundable = goals[goals["target_amount"] > 0]
        if not fundable.empty:
            pct_funded = (fundable["current_amount"] / fundable["target_amount"]).clip(upper=1.0)
            score = _clamp(pct_funded.mean() * 100)
            components.append(HealthComponent(
                "Goal Progress", score, 0.15, f"Goals are {pct_funded.mean():.0%} funded on average."
            ))

    if not components:
        return HealthScore(score=None, label="Not enough data yet", components=[])

    total_weight = sum(c.weight for c in components)
    overall = sum(c.score * c.weight for c in components) / total_weight

    if overall >= 70:
        label = "On Track"
    elif overall >= 40:
        label = "Watch"
    else:
        label = "Off Track"

    return HealthScore(score=round(overall, 1), label=label, components=components)
