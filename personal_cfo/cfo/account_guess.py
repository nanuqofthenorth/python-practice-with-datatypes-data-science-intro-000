"""Best-effort account name/kind/category guess from a statement's
filename, for the Setup Wizard. Pure function, no Streamlit or DB
dependency -- easy to test on its own, matching the pattern used for
cfo/calculations.py and cfo/tax.py.

This is deliberately a *guess*, never trusted silently: the wizard always
shows it in editable fields before creating the account, the same way
cfo/importers.py's column detection is a starting point the user reviews
and adjusts, not an automatic decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Ordered by specificity -- checked top to bottom, first match wins, so a
# more specific keyword (e.g. "heloc") must come before a more general one
# that could also appear in the same filename.
_KEYWORD_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("heloc", "home equity"), "liability", "Other Liability"),
    (("mortgage",), "liability", "Mortgage"),
    (("student loan", "sallie mae", "navient", "fedloan", "nelnet"), "liability", "Student Loan"),
    (("auto loan", "car loan"), "liability", "Auto Loan"),
    (("credit card", "visa", "mastercard", "amex", "american express", "discover card", "discover"),
     "liability", "Credit Card"),
    (("401k", "401(k)", "403b", "403(b)", "ira", "retirement", "pension"), "asset", "Retirement"),
    (("brokerage", "invest", "trading", "robinhood", "fidelity", "schwab", "vanguard", "etrade", "e*trade"),
     "asset", "Investments"),
    (("mortgage payoff", "deed", "property"), "asset", "Real Estate"),
    (("saving",), "asset", "Cash"),
    (("checking",), "asset", "Cash"),
]

_STOPWORDS = {"statement", "export", "transactions", "activity", "history", "download", "csv", "xlsx", "xls", "pdf"}


@dataclass
class AccountGuess:
    name: str
    kind: str  # "asset" | "liability"
    category: str
    confident: bool  # False if nothing matched and this fell back to a generic default


def guess_account_from_filename(filename: str) -> AccountGuess:
    stem = Path(filename).stem
    lower = stem.lower().replace("_", " ").replace("-", " ")

    for keywords, kind, category in _KEYWORD_RULES:
        if any(kw in lower for kw in keywords):
            return AccountGuess(name=_clean_name(stem), kind=kind, category=category, confident=True)

    return AccountGuess(name=_clean_name(stem), kind="asset", category="Other Asset", confident=False)


def _clean_name(stem: str) -> str:
    """Turn a filename stem into a plausible account name: split on
    underscores/hyphens, drop generic words like "statement" or
    "export", and title-case what's left. Falls back to the original
    stem if that would leave nothing useful."""
    words = re.split(r"[_\-\s]+", stem.strip())
    kept = [w for w in words if w.lower() not in _STOPWORDS and w]
    if not kept:
        kept = words
    name = " ".join(kept).strip()
    return name.title() if name else "Imported Account"
