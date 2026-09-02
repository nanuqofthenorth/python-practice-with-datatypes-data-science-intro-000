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
- **Import Statements** -- upload a CSV/Excel export or PDF statement from a
  bank, brokerage, credit card, mortgage, or HELOC. Auto-detects columns,
  guesses categories, flags likely duplicates and payment/transfer rows,
  and can update the linked account's balance (from a balance column in a
  CSV, or extracted from PDF text). You review and adjust everything before
  anything is saved.
- **Transactions** -- log income/expenses manually, or see everything
  that's been imported.
- **Budget** -- set a monthly target per expense category and see budget vs.
  actual for the current month.
- **Debt Payoff** -- simulate the avalanche (highest APR first) or snowball
  (smallest balance first) strategy with an extra monthly payment, and see
  the payoff timeline and total interest.
- **Goals** -- track progress toward savings goals and the monthly
  contribution needed to hit a target date.

## Importing statements

Most banks and brokerages let you export a CSV or Excel (.xlsx) file of
transactions from their website -- Import Statements auto-detects the date,
description, and amount columns (or separate debit/credit columns), guesses
a category per row from the description, and flags rows that look like
duplicates of what's already imported or like payment/transfer line items
(e.g. "PAYMENT - THANK YOU" on a credit card) rather than real spending.
Nothing is written until you review the preview table and click Import.

Credit card, mortgage, and HELOC issuers often only offer a PDF statement.
For those, the app extracts the statement balance (and statement date) from
the PDF's text and updates the linked account -- it does not attempt to
extract itemized transactions from PDF tables, since those layouts vary too
much to parse reliably. If you need line-item detail for a credit card,
check whether the issuer also offers a CSV/Excel export.

## Data & privacy

All data is stored locally in a SQLite file at `personal_cfo/data/cfo.db`.
Nothing is sent anywhere -- this is a single-user, run-it-yourself app with
no accounts, no server, and no external services.

## Tech

Python, [Streamlit](https://streamlit.io) for the UI, SQLite for storage,
[Plotly](https://plotly.com/python/) for charts.
