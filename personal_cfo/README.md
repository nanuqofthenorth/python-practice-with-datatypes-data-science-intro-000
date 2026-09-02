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

**Dark mode:** open the **⋮** menu at the top right of any page and pick
Light, Dark, or System under the theme icons -- that's Streamlit's own
built-in switcher, no setup needed. Every chart in the app (the health
gauge, trend lines, bar charts) is theme-aware and switches its own colors
to match; they don't just inherit the page background, since Plotly
figures are static images sent to the browser rather than themed CSS.

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
- **Profile** -- your name, age, photo, and a short bio. Personalizes the
  sidebar today; see "Profile & the community idea" below for why it exists.
- **Settings** -- download a full backup, restore from one, export
  transactions as CSV, and see whether password protection is on. See
  "Backup, restore & locking it down" below.

## Backup, restore & locking it down

**Backup.** Settings has a **Download backup** button -- a complete,
consistent snapshot of everything (accounts, transactions, budgets, debts,
goals, and your profile, photo included) as one `.db` file, taken via
SQLite's own `VACUUM INTO` rather than a raw file copy so it's never
half-written. There's also a plain CSV export of just your transactions.
Nothing does this automatically -- it's a button, not a schedule -- so
make a habit of it, especially before restoring or upgrading.

**Restore.** Also on Settings: upload a `.db` file and it's checked (SQLite
integrity check, plus the expected tables) before you're allowed to
confirm the overwrite. Restoring replaces *everything* currently in the
app -- there's no merge and no undo beyond keeping your own backups.

**Locking it down.** By default this app has no password and no login --
fine for the intended use (you, on your own machine, at `localhost`).
Three things exist for anyone who runs it somewhere reachable over a
network, or who just wants a lock screen:

- Set the `PERSONAL_CFO_PASSWORD` environment variable before launching to
  require a password once per browser session before anything renders.
  It's a single shared password, not a user-accounts system.
- **Google Sign-In**, via Streamlit's own native `st.login()` (Authlib
  under the hood) -- opt in by copying `.streamlit/secrets.toml.example`
  to `.streamlit/secrets.toml` and filling in a real OAuth client you
  register yourself at [Google Cloud Console](https://console.cloud.google.com/)
  (OAuth consent screen -> Web application credential -> add
  `http://localhost:8501/oauth2callback` as an authorized redirect URI).
  Full steps are on the Settings page. `secrets.toml` is gitignored --
  never commit it, it holds a real client secret. If both this and
  `PERSONAL_CFO_PASSWORD` are set, either one unlocks the app.
- `.streamlit/config.toml` hides Streamlit's own "Deploy" button and
  developer menu app-wide (`toolbarMode = "viewer"`) -- a one-click cloud
  deploy prompt is a bad fit sitting on top of financial and personal data.

**Biometric login (Face ID / Touch ID / Windows Hello) isn't built.**
Doing that as a standalone feature means implementing WebAuthn/passkeys --
a browser-side JavaScript credential ceremony plus server-side
cryptographic challenge/response -- with nothing in Streamlit to build on.
That's a real, security-critical feature to get right, not something to
bolt on quickly; getting it wrong would be worse than not having it. If
you already have a passkey configured on your Google account, Google's
own sign-in screen will typically prompt for it automatically, which may
already deliver what "biometric login" was after without a separate
implementation.

None of the above makes the app suitable for multiple untrusted users --
there's still one shared dataset, not per-user accounts. Google Sign-In
authenticates *a* Google account; it doesn't create separate permissions
per person.

## Profile & the community idea

The Profile page stores a name, age, filing status, photo, bio, and
optional links (LinkedIn, Instagram, Facebook, a website) -- purely local,
like everything except the AI features. It exists today just to
personalize the app (your name and photo show up in the sidebar) and to
make those links clickable.

Filing status uses the actual IRS categories (Single, Married Filing
Jointly, Married Filing Separately, Head of Household, Qualifying
Surviving Spouse) rather than a plain single/married toggle, since
jointly vs. separately is the distinction with real tax consequences. It's
stored but not used anywhere yet -- the health score and AI Advisor don't
factor it in. Turning it into actual tax-aware guidance (bracket-aware
suggestions, standard-vs-itemized tradeoffs) is a reasonable next step but
a deliberately separate one, since it means committing to a tax year and a
scope (federal only vs. state too) for guidance that should be right
rather than approximately right.

The social fields are plain links, not a sync: paste a handle or URL and
it renders as a button, nothing more. No photo, bio, or verification is
pulled in from LinkedIn/Instagram/Facebook automatically -- that would
need an OAuth app registered with each platform (LinkedIn's API is tightly
restricted for third parties; Meta requires app review for Instagram/
Facebook access) plus somewhere to securely hold the resulting tokens,
which is real infrastructure this self-hosted, no-accounts app doesn't
have. Worth building later if there's a real reason to verify identity or
pull in a live photo, but it's a separate decision from a link field.

The reason it's shaped like a profile rather than a settings field: the
longer-term idea is a community layer where people who take their finances
seriously could find and meet each other, using a profile like this one
plus a privacy-controlled summary of financial health (like the Dashboard's
on-track gauge) rather than raw numbers. That doesn't exist yet -- there's
no server, no other users, no discovery, and nothing is shared or
published. The Profile page says so explicitly and has a disabled
"discoverable" checkbox as a visible placeholder for that possible future,
not a working toggle. Building the real thing would mean real infrastructure
(accounts, a backend, moderation, consent flows) that's a deliberately
separate decision from storing a profile locally today.

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
