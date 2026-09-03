from __future__ import annotations

import streamlit as st

from cfo import db
from cfo.account_guess import guess_account_from_filename
from cfo.import_ui import render_statement_import
from cfo.ui import setup_page

setup_page("Setup Wizard")

st.title("Setup Wizard")
st.caption(
    "Upload your statements and we'll create the right accounts and import the transactions -- "
    "reviewing everything with you before anything is saved, same as Import Statements. Prefer to "
    "build things up by hand? Use **Accounts** and **Transactions** in the sidebar instead."
)

for key, default in (
    ("wizard_queue", []), ("wizard_index", 0), ("wizard_created", []),
):
    if key not in st.session_state:
        st.session_state[key] = default

queue: list[tuple[str, bytes]] = st.session_state["wizard_queue"]
index: int = st.session_state["wizard_index"]


def _reset_wizard() -> None:
    st.session_state["wizard_queue"] = []
    st.session_state["wizard_index"] = 0
    st.session_state["wizard_created"] = []


# ------------------------------------------------------------- step 1: upload
if not queue:
    st.subheader("1. Upload your statements")
    st.caption(
        "One or more CSV/Excel exports or PDF statements -- bank, brokerage, credit card, mortgage, "
        "or HELOC. We'll go through them one at a time."
    )
    uploaded_files = st.file_uploader(
        "Statements", type=["csv", "xlsx", "xls", "pdf"], accept_multiple_files=True,
    )
    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected.")
        if st.button("Start setup", type="primary"):
            st.session_state["wizard_queue"] = [(f.name, f.getvalue()) for f in uploaded_files]
            st.session_state["wizard_index"] = 0
            st.session_state["wizard_created"] = []
            st.rerun()
    st.stop()

# ------------------------------------------------------------ step done: summary
if index >= len(queue):
    st.success(f"All set! Created {len(st.session_state['wizard_created'])} account(s).")
    for item in st.session_state["wizard_created"]:
        st.markdown(f"- **{item['name']}**")
    st.caption(
        "You can always add more accounts, log transactions by hand, or run the wizard again from "
        "the sidebar."
    )
    c1, c2 = st.columns(2)
    if c1.button("Go to Accounts", type="primary"):
        _reset_wizard()
        st.switch_page("pages/1_Accounts.py")
    if c2.button("Import more statements"):
        _reset_wizard()
        st.rerun()
    st.stop()

# --------------------------------------------------- processing the current file
filename, file_bytes = queue[index]
st.subheader(f"File {index + 1} of {len(queue)}: {filename}")
st.progress(index / len(queue))

account_key = f"wizard_account_id_{index}"

if account_key not in st.session_state:
    guess = guess_account_from_filename(filename)
    st.markdown("**2. Confirm this account**")
    if not guess.confident:
        st.caption("Couldn't guess the account type from this filename -- double check these before continuing.")

    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Account name", value=guess.name, key=f"wizard_name_{index}")
    kind = c2.selectbox(
        "Type", ["asset", "liability"],
        index=0 if guess.kind == "asset" else 1,
        format_func=lambda k: "Asset (I own this)" if k == "asset" else "Liability (I owe this)",
        key=f"wizard_kind_{index}",
    )
    categories = db.ASSET_CATEGORIES if kind == "asset" else db.LIABILITY_CATEGORIES
    default_category = guess.category if guess.category in categories else categories[0]
    category = c3.selectbox(
        "Category", categories, index=categories.index(default_category), key=f"wizard_category_{index}",
    )
    rate = (
        st.number_input("Interest rate (%)", min_value=0.0, step=0.1, key=f"wizard_rate_{index}")
        if kind == "liability" else 0.0
    )

    b1, b2 = st.columns([1, 1])
    if b1.button("Use this account", type="primary", key=f"wizard_confirm_{index}"):
        if name.strip():
            new_id = db.add_account(name.strip(), kind, category, 0.0, rate)
            st.session_state[account_key] = new_id
            st.rerun()
        else:
            st.warning("Enter an account name.")
    if b2.button("Skip this file", key=f"wizard_skip_{index}"):
        st.session_state["wizard_index"] += 1
        st.rerun()
    st.stop()

account = db.get_account(st.session_state[account_key])
st.caption(f"Importing into **{account['name']}**")

st.markdown("**3. Review and import**")
completed = render_statement_import(file_bytes, filename, account, key_prefix=f"wizard_{index}")
if completed:
    st.session_state["wizard_created"].append({"name": account["name"]})
    st.session_state["wizard_index"] += 1
    del st.session_state[account_key]
    st.rerun()

if st.button("Start over", key=f"wizard_start_over_{index}"):
    _reset_wizard()
    st.rerun()
