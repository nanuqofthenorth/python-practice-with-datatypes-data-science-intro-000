"""Parsing real-world financial statements: bank/brokerage/credit-card CSV
and XLSX exports, and PDF statements (credit cards, mortgages, HELOCs).

Institutions export wildly inconsistent formats, so this module favors
best-effort detection with a human confirming the result over silent
"magic" -- every guess made here is surfaced in the UI as an editable
default, never applied blindly.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import pandas as pd

# ------------------------------------------------------------ CSV / XLSX

DATE_ALIASES = ["date", "transaction date", "posted date", "posting date", "trans date", "post date"]
DESC_ALIASES = ["description", "memo", "payee", "name", "details", "transaction", "merchant"]
AMOUNT_ALIASES = ["amount", "transaction amount", "amount ($)"]
DEBIT_ALIASES = ["debit", "withdrawal", "withdrawals", "money out", "charge", "charges"]
CREDIT_ALIASES = ["credit", "deposit", "deposits", "money in", "payment", "payments"]
BALANCE_ALIASES = ["balance", "running balance", "ending balance", "new balance"]
CATEGORY_ALIASES = ["category", "type"]

KEYWORD_CATEGORY_MAP: list[tuple[str, str]] = [
    (r"payroll|direct dep(osit)?|salary|paycheck", "Salary"),
    (r"dividend|interest (earned|income)|capital gain", "Investment Income"),
    (r"rent(?!al car)|landlord|mortgage payment", "Housing"),
    (r"electric|water\s?works|utility|utilities|internet|comcast|xfinity|verizon|at&t|t-mobile|spectrum", "Utilities"),
    (r"grocery|groceries|walmart|kroger|whole foods|trader joe|safeway|costco|aldi|publix", "Groceries"),
    (
        r"restaurant|starbucks|chipotle|mcdonald|doordash|grubhub|uber eats|postmates|cafe|coffee|pizza|"
        r"chick-fil-a|bar\b",
        "Dining",
    ),
    (r"shell|chevron|exxon|gas station|uber\b|lyft|parking|transit|metro|toll", "Transportation"),
    (r"insurance|geico|progressive|state farm|allstate", "Insurance"),
    (r"pharmacy|cvs|walgreens|doctor|medical|health|dental|clinic", "Healthcare"),
    (r"payment.*thank you|online payment|autopay|electronic payment|internet payment|loan payment|card payment", "Debt Payments"),
    (r"netflix|spotify|hulu|disney\+|prime video|subscription|apple\.com/bill", "Subscriptions"),
    (r"amazon|target\b|best buy|shopping|walgreens", "Shopping"),
    (r"airline|hotel|airbnb|expedia|delta |united |southwest ", "Travel"),
    (r"daycare|childcare|preschool", "Childcare"),
    (r"movie|concert|theater|ticketmaster|spotify|netflix|steam\b", "Entertainment"),
]

PAYMENT_TRANSFER_PATTERN = re.compile(
    r"payment.*thank you|online payment|autopay|electronic payment|internet payment|"
    r"transfer (to|from)|(^|\s)ach (debit|credit)(\s|$)",
    re.IGNORECASE,
)


def _norm(col: str) -> str:
    return re.sub(r"\s+", " ", str(col)).strip().lower()


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    normed = {_norm(c): c for c in columns}
    for alias in aliases:
        if alias in normed:
            return normed[alias]
    for alias in aliases:
        for norm_col, orig in normed.items():
            if alias in norm_col:
                return orig
    return None


def read_statement_table(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read a CSV or XLSX export, tolerating a few junk header rows that
    some institutions (notably brokerages) prepend before the real table."""
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        return _read_excel_smart(file_bytes)
    return _read_csv_smart(file_bytes)


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(_norm(c) for c in cells)
    signals = DATE_ALIASES + DESC_ALIASES + AMOUNT_ALIASES + DEBIT_ALIASES + CREDIT_ALIASES
    return any(s in joined for s in signals)


def _read_csv_smart(file_bytes: bytes) -> pd.DataFrame:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Could not decode this file as text -- is it really a CSV?")

    lines = text.splitlines()
    header_row = 0
    for i, line in enumerate(lines[:15]):
        cells = next(_csv_split(line))
        if _looks_like_header(cells):
            header_row = i
            break

    df = pd.read_csv(io.StringIO(text), skiprows=header_row)
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _csv_split(line: str):
    import csv as _csv
    yield next(_csv.reader([line]))


def _read_excel_smart(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    header_row = 0
    for i in range(min(15, len(raw))):
        cells = [str(v) for v in raw.iloc[i].tolist() if pd.notna(v)]
        if _looks_like_header(cells):
            header_row = i
            break
    df = pd.read_excel(io.BytesIO(file_bytes), skiprows=header_row)
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df


@dataclass
class ColumnMapping:
    date_col: str | None = None
    description_col: str | None = None
    amount_col: str | None = None
    debit_col: str | None = None
    credit_col: str | None = None
    balance_col: str | None = None


def detect_columns(df: pd.DataFrame) -> ColumnMapping:
    columns = list(df.columns)
    mapping = ColumnMapping(
        date_col=_find_column(columns, DATE_ALIASES),
        description_col=_find_column(columns, DESC_ALIASES),
        balance_col=_find_column(columns, BALANCE_ALIASES),
    )
    debit = _find_column(columns, DEBIT_ALIASES)
    credit = _find_column(columns, CREDIT_ALIASES)
    if debit and credit:
        mapping.debit_col, mapping.credit_col = debit, credit
    else:
        mapping.amount_col = _find_column(columns, AMOUNT_ALIASES)
    return mapping


def guess_category(description: str, is_expense: bool) -> str:
    text = str(description).lower()
    for pattern, category in KEYWORD_CATEGORY_MAP:
        if re.search(pattern, text):
            return category
    return "Other" if is_expense else "Other Income"


def is_likely_transfer(description: str) -> bool:
    return bool(PAYMENT_TRANSFER_PATTERN.search(str(description)))


def normalize_transactions(
    df: pd.DataFrame,
    mapping: ColumnMapping,
    flip_sign: bool = False,
) -> pd.DataFrame:
    """Turn a raw statement table into the app's canonical transaction
    shape: txn_date, description, category, txn_type, amount, is_transfer
    (is_duplicate is filled in by the caller against the existing ledger).

    Sign convention: on essentially every consumer bank/card CSV export,
    a positive amount (or a populated Credit column) means money moving
    toward the account holder -- a deposit into a checking account, or a
    payment/refund on a credit card -- and negative (or a populated Debit
    column) means money moving away -- a withdrawal, or a purchase. That
    holds regardless of whether the account itself is an asset or a
    liability, so no kind-based sign flip is applied here; use flip_sign
    for the minority of exports that reverse it.
    """
    out = pd.DataFrame()
    out["txn_date"] = pd.to_datetime(df[mapping.date_col], errors="coerce").dt.date.astype(str)
    out["description"] = df[mapping.description_col].astype(str).str.strip()

    if mapping.debit_col and mapping.credit_col:
        debit = pd.to_numeric(df[mapping.debit_col], errors="coerce").fillna(0).abs()
        credit = pd.to_numeric(df[mapping.credit_col], errors="coerce").fillna(0).abs()
        signed = credit - debit
    else:
        signed = pd.to_numeric(df[mapping.amount_col], errors="coerce").fillna(0)

    if flip_sign:
        signed = -signed

    out["txn_type"] = signed.apply(lambda v: "expense" if v < 0 else "income")
    out["amount"] = signed.abs().round(2)
    out["category"] = [
        guess_category(desc, t == "expense") for desc, t in zip(out["description"], out["txn_type"])
    ]
    out["is_transfer"] = out["description"].apply(is_likely_transfer)
    out = out.dropna(subset=["txn_date"])
    out = out[out["amount"] > 0]
    return out.reset_index(drop=True)


def extract_ending_balance_from_table(df: pd.DataFrame, mapping: ColumnMapping) -> float | None:
    if not mapping.balance_col or mapping.date_col is None:
        return None
    try:
        dated = df.copy()
        dated["_date"] = pd.to_datetime(dated[mapping.date_col], errors="coerce")
        dated = dated.dropna(subset=["_date"]).sort_values("_date")
        if dated.empty:
            return None
        value = pd.to_numeric(dated.iloc[-1][mapping.balance_col], errors="coerce")
        return None if pd.isna(value) else float(value)
    except Exception:
        return None


# ------------------------------------------------------------------- PDF

BALANCE_LABELS = [
    "new balance", "statement balance", "current balance", "ending balance",
    "outstanding balance", "principal balance", "total balance due",
    "account balance", "total balance",
]
DATE_LABELS = ["statement date", "closing date", "statement closing date", "as of"]

# Ordered most-specific first -- a statement listing separate purchase/cash
# advance/balance-transfer APRs should surface each labeled distinctly
# rather than all collapsing to the generic "apr" match.
RATE_LABELS = [
    "purchase apr", "cash advance apr", "balance transfer apr", "penalty apr",
    "annual percentage rate", "interest rate", "apr",
]

_MONEY = r"\$?\s*(-?[\d,]+\.\d{2})"
_PERCENT = r"([\d]{1,2}(?:\.\d{1,3})?)\s*%"
# Up to 20 non-digit, non-percent characters between the label and the
# number -- covers "APR: 24.99%", "APR (Purchases) 24.99%", and "your
# current APR is 24.99%" alike without drifting onto an unrelated number
# many sentences later.
_RATE_SEP = r"[^\d%]{0,20}"


@dataclass
class PdfExtractionResult:
    text: str = ""
    balance_candidates: list[tuple[str, float]] = field(default_factory=list)
    date_candidates: list[str] = field(default_factory=list)
    rate_candidates: list[tuple[str, float]] = field(default_factory=list)
    error: str | None = None


def extract_rate_candidates(text: str) -> list[tuple[str, float]]:
    """Interest rate / APR candidates found in statement text -- credit
    card, mortgage, and loan statements routinely print this, so it
    doesn't need to be typed in by hand. Like balance_candidates, this is
    a starting point shown to and confirmed by the user, never applied
    silently: a statement listing separate purchase/cash-advance/balance-
    transfer APRs will surface more than one candidate on purpose,
    since picking the wrong one has real consequences for the debt
    payoff calculations that use it."""
    flat = re.sub(r"\s+", " ", text)
    candidates: list[tuple[str, float]] = []
    seen_values: set[float] = set()
    for label in RATE_LABELS:
        for match in re.finditer(r"\b" + re.escape(label) + r"\b" + _RATE_SEP + _PERCENT, flat, re.IGNORECASE):
            value = float(match.group(1))
            if value in seen_values or value <= 0 or value > 60:
                continue  # 0% or absurdly high isn't a real APR -- likely an unrelated number
            seen_values.add(value)
            candidates.append((label.title(), value))
    return candidates


def extract_pdf_statement(file_bytes: bytes) -> PdfExtractionResult:
    try:
        import pdfplumber
    except ImportError:
        return PdfExtractionResult(error="PDF support isn't installed (pdfplumber missing).")

    try:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts)
    except Exception as exc:  # noqa: BLE001 -- surface any parse failure to the user
        return PdfExtractionResult(error=f"Couldn't read this PDF: {exc}")

    if not text.strip():
        return PdfExtractionResult(error="No extractable text found -- this may be a scanned image PDF.")

    flat = re.sub(r"\s+", " ", text)
    balance_candidates: list[tuple[str, float]] = []
    seen = set()
    for label in BALANCE_LABELS:
        for match in re.finditer(re.escape(label) + r"[:\s]*" + _MONEY, flat, re.IGNORECASE):
            value = float(match.group(1).replace(",", ""))
            key = (label, value)
            if key not in seen:
                seen.add(key)
                balance_candidates.append((label.title(), value))

    date_candidates: list[str] = []
    for label in DATE_LABELS:
        for match in re.finditer(
            re.escape(label) + r"[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+ \d{1,2},? \d{4})",
            flat, re.IGNORECASE,
        ):
            date_candidates.append(match.group(1))

    rate_candidates = extract_rate_candidates(text)

    return PdfExtractionResult(
        text=text, balance_candidates=balance_candidates, date_candidates=date_candidates,
        rate_candidates=rate_candidates,
    )


def parse_flexible_date(value: str):
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%B %d, %Y", "%B %d %Y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(value.strip().rstrip(","), fmt).date()
        except ValueError:
            continue
    return None
