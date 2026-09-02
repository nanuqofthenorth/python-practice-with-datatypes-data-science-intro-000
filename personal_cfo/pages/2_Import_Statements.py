from __future__ import annotations

from datetime import date

import streamlit as st

from cfo import calculations as calc
from cfo import db
from cfo import importers as imp
from cfo.ui import setup_page

setup_page("Import Statements")

st.title("Import Statements")
st.caption(
    "Upload a CSV/Excel export or a PDF statement from a bank, brokerage, credit card, "
    "mortgage, or HELOC -- match it to an account and we'll pull out the transactions and balance."
)


def _safe_index(options: list, value, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return list(options).index(value)
    except ValueError:
        return default


accounts = db.list_accounts()

st.subheader("1. Which account is this statement for?")
NEW_ACCOUNT = -1
account_options = {int(r["id"]): f"{r['name']} ({r['category']})" for _, r in accounts.iterrows()}
choice = st.selectbox(
    "Account",
    options=[NEW_ACCOUNT] + list(account_options.keys()),
    format_func=lambda x: "+ Create a new account" if x == NEW_ACCOUNT else account_options[x],
)

if choice == NEW_ACCOUNT:
    with st.form("new_account_inline"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Account name")
        kind = c2.selectbox(
            "Type", ["asset", "liability"],
            format_func=lambda k: "Asset (I own this)" if k == "asset" else "Liability (I owe this)",
        )
        categories = db.ASSET_CATEGORIES if kind == "asset" else db.LIABILITY_CATEGORIES
        category = c3.selectbox("Category", categories)
        rate = st.number_input("Interest rate (%)", min_value=0.0, step=0.1) if kind == "liability" else 0.0
        if st.form_submit_button("Create account"):
            if name.strip():
                db.add_account(name.strip(), kind, category, 0.0, rate)
                st.rerun()
            else:
                st.warning("Enter an account name.")
    st.stop()

selected_account = db.get_account(choice)
st.caption(f"Importing into **{selected_account['name']}** -- current balance ${selected_account['balance']:,.0f}")

st.divider()
st.subheader("2. Upload the statement")
uploaded = st.file_uploader("CSV, Excel (.xlsx), or PDF", type=["csv", "xlsx", "xls", "pdf"])

if uploaded is None:
    st.info(
        "Most banks and brokerages let you export a CSV or Excel file of transactions from "
        "their website. Credit card, mortgage, and HELOC issuers usually offer a PDF statement -- "
        "we'll pull the balance from that even though we can't extract line-item transactions from it."
    )
    st.stop()

file_bytes = uploaded.getvalue()
is_pdf = uploaded.name.lower().endswith(".pdf")

# ------------------------------------------------------------------- PDF
if is_pdf:
    result = imp.extract_pdf_statement(file_bytes)
    if result.error:
        st.error(result.error)
        st.stop()

    st.subheader("3. Confirm the balance")
    if not result.balance_candidates:
        st.warning("Couldn't automatically find a balance in this PDF -- enter it manually.")
        chosen_balance = st.number_input(
            "Statement balance", min_value=0.0, step=10.0, value=float(selected_account["balance"])
        )
    else:
        labels = [f"{label}: ${value:,.2f}" for label, value in result.balance_candidates]
        idx = st.radio(
            "Found these balances in the statement -- pick the right one:",
            options=list(range(len(labels))), format_func=lambda i: labels[i],
        )
        chosen_balance = st.number_input(
            "Balance to apply (edit if needed)", min_value=0.0, step=10.0,
            value=float(result.balance_candidates[idx][1]),
        )

    detected_date = imp.parse_flexible_date(result.date_candidates[0]) if result.date_candidates else None
    statement_date = st.date_input("Statement date", value=detected_date or date.today())

    with st.expander("Extracted text (for reference)"):
        st.text(result.text[:5000])

    st.subheader("4. Apply")
    if st.button("Update account balance", type="primary"):
        db.update_account_balance(int(selected_account["id"]), chosen_balance)
        nw = calc.net_worth_summary(db.list_accounts())
        db.record_snapshot(statement_date.isoformat(), nw["total_assets"], nw["total_liabilities"])
        st.success(
            f"Updated {selected_account['name']} to ${chosen_balance:,.2f} and recorded a snapshot "
            f"for {statement_date.isoformat()}."
        )
        st.balloons()

    st.caption(
        "PDF statements rarely have a machine-readable transaction table, so line items aren't "
        "extracted automatically. If you need itemized transactions, check whether your institution "
        "also offers a CSV/Excel export."
    )

# ------------------------------------------------------------- CSV / XLSX
else:
    try:
        raw_df = imp.read_statement_table(file_bytes, uploaded.name)
    except Exception as exc:  # noqa: BLE001 -- surface any parse failure to the user
        st.error(f"Couldn't read this file: {exc}")
        st.stop()

    if raw_df.empty:
        st.error("No rows found in this file.")
        st.stop()

    st.subheader("3. Confirm columns")
    st.caption("We guessed these from the file's headers -- adjust anything that looks wrong.")
    with st.expander("Raw file preview"):
        st.dataframe(raw_df.head(5), use_container_width=True, hide_index=True)

    mapping = imp.detect_columns(raw_df)
    columns = list(raw_df.columns)

    c1, c2 = st.columns(2)
    date_col = c1.selectbox("Date column", columns, index=_safe_index(columns, mapping.date_col))
    description_col = c2.selectbox("Description column", columns, index=_safe_index(columns, mapping.description_col))

    use_split = st.checkbox(
        "This file has separate Debit and Credit columns (instead of one signed Amount column)",
        value=mapping.debit_col is not None and mapping.credit_col is not None,
    )
    if use_split:
        c3, c4 = st.columns(2)
        debit_col = c3.selectbox("Debit column", columns, index=_safe_index(columns, mapping.debit_col))
        credit_col = c4.selectbox("Credit column", columns, index=_safe_index(columns, mapping.credit_col, default=min(1, len(columns) - 1)))
        amount_col = None
    else:
        amount_col = st.selectbox("Amount column", columns, index=_safe_index(columns, mapping.amount_col))
        debit_col = credit_col = None

    balance_options = ["(none)"] + columns
    balance_choice = st.selectbox(
        "Balance column (optional -- used to update the account balance)",
        balance_options, index=_safe_index(balance_options, mapping.balance_col),
    )
    balance_col = None if balance_choice == "(none)" else balance_choice

    flip_sign = st.checkbox("Flip amount sign (use this if expenses show up as income below)")

    final_mapping = imp.ColumnMapping(
        date_col=date_col, description_col=description_col, amount_col=amount_col,
        debit_col=debit_col, credit_col=credit_col, balance_col=balance_col,
    )

    try:
        normalized = imp.normalize_transactions(raw_df, final_mapping, flip_sign=flip_sign)
    except Exception as exc:  # noqa: BLE001 -- bad column choice, not a bug
        st.error(f"Couldn't parse with these columns: {exc}")
        st.stop()

    if normalized.empty:
        st.warning("No valid transactions parsed with this mapping -- check the column selections above.")
        st.stop()

    fingerprints = db.transaction_fingerprints()
    normalized["is_duplicate"] = normalized.apply(
        lambda r: (r["txn_date"], r["description"].strip().lower(), round(r["amount"], 2)) in fingerprints,
        axis=1,
    )
    normalized["Import"] = ~(normalized["is_duplicate"] | normalized["is_transfer"])

    st.subheader("4. Review transactions")
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
    )

    detected_balance = imp.extract_ending_balance_from_table(raw_df, final_mapping)
    update_balance = False
    new_balance_value = float(selected_account["balance"])
    if detected_balance is not None:
        update_balance = st.checkbox(
            f"Also update {selected_account['name']}'s balance to ${detected_balance:,.2f} "
            "(from this file's balance column)",
            value=True,
        )
        new_balance_value = detected_balance

    to_import = edited[edited["Import"]]
    st.subheader("5. Import")
    st.caption(f"{len(to_import)} of {len(edited)} transactions selected.")
    if st.button("Import", type="primary", disabled=to_import.empty and not update_balance):
        count = 0
        if not to_import.empty:
            bulk = to_import.rename(columns={
                "Date": "txn_date", "Description": "description", "Category": "category",
                "Type": "txn_type", "Amount": "amount",
            })
            count = db.add_transactions_bulk(bulk[["txn_date", "description", "category", "txn_type", "amount"]])
        if update_balance:
            db.update_account_balance(int(selected_account["id"]), new_balance_value)
            nw = calc.net_worth_summary(db.list_accounts())
            db.record_snapshot(date.today().isoformat(), nw["total_assets"], nw["total_liabilities"])
        st.success(
            f"Imported {count} transaction(s)"
            + (f" and updated {selected_account['name']}'s balance." if update_balance else ".")
        )
        st.balloons()
