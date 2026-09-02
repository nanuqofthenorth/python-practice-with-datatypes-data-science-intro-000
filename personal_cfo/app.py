import streamlit as st

from cfo import calculations as calc
from cfo import charts
from cfo import db
from cfo.ui import render_insights, setup_page, stat_tile

setup_page("Dashboard")

st.title("Dashboard")
st.caption("A snapshot of where your money stands today.")

accounts = db.list_accounts()
snapshots = db.list_snapshots()
transactions = db.list_transactions()
budgets = db.list_budgets()
debts = db.list_debts()
goals = db.list_goals()

net_worth = calc.net_worth_summary(accounts)
cash_flow = calc.monthly_cash_flow(transactions)
budget_df = calc.budget_vs_actual(budgets, transactions)

latest_income = cash_flow.iloc[-1]["income"] if not cash_flow.empty else 0.0
latest_expenses = cash_flow.iloc[-1]["expenses"] if not cash_flow.empty else 0.0
latest_savings_rate = cash_flow.iloc[-1]["savings_rate"] if not cash_flow.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
with col1:
    stat_tile("Net Worth", f"${net_worth['net_worth']:,.0f}")
with col2:
    stat_tile("This Month's Income", f"${latest_income:,.0f}")
with col3:
    stat_tile("This Month's Expenses", f"${latest_expenses:,.0f}")
with col4:
    stat_tile("Savings Rate", f"{latest_savings_rate:.0%}")

st.divider()

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Net worth trend")
    st.plotly_chart(charts.net_worth_trend_chart(snapshots), use_container_width=True, config={"displayModeBar": False})

    st.subheader("Income vs. expenses")
    st.plotly_chart(charts.income_vs_expenses_chart(cash_flow), use_container_width=True, config={"displayModeBar": False})

with right:
    st.subheader("Spending by category")
    spending = calc.spending_by_category(transactions, month=calc.current_month_key())
    st.plotly_chart(charts.spending_by_category_chart(spending), use_container_width=True, config={"displayModeBar": False})

st.divider()
st.subheader("Insights")
insights = calc.generate_insights(net_worth, cash_flow, budget_df, debts, goals)
render_insights(insights)

if not db.has_any_data():
    st.info("This dashboard is empty. Use **Load sample data** in the sidebar, or start adding your own "
            "accounts, transactions, and debts using the pages in the sidebar.")
