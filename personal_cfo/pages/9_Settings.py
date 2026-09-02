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
st.caption(
    "Separately, the Streamlit \"Deploy\" button and developer menu are hidden app-wide "
    "(`.streamlit/config.toml`) -- a one-click cloud deploy is a bad fit for data like this."
)
