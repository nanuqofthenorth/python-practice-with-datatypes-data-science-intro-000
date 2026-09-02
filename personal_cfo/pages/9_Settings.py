from datetime import date

import streamlit as st

from cfo import auth
from cfo import db
from cfo.ui import setup_page

setup_page("Settings")

st.title("Settings")
st.caption("Backups, restore, and how to lock this app down.")

if st.session_state.pop("_restore_flash", False):
    st.success("Restored.")

st.subheader("Backup")
st.caption(
    "Downloads everything -- accounts, transactions, budgets, debts, goals, and your profile "
    "(including your photo) -- as one file. This is the real backup; keep a copy somewhere safe."
)
st.download_button(
    "Download backup", db.backup_bytes(),
    file_name=f"personal-cfo-backup-{date.today().isoformat()}.db", mime="application/x-sqlite3",
)

transactions = db.list_transactions()
if not transactions.empty:
    st.caption("Want just your transactions in a spreadsheet (e.g. for tax prep)?")
    csv_bytes = transactions.drop(columns=["id"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export transactions as CSV", csv_bytes,
        file_name=f"personal-cfo-transactions-{date.today().isoformat()}.csv", mime="text/csv",
    )

st.divider()
st.subheader("Restore from backup")
st.warning(
    "Restoring **replaces everything currently in the app** with the contents of the uploaded file. "
    "This can't be undone -- if you're not sure, download a fresh backup above first."
)
restore_file = st.file_uploader("Backup file (.db)", type=["db", "sqlite", "sqlite3"])
if restore_file is not None:
    file_bytes = restore_file.getvalue()
    ok, reason = db.validate_backup(file_bytes)
    if not ok:
        st.error(f"Can't restore this file: {reason}")
    else:
        st.success("This looks like a valid Personal CFO backup.")
        confirm = st.checkbox("I understand this will overwrite all current data.")
        if st.button("Restore", disabled=not confirm, type="primary"):
            db.restore_from_bytes(file_bytes)
            st.session_state.pop("advisor_messages", None)
            st.session_state.pop("briefing_nonce", None)
            st.session_state["_restore_flash"] = True
            st.rerun()

st.divider()
st.subheader("Password protection")
if auth.is_password_protected():
    st.success("Password protection is **on**, set via the `PERSONAL_CFO_PASSWORD` environment variable.")
else:
    st.warning(
        "Password protection is **off**. Anyone who can reach this app's URL can see everything in it -- "
        "your finances, name, age, photo, and bio. That's fine for `localhost`-only use. If you ever run "
        "this somewhere reachable over a network, set the `PERSONAL_CFO_PASSWORD` environment variable "
        "before launching to require a password once per browser session:"
    )
    st.code('PERSONAL_CFO_PASSWORD="your-password" streamlit run app.py', language="bash")
    st.caption(
        "This is a single shared password, not a full accounts system -- it closes the gap between "
        "\"built for localhost\" and \"reachable from anywhere,\" not a login for multiple separate people."
    )

st.divider()
st.subheader("Google Sign-In")
if auth.is_google_oauth_configured():
    st.success("Google Sign-In is **configured** -- available as a login option alongside the password, if set.")
    identity = auth.current_google_identity()
    if identity:
        st.caption(f"Currently signed in as {identity}.")
else:
    st.info(
        "Not configured. This uses Streamlit's own native Google login (`st.login()`), which requires a "
        "real OAuth app registered in Google Cloud Console -- there's no credential we can hand you for "
        "this, it's tied to a Google account you control. Setup:"
    )
    st.markdown(
        "1. [Google Cloud Console](https://console.cloud.google.com/) -> create or pick a project -> "
        "**APIs & Services > OAuth consent screen** -> configure it.\n"
        "2. **APIs & Services > Credentials > Create Credentials > OAuth client ID**, "
        "application type **Web application**.\n"
        "3. Under **Authorized redirect URIs**, add `http://localhost:8501/oauth2callback` "
        "(match your port if it isn't 8501).\n"
        "4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the "
        "Client ID and Client secret from step 2.\n"
        "5. Generate a `cookie_secret`: `python3 -c \"import secrets; print(secrets.token_hex(32))\"` "
        "and paste it into the same file.\n"
        "6. Restart the app."
    )
    st.caption(
        "secrets.toml is gitignored -- it holds a real client secret, treat it like a password. If both "
        "this and PERSONAL_CFO_PASSWORD are configured, either one unlocks the app."
    )

st.caption(
    "Separately, the Streamlit \"Deploy\" button and developer menu are hidden app-wide "
    "(`.streamlit/config.toml`) -- a one-click cloud deploy is a bad fit for data like this."
)

st.divider()
st.subheader("Biometric login (Face ID / Touch ID / Windows Hello)")
st.caption(
    "Not built. A standalone biometric login means implementing WebAuthn/passkeys yourself -- a browser "
    "JavaScript credential ceremony plus server-side cryptographic challenge/response, with no native "
    "Streamlit support to build on. Getting that wrong is worse than not having it, so it isn't something "
    "to bolt on quickly. If you have a passkey set up on your Google account already, Google's own sign-in "
    "screen above will typically prompt for it automatically -- which may already cover what you're after "
    "without a separate implementation. Ask if you want a dedicated passkey system regardless."
)
