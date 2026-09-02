# App Store submission checklist

Concrete steps to get the iOS wrapper (`ios/`) in front of friends and
family via TestFlight, and what's needed for a full App Store release
after that. Written for someone doing this for the first time -- skip
what you already know.

## 0. Prerequisites

- [ ] The app is hosted somewhere with a real, stable HTTPS URL and
      persistent storage (see main README, "Hosting it for other
      people"). The iOS wrapper has nothing to point at otherwise.
- [ ] The iOS wrapper (`ios/`) builds and runs on your own device via
      Xcode -- see `ios/README.md`. Get this working before touching App
      Store Connect; nothing below matters until the app actually runs.
- [ ] A Mac with a recent Xcode version.

## 1. Apple Developer Program enrollment

- [ ] Sign up at [developer.apple.com/programs](https://developer.apple.com/programs/)
      -- $99/year, individual or organization. Takes anywhere from
      minutes to a couple of days for Apple to verify, longer for an
      organization (needs a D-U-N-S number).
- [ ] Once enrolled, your Apple ID is tied to a Team in Xcode's Signing &
      Capabilities -- this is what `ios/README.md` step 5 refers to.

## 2. App Store Connect: create the app record

At [appstoreconnect.apple.com](https://appstoreconnect.apple.com):

- [ ] **My Apps -> +  -> New App.**
- [ ] **Platform:** iOS.
- [ ] **Name:** what shows on the App Store (unique across the entire
      store -- "Personal CFO" alone may well be taken; be ready with a
      variant).
- [ ] **Primary language, Bundle ID** (must match the one you set in
      Xcode signing), **SKU** (an internal identifier, your choice, not
      shown publicly).

## 3. Privacy nutrition label (App Privacy questionnaire)

This is filled out in App Store Connect, not in code -- it's what
produces the "Data Used to Track You" / "Data Linked to You" labels
shown on your store listing. Answer based on what this app actually does;
`PRIVACY_POLICY.md` in this repo is the source of truth to answer from.
As built, expect roughly:

| Data type | Collected? | Linked to identity? | Used for |
|---|---|---|---|
| Financial Info (account balances, transactions, budgets, debts, goals) | Yes | Yes, if Google Sign-In is on (else no per-user identity exists at all) | App Functionality |
| Contact Info (email) | Only if Google Sign-In is on | Yes | App Functionality (sign-in) |
| User ID (Google account ID) | Only if Google Sign-In is on | Yes | App Functionality (sign-in, data isolation) |
| Photos | Only if you upload a profile photo | Yes | App Functionality |
| Other User Content (name, age, bio, social links) | Only if you fill in the Profile page | Yes | App Functionality |

None of this is used for tracking (no cross-app/cross-site identifiers,
no ad targeting -- there's no advertising in this app at all) and none of
it is shared with third parties except Anthropic, and only the financial
snapshot described in `PRIVACY_POLICY.md`, only when the AI Advisor is
used. Answer the "used for tracking" and "shared with third parties for
tracking" questions **No** based on that -- revisit this table if you
change what the app actually does.

- [ ] Fill out the questionnaire in App Store Connect using the table above.
- [ ] **Privacy Policy URL:** point this at your hosted app's
      `/Privacy_and_Terms` page (e.g.
      `https://your-app.onrender.com/Privacy_and_Terms`) -- see
      `pages/10_Privacy_and_Terms.py`, which is reachable without signing
      in specifically so this works.
- [ ] Before any of this is real: fill in the `[FILL IN ...]` placeholders
      in `PRIVACY_POLICY.md` and `TERMS.md` (your name/contact, the date)
      and redeploy so the live page reflects them.

## 4. Screenshots

App Store Connect requires at least one screenshot set for the largest
iPhone size class you support (6.9" / iPhone 16 Pro Max-class as of this
writing -- Apple's requirements shift with new device sizes, check the
current spec in App Store Connect when you get here). Simplest path:

- [ ] Run the app in the iOS Simulator on the required device size.
- [ ] Simulator -> Device -> Trigger Screenshot (or Cmd+S) on 3-5 key
      screens: Dashboard (with sample data, showing the health gauge),
      Accounts, Debt Payoff or Goals, and the Advisor (if you're
      showcasing the AI feature).
- [ ] Upload in App Store Connect's Media Manager for the app version.

## 5. App metadata

- [ ] **Description:** what the app does, in App Store Connect's
      description field. The main README's intro paragraph and "What's
      inside" section are a solid starting draft to adapt.
- [ ] **Keywords, Support URL, Marketing URL:** Support URL can point at
      the same `/Privacy_and_Terms` page, or a GitHub issues link if this
      stays open-source; Marketing URL is optional.
- [ ] **Age rating questionnaire:** answer honestly -- this app has no
      objectionable content, gambling, or user-generated content shared
      with others (the "community" idea on the Profile page is explicitly
      not built). Should land at the lowest age tier.

## 6. Guideline 4.2 (Minimum Functionality) -- the real risk here

Apple's reviewers reject bare website-in-a-WebView apps under Guideline
4.2. This app is a thin wrapper by design (see `ios/README.md`), which is
exactly the shape Apple scrutinizes. What pushes it toward "acceptable"
rather than "just a website":

- Native Face ID / Touch ID gating (`BiometricAuthManager.swift`) -- a
  real platform capability a website can't replicate.
- A persistent native app icon and launch experience, not a bookmark.
- (If you build them later) native push notifications, widgets, or
  Shortcuts/Siri integration would strengthen this further.

If rejected under 4.2, Apple's response usually names specifically what's
missing -- read it carefully and address that, rather than resubmitting
unchanged. There's no way to guarantee approval in advance; this section
exists so it isn't a surprise.

## 7. TestFlight (for the friends-and-family beta you actually want first)

- [ ] In App Store Connect, once you've uploaded a build (via Xcode ->
      Product -> Archive -> Distribute App -> App Store Connect), it
      appears under **TestFlight**.
- [ ] **Internal Testing:** up to 100 testers who are members of your
      App Store Connect team -- fastest path, no App Review needed, but
      limited to people you'd add as team members.
- [ ] **External Testing:** up to 10,000 testers via email or a public
      link, no App Store Connect team membership needed -- this is
      almost certainly what you want for actual friends and family. The
      **first** external build needs a lightweight Beta App Review
      (usually faster than full App Review, but still a real review);
      subsequent builds to the same testers don't need re-review unless
      you change significant functionality.
- [ ] Add a build, fill in "What to Test" notes, add testers by email or
      share the public TestFlight link.
- [ ] Builds expire after 90 days -- upload a new one before then to keep
      testing.

## 8. Review notes for whoever reviews the build

Both Beta App Review (TestFlight) and full App Store Review need a way to
actually open the app. If you have `PERSONAL_CFO_PASSWORD` set on your
hosted deployment, **create a demo account or share the password in the
review notes** (App Store Connect has a specific "Sign-In Information"
field for exactly this) -- a reviewer who can't get past your login
screen can't approve the app.

## 9. Full App Store submission (after the beta)

- [ ] Once you're happy with TestFlight feedback, go to the app version
      in App Store Connect, fill in anything not already done above, and
      **Submit for Review**.
- [ ] Typical review time is 24-48 hours as of this writing, but varies.
- [ ] If rejected, the Resolution Center in App Store Connect explains
      why -- fix the specific thing named, don't guess.
