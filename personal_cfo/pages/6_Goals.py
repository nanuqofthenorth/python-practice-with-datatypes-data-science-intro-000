from datetime import date, timedelta

import streamlit as st

from cfo import calculations as calc
from cfo import db
from cfo.ui import setup_page

setup_page("Goals")

st.title("Goals")
st.caption("Track progress toward what matters -- an emergency fund, a trip, a down payment.")

goals = db.list_goals()

if goals.empty:
    st.caption("No goals yet -- add one below.")
else:
    for _, g in goals.iterrows():
        pct = min(g["current_amount"] / g["target_amount"], 1.0) if g["target_amount"] > 0 else 0.0
        needed = calc.goal_required_monthly_contribution(g["target_amount"], g["current_amount"], g["target_date"])

        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{g['name']}**")
            if top[1].button("Delete", key=f"del_goal_{g['id']}"):
                db.delete_goal(int(g["id"]))
                st.rerun()

            st.progress(pct, text=f"${g['current_amount']:,.0f} of ${g['target_amount']:,.0f} ({pct:.0%})")

            info_cols = st.columns(3)
            if g["target_date"]:
                info_cols[0].caption(f"Target date: {g['target_date']}")
            if needed is not None and pct < 1.0:
                info_cols[1].caption(f"Needs ~${needed:,.0f}/month to hit target")
            if pct >= 1.0:
                info_cols[2].caption("Fully funded")

            new_amount = st.number_input(
                "Update saved amount", min_value=0.0, step=50.0,
                value=float(g["current_amount"]), key=f"goal_amt_{g['id']}",
            )
            if new_amount != g["current_amount"]:
                db.update_goal_progress(int(g["id"]), new_amount)
                st.rerun()

st.divider()
with st.form("add_goal_form", clear_on_submit=True):
    st.markdown("**Add a goal**")
    c1, c2, c3, c4 = st.columns(4)
    name = c1.text_input("Name")
    target_amount = c2.number_input("Target amount", min_value=0.0, step=100.0)
    current_amount = c3.number_input("Already saved", min_value=0.0, step=50.0)
    target_date = c4.date_input("Target date", value=date.today() + timedelta(days=180))
    if st.form_submit_button("Add goal"):
        if name.strip() and target_amount > 0:
            db.add_goal(name.strip(), target_amount, current_amount, target_date.isoformat())
            st.rerun()
        else:
            st.warning("Enter a name and a positive target amount.")
