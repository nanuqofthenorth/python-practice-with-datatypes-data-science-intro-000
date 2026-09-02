from datetime import date

import pandas as pd
import streamlit as st

from cfo import db
from cfo.ui import setup_page

setup_page("Transactions")

st.title("Transactions")
st.caption("Income and expenses, categorized.")

add_tab, import_tab, list_tab = st.tabs(["Add manually", "Import CSV", "All transactions"])

with add_tab:
    with st.form("add_txn_form", clear_on_submit=True):
        c1, c2, c3, c4, c5 = st.columns([1, 1.5, 1.3, 1, 1])
        txn_date = c1.date_input("Date", value=date.today())
        description = c2.text_input("Description")
        txn_type = c3.selectbox("Type", ["expense", "income"])
        category_options = db.EXPENSE_CATEGORIES if txn_type == "expense" else db.INCOME_CATEGORIES
        category = c4.selectbox("Category", category_options)
        amount = c5.number_input("Amount", min_value=0.0, step=10.0)
        if st.form_submit_button("Add transaction"):
            if description.strip() and amount > 0:
                db.add_transaction(txn_date.isoformat(), description.strip(), category, txn_type, amount)
                st.success("Transaction added.")
            else:
                st.warning("Enter a description and a positive amount.")

with import_tab:
    st.markdown(
        "Upload a CSV with columns: `date, description, category, type, amount` "
        "(`type` is `income` or `expense`). Rows that don't match are skipped."
    )
    uploaded = st.file_uploader("CSV file", type=["csv"])
    if uploaded is not None:
        try:
            raw = pd.read_csv(uploaded)
            raw.columns = [c.strip().lower() for c in raw.columns]
            rename_map = {"date": "txn_date", "type": "txn_type"}
            raw = raw.rename(columns=rename_map)
            required = {"txn_date", "description", "category", "txn_type", "amount"}
            missing = required - set(raw.columns)
            if missing:
                st.error(f"CSV is missing required columns: {sorted(missing)}")
            else:
                raw["txn_date"] = pd.to_datetime(raw["txn_date"], errors="coerce").dt.date.astype(str)
                raw["txn_type"] = raw["txn_type"].str.strip().str.lower()
                raw = raw[raw["txn_type"].isin(["income", "expense"])]
                raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce").abs()
                raw = raw.dropna(subset=["txn_date", "description", "category", "amount"])
                st.dataframe(raw, use_container_width=True, hide_index=True)
                if st.button(f"Import {len(raw)} transactions"):
                    count = db.add_transactions_bulk(raw)
                    st.success(f"Imported {count} transactions.")
        except Exception as exc:  # noqa: BLE001 -- surface any parse error to the user
            st.error(f"Couldn't read that CSV: {exc}")

with list_tab:
    transactions = db.list_transactions()
    if transactions.empty:
        st.caption("No transactions yet.")
    else:
        f1, f2 = st.columns([1, 1])
        type_filter = f1.multiselect("Type", ["income", "expense"], default=["income", "expense"])
        category_filter = f2.multiselect("Category", sorted(transactions["category"].unique()))

        filtered = transactions[transactions["txn_type"].isin(type_filter)]
        if category_filter:
            filtered = filtered[filtered["category"].isin(category_filter)]

        display = filtered[["id", "txn_date", "description", "category", "txn_type", "amount"]].rename(
            columns={"txn_date": "date", "txn_type": "type"}
        )
        st.dataframe(display.drop(columns=["id"]), use_container_width=True, hide_index=True)

        delete_id = st.selectbox(
            "Delete a transaction by ID", [None] + list(filtered["id"]), format_func=lambda x: "" if x is None else str(x)
        )
        if delete_id and st.button("Delete selected"):
            db.delete_transaction(int(delete_id))
            st.rerun()
