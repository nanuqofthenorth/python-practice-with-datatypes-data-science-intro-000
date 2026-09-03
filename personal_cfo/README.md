# Personal CFO

A self-hosted personal finance dashboard: track net worth, budget against
your income, plan debt payoff, and set savings goals -- with a running list
of plain-language insights, the way a CFO would brief you.

## Run it

```bash
cd personal_cfo
pip install -r requirements.txt
streamlit run Home.py
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

## Hosting it for other people

Running it on your own machine (above) is all that's needed to use it
yourself. To actually share a URL with friends or family -- and as a
prerequisite for Google Sign-In, whose redirect URI has to be a real
domain, not `localhost` -- it needs a real host with **persistent
storage**. That last part rules out some "easy" free options: Streamlit
Community Cloud, for instance, doesn't guarantee its filesystem survives
a restart or redeploy, which for this app means the database (everyone's
financial data) can simply vanish.

This repo includes a `Dockerfile` and a `render.yaml` blueprint for
[Render](https://render.com), which does provide a persistent disk at a
small monthly cost. The same `Dockerfile` works on any host that can run
a container with a mounted volume (Fly.io, Railway, a VPS you run
yourself) -- `render.yaml` is just the path of least setup.

**Deploying to Render:**

1. Push this repo to GitHub (already done if you're reading this from
   the repo).
2. On Render: **New +** -> **Blueprint**, point it at the repo. Render
   reads `render.yaml` and creates the service, including a persistent
   disk mounted exactly where `cfo/db.py` writes its database.
3. Render will prompt for the environment variables listed in
   `render.yaml` -- set `PERSONAL_CFO_PASSWORD` at minimum. The rest
   (`ANTHROPIC_API_KEY`, the `GOOGLE_OAUTH_*` variables) are optional;
   leave any of them blank to leave that feature off.
4. Deploy. Render gives you a URL like `https://personal-cfo-xxxx.onrender.com`.

**Google Sign-In on a real host** works differently than the localhost
setup in "Backup, restore & locking it down" below: instead of a
`secrets.toml` file (which isn't something you'd want baked into a
container image anyway), set these environment variables and
`docker-entrypoint.sh` writes the file for you on container start:

- `APP_BASE_URL` -- your app's real URL, e.g. `https://personal-cfo-xxxx.onrender.com`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` -- from the same
  Google Cloud Console OAuth client described below, except the
  authorized redirect URI you register there should be
  `<APP_BASE_URL>/oauth2callback` (your real domain, not `localhost`).
- `GOOGLE_OAUTH_COOKIE_SECRET` -- generate with
  `python3 -c "import secrets; print(secrets.token_hex(32))"`.

Leave all four unset and the app runs exactly as it does locally, just
reachable at a real URL -- password protection only, no Google Sign-In,
one shared dataset for whoever has the password.

**Sharing an API key across multiple people is a real cost/blast-radius
decision, not just a config toggle.** Setting `ANTHROPIC_API_KEY` once
for the hosted app means every signed-in tenant's Advisor questions and
CFO Briefings draw on that one key and your billing, with no per-tenant
spending limit or breakdown of who used how much. Fine for a handful of
trusted friends and family; something to actually think about before
handing the URL to more people than that.

## What's inside

- **Setup Wizard** -- new here? Upload however many statements you have at
  once and it creates the right account for each one (guessed from the
  filename, always shown to you first) and walks you through reviewing and
  importing each file's transactions. See "Setup Wizard" below.
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

Two more things live inside existing pages rather than getting their own:
a **Recurring & subscriptions** tab on Transactions (see "Recurring
transactions" below), and a **federal tax estimate** on Profile, once
you've set a filing status and logged some income (see "Filing status &
the federal tax estimate" below).

## Backup, restore & locking it down

**Backup.** Settings has a **Download backup** button -- a complete,
consistent snapshot of everything (accounts, transactions, budgets, debts,
goals, and your profile, photo included) as one `.db` file, built row by
row rather than a raw file copy so it's never half-written. There's also a
plain CSV export of just your transactions. Nothing does this
automatically -- it's a button, not a schedule -- so make a habit of it,
especially before restoring or upgrading. If Google Sign-In is configured,
this backup contains *only the signed-in account's own data* -- see
"Multiple people, one running app" below.

**Automated backups (hosted deployments only).** On top of the manual
button above, the app opportunistically makes its own full-database
backup -- every tenant, not just yours -- to `data/backups/` once it's
been at least 24 hours since the last one, checked once per page load.
This is a disaster-recovery safety net for whoever's running the server,
not something any signed-in tenant can see or download; it only actually
does anything useful once the app is hosted with persistent storage (see
"Hosting" below) -- backups written to a container's local, non-persistent
disk are lost the same way the live database would be. "Opportunistic"
means exactly what it sounds like: it runs when someone happens to load a
page, not on a guaranteed clock, so an app nobody opens for a week doesn't
get backed up for a week. The last 14 are kept; older ones are deleted
automatically.

**Restore.** Also on Settings: upload a `.db` file and it's checked (SQLite
integrity check, plus the expected tables) before you're allowed to
confirm the overwrite. Restoring replaces everything belonging to whoever
is currently signed in (with no Google Sign-In configured, that's
everyone, since there's only the one shared tenant) -- there's no merge
and no undo beyond keeping your own backups. A backup taken years ago,
before any of this multi-tenancy existed, still restores cleanly: it's
migrated to the current schema on the way in, the same as an old live
database is (see below).

**Locking it down.** By default this app has no password and no login --
fine for the intended use (you, on your own machine, at `localhost`).
Three things exist for anyone who runs it somewhere reachable over a
network, or who just wants a lock screen:

- Set the `PERSONAL_CFO_PASSWORD` environment variable before launching to
  require a password once per browser session before anything renders.
  It's a single shared password, not a user-accounts system. Rate-limited
  per client IP -- 5 wrong attempts locks that IP out for 5 minutes,
  doubling on repeated abuse up to an hour -- so it isn't trivially
  brute-forceable once the app is reachable over the internet. This is an
  in-memory, per-process limit: it resets on restart and (if this app is
  ever scaled to multiple server instances, which it isn't by default)
  doesn't share state across them.
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

**Biometric login (Face ID / Touch ID / Windows Hello) in the web app
itself isn't built.** Doing that as a standalone web feature means
implementing WebAuthn/passkeys -- a browser-side JavaScript credential
ceremony plus server-side cryptographic challenge/response -- with
nothing in Streamlit to build on. That's a real, security-critical
feature to get right, not something to bolt on quickly; getting it wrong
would be worse than not having it. If you already have a passkey
configured on your Google account, Google's own sign-in screen will
typically prompt for it automatically, which may already deliver what
"biometric login" was after without a separate implementation.
Separately, the **iOS wrapper app** (`ios/`) does add real Face ID/Touch
ID -- as a device-local lock on that one phone, layered on top of
whichever of the above the hosted app itself uses, not a replacement for
it. See `ios/README.md`.

**Encryption at rest is opt-in and needs an extra install step.** Run
`pip3 install -r requirements-encryption.txt` first (this is deliberately
*not* part of the regular `pip3 install -r requirements.txt` -- its wheel
isn't available for every platform/Python combination, notably some macOS
setups, and the base app shouldn't fail to install for everyone just
because of an optional feature). Then set the `DB_ENCRYPTION_KEY`
environment variable and the database file (plus every backup, manual or
automated) is encrypted with [SQLCipher](https://www.zetetic.net/sqlcipher/)
instead of stored as plain SQLite -- unreadable on disk without the key,
not just access-controlled. Off by default, like every other opt-in
security feature in this app; if you never set `DB_ENCRYPTION_KEY`, you
never need `requirements-encryption.txt` at all. **If you're turning this
on for a database that
already exists** (not a brand-new deployment), run
`DB_ENCRYPTION_KEY="your-new-key" python3 scripts/encrypt_existing_db.py`
once first -- SQLCipher can't open a plaintext file once a key is set, so
simply setting the environment variable against existing data would make
it unreadable, not encrypt it. The script keeps your original plaintext
file as `cfo.db.pre-encryption-backup`; verify the app works against the
encrypted copy, then delete that yourself once you're confident. Losing
the key means losing the data -- there's no recovery, by design; store it
somewhere durable (your host's secret manager), not a note to yourself.

**Multiple people, one running app.** Without Google Sign-In configured,
everyone who opens the app -- or unlocks it with the shared password --
sees and edits the exact same dataset; there's no way to tell people apart.
With Google Sign-In configured, each distinct Google account gets its own
completely separate accounts, transactions, budgets, debts, goals, and
profile, keyed by that account's stable Google id (not email, so a renamed
or re-verified email doesn't lose data) -- one person can never see, edit,
or delete another's data, even though they're all using the same running
app at the same URL. A shared `PERSONAL_CFO_PASSWORD` does *not* give this
isolation: everyone who has the password lands in that same single shared
dataset regardless. This is what makes "share the URL with friends and
family, everyone signs in with their own Google account" a real option,
not just a login screen bolted onto a single-user app.

## Profile & the community idea

The Profile page stores a name, age, filing status, photo, bio, and
optional links (LinkedIn, Instagram, Facebook, a website) -- purely local,
like everything except the AI features. It exists today just to
personalize the app (your name and photo show up in the sidebar) and to
make those links clickable.

Filing status uses the actual IRS categories (Single, Married Filing
Jointly, Married Filing Separately, Head of Household, Qualifying
Surviving Spouse) rather than a plain single/married toggle, since
jointly vs. separately is the distinction with real tax consequences. See
"Filing status & the federal tax estimate" below for what it now drives.
The Dashboard's health score still doesn't factor it in.

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

## Filing status & the federal tax estimate

Once you set a filing status on the Profile page and have logged some
income, a **federal tax estimate** appears there: estimated annual income
(the average of your last up-to-12 months of logged income transactions,
annualized), your marginal federal bracket, effective federal rate, and
the standard deduction applied. Deliberately narrow, by design:

- **Federal only** -- no state, local, or payroll (FICA) tax.
- **Standard deduction only** -- no itemizing, no credits, no AMT, no
  capital-gains preferential rates.
- **Illustrative, not a real return** -- "income" is inferred from
  transactions logged in this app, not W-2/1099 data, and doesn't account
  for pre-tax deductions (401(k), HSA, etc.) that would lower actual
  taxable income.

The tax year and bracket figures (`cfo/tax.py`) are hand-entered from a
specific IRS Revenue Procedure, named in the code and on the page --
they do not update themselves and need replacing by hand every year.
Verify against [irs.gov](https://www.irs.gov) before relying on this for
anything real; it's a planning estimate, not tax advice.

If you use the **AI Advisor**, your filing status and this tax estimate
are included in the financial snapshot it sends to Anthropic's API (see
"AI Advisor & CFO Briefing" below) so it can give bracket-aware answers
(e.g. traditional vs. Roth contributions). Your name, age, photo, bio,
and social links are never included, regardless.

## Recurring transactions

The Transactions page has a **Recurring & subscriptions** tab that
automatically flags expenses showing up with the same description and a
similar amount in most recent months -- subscriptions, rent, recurring
bills -- without you having to spot the pattern by eye. Matching
(`cfo.calculations.detect_recurring_transactions`) is by exact,
case/whitespace-insensitive description text, not fuzzy: a description
that changes slightly month to month (a trailing reference number or
date) won't be caught. Needs at least 3 months of matching history, with
no more than one month ever skipped in a row, to avoid flagging a
coincidental one-off repeat.

## Setup Wizard

The fastest way into the app with real data: **Setup Wizard** in the
sidebar (or the **Set up my accounts** button that appears there before
you've entered anything). Upload one or more statement files at once and
it walks through them one at a time:

1. **Guesses the account** -- and, for a PDF, the interest rate too --
   from both the filename *and the statement's own content* (PDF text, or
   a CSV/Excel file's column headers), not the filename alone.
   `statement_download.pdf` with no useful name still comes back correctly
   guessed as a liability in Credit Card if the statement text contains
   things like "Minimum Payment Due" or a labeled APR; a mortgage
   statement is recognized from "Escrow Balance," a brokerage export from
   column headers like "Cost Basis." (`cfo/account_guess.py` has the full
   keyword list: checking/savings, credit cards by name, mortgage, HELOC,
   student and auto loans, 401(k)/IRA, and brokerage accounts.) For a
   liability, `cfo/importers.py::extract_rate_candidates()` pulls the
   APR/interest rate straight from a PDF's text -- if the statement lists
   more than one (purchase vs. cash-advance APR, say), you're asked which
   one applies; otherwise it's pre-filled and you just confirm it, no
   typing required. Every field stays editable before you confirm --
   nothing recognized just falls back to a generic asset with a note to
   double-check it, never a silent guess.
2. **Creates that account**, then runs the exact same column-detection,
   duplicate/transfer-flagging, and review-table logic as Import
   Statements below (they share the same code, `cfo/import_ui.py`) --
   nothing is imported until you review it, same as everywhere else in
   this app.
3. **Moves to the next file** once you've imported (or skipped) the
   current one, and ends with a summary of what was created.

This is the primary way to get real data in with statements; **Accounts**
and **Transactions** in the sidebar are the manual/advanced path --
add or edit an account by hand, or log a single transaction one at a
time, whenever the wizard isn't what you want.

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
  `streamlit run Home.py`, or
- paste a key into the **AI Advisor setup** panel in the sidebar (kept only
  in that browser session's memory -- never written to disk).

Every question you ask, and the periodic briefing, sends a JSON snapshot of
your accounts, recent transactions, budget, debts, goals, and -- if you've
set one -- your filing status and federal tax estimate, to Anthropic's
API so the model can reason over real numbers instead of guessing. Your
name, age, photo, bio, and social links are never included, no matter
what. The Advisor page has a "What data is sent to Claude" panel that
shows you the exact payload. This uses your API key's own usage/billing --
each question and each briefing regeneration is a real API call.

The CFO Briefing is cached per financial snapshot (not regenerated on every
page load) and has its own Regenerate button, so it only calls the API when
your data has actually changed or you ask it to.

## Data & privacy

Everything except the AI Advisor and CFO Briefing is entirely local: all
data lives in a SQLite file at `personal_cfo/data/cfo.db` (optionally
encrypted at rest -- see "Locking it down" above), and nothing is sent
anywhere. The AI features are the one exception, are opt-in (no API key,
no calls), and only ever send the financial snapshot described above --
never your API key to anywhere but Anthropic, and never any data to any
third party beyond that. See `PRIVACY_POLICY.md` and `TERMS.md` for the
full, App-Store-facing version of this (also reachable at
`/Privacy_and_Terms` in the running app, without needing to sign in).

## Testing

```bash
cd personal_cfo
pip install -r requirements-dev.txt
python3 -m pytest tests/ -v
```

Covers the multi-tenancy/isolation logic, backup/restore (including
legacy-format migration), the health score and debt payoff simulator, the
recurring-transaction detector, the tax-estimate math, the password
gate's rate limiter, and encryption at rest -- run automatically on every
push via GitHub Actions (`.github/workflows/personal-cfo-tests.yml`).
This is unit/integration coverage of the calculation and persistence
layers; it doesn't replace clicking through the actual UI, which is worth
doing by hand for anything touching a page directly.

## iOS app & App Store

`ios/` has a SwiftUI wrapper -- a WKWebView pointed at your hosted app,
gated by Face ID/Touch ID -- and `APP_STORE_CHECKLIST.md` walks through
Apple Developer enrollment, App Store Connect setup, the privacy
nutrition label, screenshots, and TestFlight for a friends-and-family
beta before a full release. See `ios/README.md` first: this code has
never been compiled (written without access to Xcode/a Mac), so budget
time to get it actually building before anything else in the checklist
matters.

## Tech

Python, [Streamlit](https://streamlit.io) for the UI, SQLite (optionally
[SQLCipher](https://www.zetetic.net/sqlcipher/)-encrypted) for storage,
[Plotly](https://plotly.com/python/) for charts, the
[Anthropic API](https://docs.anthropic.com) for the Advisor and Briefing,
[pytest](https://pytest.org) for tests, Docker for hosting, and a SwiftUI
wrapper for iOS.
