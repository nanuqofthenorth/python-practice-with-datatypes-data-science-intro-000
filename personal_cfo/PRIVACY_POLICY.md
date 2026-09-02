# Privacy Policy

**Last updated:** [FILL IN DATE]
**App:** Personal CFO
**Operator:** [YOUR NAME OR "FRIENDS & FAMILY" GROUP NAME], contactable at [YOUR CONTACT EMAIL]

This is a self-hosted app: there is no company behind it. Whoever set up the
copy you're using (the "Operator," named above) runs the server and the
database your data lives in. This policy describes what the app itself
does with your data — fill in the placeholders above before you publish
this if you're the Operator, and read this if you're using someone else's
copy of the app.

## What data this app collects

- **Financial data you enter or import:** account balances, transactions,
  budgets, debts, and savings goals.
- **Profile information you choose to provide:** name, age, a photo, a
  short bio, filing status, and links to your other social profiles. All
  of it is optional.
- **Login information:** if the Operator has enabled Google Sign-In, your
  Google account's stable ID (not your email) is used to keep your data
  separate from anyone else using the same app. If the Operator has set a
  shared password instead, no personal login data is collected at all —
  everyone who has the password shares one dataset.

## Where your data lives

Everything above is stored in a single database file on the server the
Operator runs — not in the cloud, not with us (there is no "us"; this is
open-source software), and not with any third party, with **one
exception**: the AI Advisor, described below. If the Operator has turned
on encryption at rest, that database file is encrypted; if not, it isn't.
Ask the Operator if you want to know which.

## The one thing that leaves this server: the AI Advisor

If the Operator has turned on the AI Advisor / CFO Briefing feature (it's
off by default), asking it a question or generating a briefing sends a
snapshot of your financial data to Anthropic's Claude API to generate a
response:

- **Included:** account balances and names, recent transactions, budget
  vs. actual, debts, goals, net worth history, and — if you've set a
  filing status on your profile — that filing status and an illustrative
  federal tax estimate calculated from your transaction history.
- **Never included:** your name, age, photo, bio, or social links. Those
  stay on this server no matter what.

This is the only data that leaves the server this app runs on, and only
when you use the AI Advisor or the Operator has the CFO Briefing enabled.
See Anthropic's own privacy policy at
[anthropic.com/privacy](https://www.anthropic.com/privacy) for how they
handle it on their end. The app's Advisor page has a "What data is sent
to Claude" panel showing you the exact payload before you ask anything.

## What this app does NOT do

- It does not sell, rent, or share your data with advertisers or data
  brokers. There's no advertising in this app at all.
- It does not track you across other apps or websites.
- It does not use your data to train any AI model — Anthropic's API is
  used strictly to answer your questions, per Anthropic's own API data
  usage terms.
- It does not automatically connect to your bank or brokerage. You choose
  what to upload or enter manually.

## Your data, your control

- **Backups:** you can download a complete copy of your own data at any
  time from the Settings page.
- **Deletion:** you can delete individual accounts, transactions,
  budgets, debts, and goals yourself from their respective pages. To
  delete everything at once, restore an empty backup file on the Settings
  page, or ask the Operator to remove your data from the database
  directly — as a self-hosted app, there's no separate "delete my
  account" button that reaches into the server on its own, so the
  Operator is who to ask for anything beyond what the in-app Delete
  buttons cover.
- **Isolation (if Google Sign-In is enabled):** your data is kept
  completely separate from any other person using the same app. See the
  Settings page for details on how this works.

## Children's privacy

This app is not directed at children and the Operator should not invite
anyone under 13 (or the relevant age of digital consent where they live)
to use it.

## Changes to this policy

The Operator may update this policy as the app changes. Significant
changes (e.g. turning on a feature that sends more data externally)
should be communicated directly to whoever uses this deployment, not just
buried in a document update.

## Contact

Questions about your data in this specific deployment go to the
Operator, listed at the top of this page — not to Anthropic (whose own
privacy policy covers only what happens after data reaches their API),
and not to any other party, because there isn't one.
