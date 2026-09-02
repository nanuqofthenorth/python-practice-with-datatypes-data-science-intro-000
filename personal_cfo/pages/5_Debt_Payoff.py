from datetime import datetime, timedelta

import streamlit as st

from cfo import calculations as calc
from cfo import calendar_export as cal
from cfo import charts
from cfo import db
from cfo.ui import is_dark_theme, setup_page, stat_tile

setup_page("Debt Payoff")
dark = is_dark_theme()

st.title("Debt Payoff")
st.caption("Compare payoff strategies and see how extra payments shorten your timeline.")

debts = db.list_debts()

if debts.empty:
    st.caption("No debts yet -- add one below.")
else:
    total_balance = debts["balance"].sum()
    total_min_payment = debts["min_payment"].sum()
    c1, c2 = st.columns(2)
    with c1:
        stat_tile("Total Debt", f"${total_balance:,.0f}")
    with c2:
        stat_tile("Total Minimum Payments", f"${total_min_payment:,.0f}/mo")

    st.divider()
    st.subheader("Payoff simulator")

    s1, s2 = st.columns(2)
    strategy_label = s1.radio(
        "Strategy",
        ["Avalanche (highest APR first)", "Snowball (smallest balance first)"],
        help="Avalanche minimizes total interest paid. Snowball builds momentum by clearing small balances fast.",
    )
    strategy = "avalanche" if strategy_label.startswith("Avalanche") else "snowball"
    extra_payment = s2.number_input("Extra monthly payment (beyond minimums)", min_value=0.0, step=25.0, value=100.0)

    result = calc.simulate_debt_payoff(debts, extra_monthly_payment=extra_payment, strategy=strategy)

    r1, r2 = st.columns(2)
    with r1:
        years = result.months_to_debt_free // 12
        months = result.months_to_debt_free % 12
        stat_tile("Debt-free in", f"{years}y {months}m" if years else f"{months} months")
    with r2:
        stat_tile("Total Interest Paid", f"${result.total_interest_paid:,.0f}")

    st.plotly_chart(charts.debt_payoff_chart(result.schedule, dark=dark), use_container_width=True, config={"displayModeBar": False})

    st.caption(
        "Payoff order: " + " -> ".join(
            sorted(result.payoff_month_by_debt, key=lambda n: result.payoff_month_by_debt[n])
        ) if result.payoff_month_by_debt else ""
    )

    if extra_payment > 0 and result.months_to_debt_free > 0:
        target_debt = min(result.payoff_month_by_debt, key=lambda n: result.payoff_month_by_debt[n]) if result.payoff_month_by_debt else None
        reminder_start = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        event = cal.CalendarEvent(
            title="Make extra debt payment",
            description=(
                f"Pay an extra ${extra_payment:,.0f} this month toward "
                f"{target_debt or 'your debt'} ({strategy_label.split(' (')[0]} order) to stay on the "
                f"{result.months_to_debt_free}-month debt-free plan."
            ),
            start=reminder_start,
            recurrence_monthly_count=result.months_to_debt_free,
        )
        st.download_button(
            "Remind me monthly to make this payment", cal.build_ics([event]),
            file_name="debt-payoff-reminder.ics", mime="text/calendar", key="debt_reminder",
        )

st.divider()
st.subheader("Your debts")

if not debts.empty:
    for _, row in debts.iterrows():
        cols = st.columns([2, 1.3, 1, 1.3, 0.7])
        cols[0].markdown(f"**{row['name']}**")
        cols[1].markdown(f"${row['balance']:,.0f}")
        cols[2].markdown(f"{row['apr']:.2f}% APR")
        cols[3].markdown(f"${row['min_payment']:,.0f}/mo min")
        if cols[4].button("Delete", key=f"del_debt_{row['id']}"):
            db.delete_debt(int(row["id"]))
            st.rerun()

with st.form("add_debt_form", clear_on_submit=True):
    st.markdown("**Add a debt**")
    c1, c2, c3, c4 = st.columns(4)
    name = c1.text_input("Name")
    balance = c2.number_input("Balance", min_value=0.0, step=100.0)
    apr = c3.number_input("APR (%)", min_value=0.0, step=0.1)
    min_payment = c4.number_input("Minimum payment", min_value=0.0, step=10.0)
    if st.form_submit_button("Add debt"):
        if name.strip() and balance > 0:
            db.add_debt(name.strip(), balance, apr, min_payment)
            st.rerun()
        else:
            st.warning("Enter a name and a positive balance.")
