"""Best-effort account name/kind/category guess for the Setup Wizard, from
a statement's filename and -- when available -- the statement's own
content (PDF text, or CSV/Excel column headers). Pure function, no
Streamlit or DB dependency -- easy to test on its own, matching the
pattern used for cfo/calculations.py and cfo/tax.py.

Content matters more than the filename: institutions' boilerplate
statement language ("Minimum Payment Due", "Escrow Balance") is far more
reliable than what someone happened to name the downloaded file
("download (3).csv" tells you nothing; the statement text inside it
usually does). Both are searched together -- whichever source the
keyword actually appears in.

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
# that could also appear in the same filename or statement text.
_KEYWORD_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("heloc", "home equity line"), "liability", "Other Liability"),
    (("mortgage", "escrow balance", "principal and interest", "loan servicer"),
     "liability", "Mortgage"),
    (("student loan", "sallie mae", "navient", "fedloan", "nelnet", "great lakes loan"),
     "liability", "Student Loan"),
    (("auto loan", "car loan", "vehicle loan"), "liability", "Auto Loan"),
    (
        ("credit card", "visa", "mastercard", "amex", "american express", "discover card", "discover",
         "minimum payment due", "credit limit", "available credit", "cash advance apr", "purchase apr"),
        "liability", "Credit Card",
    ),
    (("401k", "401(k)", "403b", "403(b)", "ira", "retirement", "pension"), "asset", "Retirement"),
    (
        ("brokerage", "invest", "trading", "robinhood", "fidelity", "schwab", "vanguard", "etrade", "e*trade",
         "cost basis", "shares held", "dividends", "portfolio value"),
        "asset", "Investments",
    ),
    (("deed", "property tax", "assessed value"), "asset", "Real Estate"),
    (("saving", "high-yield savings"), "asset", "Cash"),
    (("checking", "direct deposit", "overdraft protection"), "asset", "Cash"),
]

_STOPWORDS = {"statement", "export", "transactions", "activity", "history", "download", "csv", "xlsx", "xls", "pdf"}


@dataclass
class AccountGuess:
    name: str
    kind: str  # "asset" | "liability"
    category: str
    confident: bool  # False if nothing matched and this fell back to a generic default


def guess_account(filename: str, content_hint: str = "") -> AccountGuess:
    """`content_hint` is whatever's available and cheap to get without a
    separate parse pass: PDF extraction's full text, or a CSV/Excel
    file's column headers joined into one string. The account *name* is
    still derived from the filename (statement text rarely contains
    anything as clean as "Chase Checking" verbatim) -- only kind/category
    detection considers content, and only to search a broader, more
    reliable set of keywords than a filename alone could match."""
    stem = Path(filename).stem
    filename_lower = stem.lower().replace("_", " ").replace("-", " ")
    combined_lower = filename_lower + " " + content_hint.lower()

    for keywords, kind, category in _KEYWORD_RULES:
        if any(kw in combined_lower for kw in keywords):
            return AccountGuess(name=_clean_name(stem), kind=kind, category=category, confident=True)

    return AccountGuess(name=_clean_name(stem), kind="asset", category="Other Asset", confident=False)


def guess_account_from_filename(filename: str) -> AccountGuess:
    """Filename-only convenience wrapper -- use guess_account() directly
    when statement content is available, since content is the more
    reliable signal."""
    return guess_account(filename)


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
