"""Shared Streamlit UI for turning one uploaded statement file into either
an account balance update (PDF) or reviewed, imported transactions
(CSV/Excel) -- used by both the Import Statements page (importing into an
account you've already set up) and the Setup Wizard (importing into an
account it just created for you). Keeping this in one place means a fix
or a new column-detection heuristic only has to happen once.

Nothing here writes to the database until the user reviews what was
parsed and clicks a button -- same principle as everywhere else file
data enters this app.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from . import calculations as calc
from . import db
from . import importers as imp


def _safe_index(options: list, value, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return list(options).index(value)
    except ValueError:
        return default


def render_statement_import(file_bytes: bytes, filename: str, account: pd.Series, key_prefix: str) -> bool:
    """Renders the full parse -> review -> import flow for one statement
    file against one account (already created/selected by the caller).
    `key_prefix` must be unique per file when this is called more than
    once on the same page (the Setup Wizard processes several files in
    one session) so Streamlit widget keys don't collide across files.

    Returns True the run an import/update action actually happened, so a
    multi-file caller like the Setup Wizard knows to move on to the next
    file; False otherwise (still reviewing, or nothing to do yet)."""
    is_pdf = filename.lower().endswith(".pdf")

    if is_pdf:
        return _render_pdf_import(file_bytes, account, key_prefix)
    return _render_table_import(file_bytes, filename, account, key_prefix)


def _render_pdf_import(file_bytes: bytes, account: pd.Series, key_prefix: str) -> bool:
    result = imp.extract_pdf_statement(file_bytes)
    if result.error:
        st.error(result.error)
        return False

    st.subheader("Confirm the balance")
    if not result.balance_candidates:
        st.warning("Couldn't automatically find a balance in this PDF -- enter it manually.")
        chosen_balance = st.number_input(
            "Statement balance", min_value=0.0, step=10.0, value=float(account["balance"]),
            key=f"{key_prefix}_pdf_balance_manual",
        )
    else:
        labels = [f"{label}: ${value:,.2f}" for label, value in result.balance_candidates]
        idx = st.radio(
            "Found these balances in the statement -- pick the right one:",
            options=list(range(len(labels))), format_func=lambda i: labels[i],
            key=f"{key_prefix}_pdf_balance_choice",
        )
        chosen_balance = st.number_input(
            "Balance to apply (edit if needed)", min_value=0.0, step=10.0,
            value=float(result.balance_candidates[idx][1]), key=f"{key_prefix}_pdf_balance_edit",
        )

    detected_date = imp.parse_flexible_date(result.date_candidates[0]) if result.date_candidates else None
    statement_date = st.date_input(
        "Statement date", value=detected_date or date.today(), key=f"{key_prefix}_pdf_date"
    )

    with st.expander("Extracted text (for reference)"):
        st.text(result.text[:5000])

    st.subheader("Apply")
    if st.button("Update account balance", type="primary", key=f"{key_prefix}_pdf_apply"):
        db.update_account_balance(int(account["id"]), chosen_balance)
        nw = calc.net_worth_summary(db.list_accounts())
        db.record_snapshot(statement_date.isoformat(), nw["total_assets"], nw["total_liabilities"])
        st.success(f"Updated {account['name']} to ${chosen_balance:,.2f}.")
        return True

    st.caption(
        "PDF statements rarely have a machine-readable transaction table, so line items aren't "
        "extracted automatically. If you need itemized transactions, check whether your institution "
        "also offers a CSV/Excel export."
    )
    return False


def _render_table_import(file_bytes: bytes, filename: str, account: pd.Series, key_prefix: str) -> bool:
    try:
        raw_df = imp.read_statement_table(file_bytes, filename)
    except Exception as exc:  # noqa: BLE001 -- surface any parse failure to the user
        st.error(f"Couldn't read this file: {exc}")
        return False

    if raw_df.empty:
        st.error("No rows found in this file.")
        return False

    st.subheader("Confirm columns")
    st.caption("We guessed these from the file's headers -- adjust anything that looks wrong.")
    with st.expander("Raw file preview"):
        st.dataframe(raw_df.head(5), use_container_width=True, hide_index=True)

    mapping = imp.detect_columns(raw_df)
    columns = list(raw_df.columns)

    c1, c2 = st.columns(2)
    date_col = c1.selectbox("Date column", columns, index=_safe_index(columns, mapping.date_col), key=f"{key_prefix}_date_col")
    description_col = c2.selectbox(
        "Description column", columns, index=_safe_index(columns, mapping.description_col), key=f"{key_prefix}_desc_col"
    )

    use_split = st.checkbox(
        "This file has separate Debit and Credit columns (instead of one signed Amount column)",
        value=mapping.debit_col is not None and mapping.credit_col is not None,
        key=f"{key_prefix}_use_split",
    )
    if use_split:
        c3, c4 = st.columns(2)
        debit_col = c3.selectbox("Debit column", columns, index=_safe_index(columns, mapping.debit_col), key=f"{key_prefix}_debit_col")
        credit_col = c4.selectbox(
            "Credit column", columns, index=_safe_index(columns, mapping.credit_col, default=min(1, len(columns) - 1)),
            key=f"{key_prefix}_credit_col",
        )
        amount_col = None
    else:
        amount_col = st.selectbox("Amount column", columns, index=_safe_index(columns, mapping.amount_col), key=f"{key_prefix}_amount_col")
        debit_col = credit_col = None

    balance_options = ["(none)"] + columns
    balance_choice = st.selectbox(
        "Balance column (optional -- used to update the account balance)",
        balance_options, index=_safe_index(balance_options, mapping.balance_col), key=f"{key_prefix}_balance_col",
    )
    balance_col = None if balance_choice == "(none)" else balance_choice

    flip_sign = st.checkbox("Flip amount sign (use this if expenses show up as income below)", key=f"{key_prefix}_flip_sign")

    final_mapping = imp.ColumnMapping(
        date_col=date_col, description_col=description_col, amount_col=amount_col,
        debit_col=debit_col, credit_col=credit_col, balance_col=balance_col,
    )

    try:
        normalized = imp.normalize_transactions(raw_df, final_mapping, flip_sign=flip_sign)
    except Exception as exc:  # noqa: BLE001 -- bad column choice, not a bug
        st.error(f"Couldn't parse with these columns: {exc}")
        return False

    if normalized.empty:
        st.warning("No valid transactions parsed with this mapping -- check the column selections above.")
        return False

    fingerprints = db.transaction_fingerprints()
    normalized["is_duplicate"] = normalized.apply(
        lambda r: (r["txn_date"], r["description"].strip().lower(), round(r["amount"], 2)) in fingerprints,
        axis=1,
    )
    normalized["Import"] = ~(normalized["is_duplicate"] | normalized["is_transfer"])

    st.subheader("Review transactions")
    n_dup = int(normalized["is_duplicate"].sum())
    n_transfer = int(normalized["is_transfer"].sum())
    st.caption(
        f"{len(normalized)} rows parsed. {n_dup} look like duplicates already in your ledger and "
        f"{n_transfer} look like payments/transfers -- both start unchecked. Review categories and "
        "the Import column before importing."
    )

    display_df = normalized[["Import", "txn_date", "description", "category", "txn_type", "amount", "is_duplicate", "is_transfer"]].rename(
        columns={
            "txn_date": "Date", "description": "Description", "category": "Category",
            "txn_type": "Type", "amount": "Amount",
            "is_duplicate": "Possible duplicate", "is_transfer": "Possible transfer",
        }
    )
    all_categories = sorted(set(db.EXPENSE_CATEGORIES + db.INCOME_CATEGORIES))
    edited = st.data_editor(
        display_df,
        column_config={
            "Import": st.column_config.CheckboxColumn(),
            "Category": st.column_config.SelectboxColumn(options=all_categories),
            "Type": st.column_config.SelectboxColumn(options=["income", "expense"]),
            "Amount": st.column_config.NumberColumn(format="$%.2f"),
        },
        disabled=["Date", "Description", "Possible duplicate", "Possible transfer"],
        hide_index=True,
        use_container_width=True,
        height=min(500, 38 * (len(display_df) + 1)),
        key=f"{key_prefix}_editor",
    )

    detected_balance = imp.extract_ending_balance_from_table(raw_df, final_mapping)
    update_balance = False
    new_balance_value = float(account["balance"])
    if detected_balance is not None:
        update_balance = st.checkbox(
            f"Also update {account['name']}'s balance to ${detected_balance:,.2f} (from this file's balance column)",
            value=True, key=f"{key_prefix}_update_balance",
        )
        new_balance_value = detected_balance

    to_import = edited[edited["Import"]]
    st.subheader("Import")
    st.caption(f"{len(to_import)} of {len(edited)} transactions selected.")
    if st.button("Import", type="primary", disabled=to_import.empty and not update_balance, key=f"{key_prefix}_import"):
        count = 0
        if not to_import.empty:
            bulk = to_import.rename(columns={
                "Date": "txn_date", "Description": "description", "Category": "category",
                "Type": "txn_type", "Amount": "amount",
            })
            count = db.add_transactions_bulk(bulk[["txn_date", "description", "category", "txn_type", "amount"]])
        if update_balance:
            db.update_account_balance(int(account["id"]), new_balance_value)
            nw = calc.net_worth_summary(db.list_accounts())
            db.record_snapshot(date.today().isoformat(), nw["total_assets"], nw["total_liabilities"])
        st.success(
            f"Imported {count} transaction(s)" + (f" and updated {account['name']}'s balance." if update_balance else ".")
        )
        return True

    return False
