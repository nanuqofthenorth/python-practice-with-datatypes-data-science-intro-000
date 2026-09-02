#!/bin/sh
# Runs once per container start. secrets.toml is gitignored and never
# built into the image -- if you want Google Sign-In on a host that (unlike
# Streamlit Community Cloud) has no secrets-file UI of its own, set these
# environment variables instead and this writes the file Streamlit's
# st.login() actually reads it from. No-op (and Google Sign-In stays off)
# if GOOGLE_OAUTH_CLIENT_ID isn't set -- everything else in the app works
# the same either way.
set -e

if [ -n "$GOOGLE_OAUTH_CLIENT_ID" ]; then
    mkdir -p .streamlit
    redirect_uri="${APP_BASE_URL%/}/oauth2callback"
    cat > .streamlit/secrets.toml <<EOF
[auth]
redirect_uri = "$redirect_uri"
cookie_secret = "$GOOGLE_OAUTH_COOKIE_SECRET"
client_id = "$GOOGLE_OAUTH_CLIENT_ID"
client_secret = "$GOOGLE_OAUTH_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
EOF
fi

exec streamlit run app.py \
    --server.port="${PORT:-8501}" \
    --server.address=0.0.0.0 \
    --server.headless=true
