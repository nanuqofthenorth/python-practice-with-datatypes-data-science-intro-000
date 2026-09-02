# Personal CFO

A self-hosted personal finance dashboard: track net worth, budget against
your income, plan debt payoff, and set savings goals -- with a running list
of plain-language insights, the way a CFO would brief you.

## Run it

```bash
cd personal_cfo
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

On first run, click **Load sample data** in the sidebar to explore the app
with realistic example data, or start adding your own accounts and
transactions right away.

## What's inside

- **Dashboard** -- net worth trend, income vs. expenses, spending by
  category, and rule-based insights (savings rate, over-budget categories,
  high-APR debt, goal pacing).
- **Accounts** -- track asset and liability balances; take point-in-time net
  worth snapshots to build the trend line.
- **Transactions** -- log income/expenses manually or import a CSV
  (`date, description, category, type, amount`).
- **Budget** -- set a monthly target per expense category and see budget vs.
  actual for the current month.
- **Debt Payoff** -- simulate the avalanche (highest APR first) or snowball
  (smallest balance first) strategy with an extra monthly payment, and see
  the payoff timeline and total interest.
- **Goals** -- track progress toward savings goals and the monthly
  contribution needed to hit a target date.

## Data & privacy

All data is stored locally in a SQLite file at `personal_cfo/data/cfo.db`.
Nothing is sent anywhere -- this is a single-user, run-it-yourself app with
no accounts, no server, and no external services.

## Tech

Python, [Streamlit](https://streamlit.io) for the UI, SQLite for storage,
[Plotly](https://plotly.com/python/) for charts.
