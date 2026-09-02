from pathlib import Path

import streamlit as st

# Deliberately does NOT call cfo.ui.setup_page() / auth.check_authentication()
# -- this page must stay reachable without signing in or knowing the
# shared password. A legal disclosure page that requires a login to read
# defeats its own purpose (an App Store reviewer, or anyone deciding
# whether to trust this app with their data, needs to read it *before*
# they'd ever have credentials), and Apple's own guidelines expect the
# privacy policy URL to be publicly reachable.
st.set_page_config(page_title="Privacy & Terms - Personal CFO", layout="wide")

_ROOT = Path(__file__).resolve().parent.parent

st.title("Privacy & Terms")
st.caption(
    "This app is self-hosted -- there's no company behind it, just whoever is running this "
    "particular copy. These documents explain what that means for your data."
)

privacy_tab, terms_tab = st.tabs(["Privacy Policy", "Terms of Use"])

with privacy_tab:
    st.markdown((_ROOT / "PRIVACY_POLICY.md").read_text())

with terms_tab:
    st.markdown((_ROOT / "TERMS.md").read_text())
