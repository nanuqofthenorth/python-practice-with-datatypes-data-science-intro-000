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

- **Dashboard** -- a financial health gauge ("are you on track?"), net worth
  trend, income vs. expenses, spending by category, rule-based insights
  (savings rate, over-budget categories, high-APR debt, goal pacing), and,
  if configured, a **CFO Briefing** -- a handful of proactive, AI-generated
  recommendations that appear without being asked. Any actionable item can
  be turned into a calendar reminder.
- **Advisor** -- ask free-form questions ("should I pay down debt or keep
  investing?", "am I on track for my goals?") and get answers grounded in
  your actual accounts, transactions, budget, debts, and goals.
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

## Financial health gauge

"Are you on track?" boils down to one 0-100 score, built from five
components -- savings rate, budget adherence, debt health (balance-weighted
average APR), emergency fund coverage (months of expenses held in cash),
and goal progress. Each component is scored independently on its own 0-100
scale; a component with no underlying data yet (e.g. no goals added) is
simply left out and the remaining weights are renormalized, rather than
dragging the score down for something you haven't entered. The Dashboard
shows the gauge plus a plain-language breakdown of what's driving it. This
is entirely local and rule-based -- no API key needed, unlike the Briefing.

## Calendar reminders

Any actionable item -- a Watch/Action item in the CFO Briefing or Insights,
a goal's monthly contribution, or a debt payoff plan's extra payment -- has
an **Add to Calendar** button (downloads a `.ics` file: Apple Calendar,
Outlook, Google Calendar import, or any standards-compliant app) and, on
the Dashboard, a **Google Calendar** quick-add link. A bulk button bundles
every actionable item into one file. Goal and debt reminders recur monthly
until the target date / payoff month.

This is export, not sync -- there's no OAuth, no connected account, and no
background polling. Genuine two-way calendar sync would need real
credentials and consent screens per provider, which doesn't fit a
self-hosted, no-accounts app; a downloadable reminder does the actual job
("get this recommendation onto my calendar") without that overhead.

## AI Advisor & CFO Briefing

The Advisor page and the Dashboard's CFO Briefing are powered by the
[Claude API](https://www.anthropic.com/api) (Claude Opus 5) and are **off by
default**. To turn them on, either:

- set the `ANTHROPIC_API_KEY` environment variable before running
  `streamlit run app.py`, or
- paste a key into the **AI Advisor setup** panel in the sidebar (kept only
  in that browser session's memory -- never written to disk).

Every question you ask, and the periodic briefing, sends a JSON snapshot of
your accounts, recent transactions, budget, debts, and goals to Anthropic's
API so the model can reason over real numbers instead of guessing. The
Advisor page has a "What data is sent to Claude" panel that shows you the
exact payload. This uses your API key's own usage/billing -- each question
and each briefing regeneration is a real API call.

The CFO Briefing is cached per financial snapshot (not regenerated on every
page load) and has its own Regenerate button, so it only calls the API when
your data has actually changed or you ask it to.

## Data & privacy

Everything except the AI Advisor and CFO Briefing is entirely local: all
data lives in a SQLite file at `personal_cfo/data/cfo.db`, and nothing is
sent anywhere. The AI features are the one exception, are opt-in (no API
key, no calls), and only ever send the financial snapshot described above --
never your API key to anywhere but Anthropic, and never any data to any
third party beyond that.

## Tech

Python, [Streamlit](https://streamlit.io) for the UI, SQLite for storage,
[Plotly](https://plotly.com/python/) for charts, the
[Anthropic API](https://docs.anthropic.com) for the Advisor and Briefing.
