from __future__ import annotations

from datetime import date

import streamlit as st

from cfo import calculations as calc
from cfo import db
from cfo.ui import setup_page, stat_tile

setup_page("Accounts")

st.title("Accounts")
st.caption("Everything you own and everything you owe.")

accounts = db.list_accounts()
summary = calc.net_worth_summary(accounts)

c1, c2, c3 = st.columns(3)
with c1:
    stat_tile("Total Assets", f"${summary['total_assets']:,.0f}")
with c2:
    stat_tile("Total Liabilities", f"${summary['total_liabilities']:,.0f}")
with c3:
    stat_tile("Net Worth", f"${summary['net_worth']:,.0f}")

if st.button("Take net worth snapshot", help="Records today's total assets/liabilities so the dashboard trend line updates."):
    db.record_snapshot(date.today().isoformat(), summary["total_assets"], summary["total_liabilities"])
    st.success(f"Snapshot recorded for {date.today().isoformat()}.")

st.divider()

tab_assets, tab_liabilities = st.tabs(["Assets", "Liabilities"])

for tab, kind, categories in (
    (tab_assets, "asset", db.ASSET_CATEGORIES),
    (tab_liabilities, "liability", db.LIABILITY_CATEGORIES),
):
    with tab:
        subset = accounts[accounts["kind"] == kind] if not accounts.empty else accounts
        if subset.empty:
            st.caption("No accounts yet.")
        else:
            for _, row in subset.iterrows():
                cols = st.columns([2.5, 1.5, 1.5, 1, 0.7])
                cols[0].markdown(f"**{row['name']}**  \n:gray[{row['category']}]")
                new_balance = cols[1].number_input(
                    "Balance", value=float(row["balance"]), key=f"bal_{row['id']}", label_visibility="collapsed"
                )
                if row["interest_rate"]:
                    cols[2].markdown(f"APR: {row['interest_rate']:.2f}%")
                if new_balance != row["balance"]:
                    db.update_account_balance(int(row["id"]), new_balance)
                    st.rerun()
                if cols[4].button("Delete", key=f"del_{row['id']}"):
                    db.delete_account(int(row["id"]))
                    st.rerun()

        with st.form(f"add_{kind}_form", clear_on_submit=True):
            st.markdown(f"**Add {'asset' if kind == 'asset' else 'liability'}**")
            fc1, fc2, fc3, fc4 = st.columns(4)
            name = fc1.text_input("Name")
            category = fc2.selectbox("Category", categories)
            balance = fc3.number_input("Balance", min_value=0.0, step=100.0)
            rate = fc4.number_input("Interest rate (%)", min_value=0.0, step=0.1) if kind == "liability" else 0.0
            if st.form_submit_button("Add account"):
                if name.strip():
                    db.add_account(name.strip(), kind, category, balance, rate)
                    st.rerun()
                else:
                    st.warning("Enter a name for the account.")
