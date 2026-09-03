from __future__ import annotations

import streamlit as st

from cfo import db
from cfo.import_ui import render_statement_import
from cfo.ui import setup_page

setup_page("Import Statements")

st.title("Import Statements")
st.caption(
    "Upload a CSV/Excel export or a PDF statement from a bank, brokerage, credit card, "
    "mortgage, or HELOC -- match it to an account and we'll pull out the transactions and balance."
)
st.caption(
    "First time setting up? The **Setup Wizard** walks through uploading several statements at "
    "once and creates each account for you -- this page is for importing into an account you "
    "already have."
)

accounts = db.list_accounts()

# A widget's own session_state key can't be written to after that widget
# has already run this script -- so a newly-created account's id is
# staged here (set right before the st.rerun() below) and consumed into
# the selectbox's real key on the *next* run, before the selectbox is
# instantiated. Without this two-step handoff, "Create account" either
# raises StreamlitWidgetAlreadyInstantiatedError or (if the state write is
# skipped) silently resets to "+ Create a new account" every time,
# trapping the user in a loop that creates a duplicate account per click.
if "_pending_account_choice" in st.session_state:
    st.session_state["import_account_choice"] = st.session_state.pop("_pending_account_choice")

st.subheader("1. Which account is this statement for?")
NEW_ACCOUNT = -1
account_options = {int(r["id"]): f"{r['name']} ({r['category']})" for _, r in accounts.iterrows()}
choice = st.selectbox(
    "Account",
    options=[NEW_ACCOUNT] + list(account_options.keys()),
    format_func=lambda x: "+ Create a new account" if x == NEW_ACCOUNT else account_options[x],
    key="import_account_choice",
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
                new_id = db.add_account(name.strip(), kind, category, 0.0, rate)
                st.session_state["_pending_account_choice"] = new_id
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

if render_statement_import(uploaded.getvalue(), uploaded.name, selected_account, key_prefix="single"):
    st.balloons()
