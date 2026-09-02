import io

import streamlit as st
from PIL import Image

from cfo import db
from cfo.ui import setup_page

setup_page("Profile")

st.title("Profile")
st.caption("Who you are, so the app can greet you by name -- and groundwork for a possible future feature.")

if st.session_state.pop("_profile_saved_flash", False):
    st.success("Profile saved.")

st.info(
    "This stays on your machine like everything else in this app, with one exception: the AI Advisor "
    "sends your *financial* snapshot to Anthropic's API when you use it, but never this profile. "
    "Nothing here is shared, published, or visible to anyone else -- there's no other side to share it "
    "with yet. See \"What this is for\" below."
)

profile = db.get_profile() or {}

SOCIAL_PLATFORMS = [
    ("linkedin_url", "LinkedIn", "https://linkedin.com/in", "yourname or linkedin.com/in/yourname"),
    ("instagram_url", "Instagram", "https://instagram.com", "@yourhandle or instagram.com/yourhandle"),
    ("facebook_url", "Facebook", "https://facebook.com", "yourname or facebook.com/yourname"),
    ("website_url", "Website", None, "yoursite.com"),
]


def _process_photo(file_bytes: bytes, max_dim: int = 512) -> tuple[bytes, str] | None:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 -- not a valid image; caller shows the error
        return None


def _normalize_link(value: str, base_url: str | None) -> str:
    """Accept a bare handle, a bare domain, or a full URL and return
    something clickable. base_url=None means "generic site" -- just add a
    scheme if missing, no platform-specific handle expansion.

    A handle is anything without a "/" -- deliberately not gated on
    whether it contains a "." too, since dotted handles (e.g. an
    Instagram "@alex.morgan") are common and would otherwise get
    misread as a bare domain."""
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value
    if base_url and "/" not in value:
        return f"{base_url}/{value.lstrip('@')}"
    return f"https://{value.lstrip('@')}"


existing_links = {key: profile.get(key) for key, *_ in SOCIAL_PLATFORMS if profile.get(key)}
if existing_links:
    st.markdown("**Links**")
    link_cols = st.columns(len(existing_links))
    for col, (key, url) in zip(link_cols, existing_links.items()):
        label = next(label for k, label, *_ in SOCIAL_PLATFORMS if k == key)
        with col:
            st.link_button(label, url, use_container_width=True)

left, right = st.columns([1, 2])

with left:
    st.markdown("**Photo**")
    if profile.get("photo"):
        st.image(profile["photo"], width=200)
        if st.button("Remove photo"):
            db.clear_profile_photo()
            st.rerun()
    else:
        st.caption("No photo yet.")
    uploaded_photo = st.file_uploader("Upload a new photo", type=["png", "jpg", "jpeg"])

with right:
    with st.form("profile_form"):
        name = st.text_input("Name", value=profile.get("name", ""))
        age = st.number_input(
            "Age", min_value=0, max_value=120, value=int(profile.get("age") or 0),
            help="0 = prefer not to say",
        )
        bio = st.text_area(
            "Bio", value=profile.get("bio", ""), max_chars=500, height=140,
            help="A few sentences about you and your financial goals.",
        )

        st.markdown("**Social links**")
        st.caption("A handle, a bare domain, or a full URL all work.")
        link_inputs = {}
        for key, label, base_url, placeholder in SOCIAL_PLATFORMS:
            link_inputs[key] = st.text_input(label, value=profile.get(key) or "", placeholder=placeholder)

        submitted = st.form_submit_button("Save profile")

    if submitted:
        photo_bytes, photo_mime = profile.get("photo"), profile.get("photo_mime")
        if uploaded_photo is not None:
            processed = _process_photo(uploaded_photo.getvalue())
            if processed is None:
                st.error("Couldn't read that image -- try a PNG or JPEG.")
                st.stop()
            photo_bytes, photo_mime = processed
        social_links = {
            key: _normalize_link(link_inputs[key], base_url)
            for key, _, base_url, _ in SOCIAL_PLATFORMS
        }
        db.save_profile(name.strip(), age or None, bio.strip(), photo_bytes, photo_mime, social_links)
        st.session_state["_profile_saved_flash"] = True
        st.rerun()

st.divider()
st.subheader("What this is for")
st.markdown(
    "Right now this page just personalizes the app -- your name and photo show up in the sidebar, and "
    "the social fields are plain links: paste a handle or URL and it becomes a clickable button above. "
    "That's it -- nothing is fetched from LinkedIn, Instagram, or Facebook, and no photo or bio is pulled "
    "in from them automatically. A real \"sync\" (auto-importing your photo/bio, or verifying the account "
    "is really yours) needs an OAuth app registered with each platform -- LinkedIn's API is tightly "
    "restricted for third-party apps, and Meta requires app review for Instagram/Facebook access -- plus "
    "somewhere to securely hold the resulting tokens. That's real infrastructure this self-hosted, "
    "no-accounts app doesn't have, and a bigger, separate decision from adding a link field.\n\n"
    "The longer-term idea behind the page as a whole is a community layer: a way for people who take "
    "their finances seriously to find and meet each other, using a profile like this one plus a "
    "privacy-controlled summary of financial health (like the on-track gauge on the Dashboard) instead "
    "of raw numbers. None of that exists yet -- there's no server, no other users, and nothing here is "
    "shared. This page is just the data model, built now so it wouldn't need to be rebuilt later."
)
st.checkbox(
    "Make my profile discoverable to other financially responsible people",
    value=False, disabled=True,
    help="Not built yet -- shown here to make the roadmap concrete. Toggling it does nothing right now.",
)
