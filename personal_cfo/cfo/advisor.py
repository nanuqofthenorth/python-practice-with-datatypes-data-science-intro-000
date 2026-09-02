"""LLM-powered financial consultation, grounded in the user's own local
data: on-demand Q&A ("what should I do next?") and a proactive briefing
that surfaces the same kind of judgment without being asked.

This is the one part of the app that leaves the machine -- every call
here sends the user's financial snapshot to the Anthropic API. Nothing
in this module reads Streamlit session state or environment variables
directly; the caller resolves and passes an API key explicitly, so it's
obvious at the call site when data is about to be sent externally.
"""
from __future__ import annotations

import json

import pandas as pd

from . import calculations as calc

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """You are a meticulous, plain-spoken personal CFO for an individual user. You are given a structured JSON snapshot of their real financial data (accounts, recent transactions, budget, debts, and goals) drawn from an app they use to track their finances -- treat every number in it as ground truth, and never invent figures that aren't there.

Your job: help them decide what to do next in relation to their stated goals. Be specific and prioritized -- name actual dollar amounts, account names, and categories from their data rather than generic advice. When you make a recommendation, say why, using the numbers.

Ground rules:
- You are not a licensed financial, tax, or legal advisor. If a question has real regulatory/tax stakes (e.g. retirement account withdrawals, tax-loss harvesting), say so briefly, but still give your best reasoned take rather than deflecting.
- If the data is too sparse to answer well (e.g. no transactions logged), say what's missing and what to add.
- Keep answers tight: lead with the recommendation, then the 2-4 numbers that justify it. Avoid disclaimers-as-padding and avoid restating the question."""

BRIEFING_INSTRUCTION = """Based on the financial snapshot above, proactively identify the 3 to 5 most important things this person should know or do right now -- what a good CFO would flag without being asked. Prioritize by financial impact and urgency (a high-APR debt or a budget blown by a lot outranks a minor optimization).

Return ONLY a JSON array (no prose, no markdown fence), each element shaped like:
{"title": "short imperative headline, <=8 words", "detail": "1-2 sentences with the specific numbers behind it", "level": "good" | "watch" | "action"}

"action" = needs a decision or a change soon; "watch" = worth monitoring, not urgent; "good" = going well, worth reinforcing. Include at least one "good" item if the data supports it -- this should read as a briefing, not just a list of problems."""


def build_financial_snapshot() -> dict:
    """Assemble the same data the dashboard shows into one JSON-able
    snapshot -- this, not raw DB access, is what the model sees."""
    from . import db  # local import: keep advisor.py importable without a live DB in tests

    accounts = db.list_accounts()
    transactions = db.list_transactions()
    budgets = db.list_budgets()
    debts = db.list_debts()
    goals = db.list_goals()
    snapshots = db.list_snapshots()

    net_worth = calc.net_worth_summary(accounts)
    cash_flow = calc.monthly_cash_flow(transactions)
    budget_df = calc.budget_vs_actual(budgets, transactions)
    spending = calc.spending_by_category(transactions, month=calc.current_month_key())

    return {
        "today": pd.Timestamp.today().date().isoformat(),
        "net_worth": net_worth,
        "accounts": _records(accounts, ["name", "kind", "category", "balance", "interest_rate"]),
        "net_worth_trend_last_12_snapshots": _records(snapshots.tail(12), ["snapshot_date", "net_worth"]),
        "monthly_cash_flow_last_6mo": _records(cash_flow.tail(6).round(2), ["month", "income", "expenses", "net", "savings_rate"]),
        "current_month_spending_by_category": _records(spending.round(2), ["category", "amount"]),
        "budget_vs_actual_this_month": _records(budget_df.round(2), ["category", "budgeted", "actual", "variance"]),
        "debts": _records(debts, ["name", "balance", "apr", "min_payment"]),
        "goals": _records(goals, ["name", "target_amount", "current_amount", "target_date"]),
        "recent_transactions_last_60": _records(
            transactions.head(60), ["txn_date", "description", "category", "txn_type", "amount"]
        ),
    }


def _records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    if df.empty:
        return []
    return df[columns].to_dict("records")


def snapshot_json() -> str:
    return json.dumps(build_financial_snapshot(), default=str, sort_keys=True)


def _extract_text(content) -> str:
    return "".join(block.text for block in content if block.type == "text").strip()


def _system_blocks(snapshot: str) -> list[dict]:
    return [
        {"type": "text", "text": SYSTEM_PROMPT},
        {
            "type": "text",
            "text": f"The user's current financial snapshot (JSON, ground truth):\n{snapshot}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def ask_question(api_key: str, question: str, snapshot: str, history: list[dict] | None = None) -> str:
    """Answer a free-form question grounded in the user's financial data.
    `history` is prior {"role": "user"|"assistant", "content": str} turns
    from this chat session (the snapshot itself lives in the cached
    system prompt, not repeated per turn)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    messages = list(history or []) + [{"role": "user", "content": question}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_system_blocks(snapshot),
        messages=messages,
    )
    return _extract_text(response.content)


def generate_briefing(api_key: str, snapshot: str) -> list[dict]:
    """Proactive, unprompted recommendations -- the model returns a JSON
    array of {title, detail, level}."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_system_blocks(snapshot),
        messages=[{"role": "user", "content": BRIEFING_INSTRUCTION}],
    )
    text = _extract_text(response.content)
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError("Expected a JSON array of briefing items")
    return items
