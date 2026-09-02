from __future__ import annotations

import pandas as pd
import streamlit as st

from cfo import calculations as calc
from cfo import charts
from cfo import db
from cfo.ui import is_dark_theme, setup_page

setup_page("Budget")
dark = is_dark_theme()

st.title("Budget")
st.caption("Set a monthly target per category and see how you're tracking.")

budgets = db.list_budgets()
transactions = db.list_transactions()
month = calc.current_month_key()
budget_df = calc.budget_vs_actual(budgets, transactions, month=month)

st.subheader(f"Budget vs. actual -- {month}")
st.plotly_chart(charts.budget_vs_actual_chart(budget_df, dark=dark), use_container_width=True, config={"displayModeBar": False})

if not budget_df.empty:
    display = budget_df.copy()
    display["pct_used"] = display["pct_used"].apply(lambda v: "--" if pd.isna(v) else f"{v:.0%}")
    display = display.rename(columns={
        "category": "Category", "budgeted": "Budgeted", "actual": "Actual",
        "variance": "Remaining", "pct_used": "% Used",
    })
    st.dataframe(
        display[["Category", "Budgeted", "Actual", "Remaining", "% Used"]],
        use_container_width=True, hide_index=True,
    )

st.divider()
st.subheader("Set budgets")

existing = {row["category"]: row for _, row in budgets.iterrows()} if not budgets.empty else {}
with st.form("budget_form"):
    updates = {}
    cols = st.columns(3)
    for i, category in enumerate(db.EXPENSE_CATEGORIES):
        default = float(existing[category]["monthly_amount"]) if category in existing else 0.0
        with cols[i % 3]:
            updates[category] = st.number_input(category, min_value=0.0, step=25.0, value=default, key=f"budget_{category}")
    if st.form_submit_button("Save budgets"):
        for category, amount in updates.items():
            if amount > 0:
                db.set_budget(category, amount)
        st.success("Budgets saved.")
        st.rerun()
