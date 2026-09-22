"""
Run this locally to get a refresh token for ONE Microsoft 365 mailbox, to
paste into the "+ Add Identity" form (SOPsPanel.jsx -> Outreach Templates ->
Email Handoff -> View Warm-Up Status), or POST /api/email-identities
directly.

Usage (PowerShell):
  $env:MS_CLIENT_ID = "..."
  $env:MS_CLIENT_SECRET = "..."
  $env:MS_TENANT_ID = "..."
  python reauth_microsoft.py

Uses msal.ConfidentialClientApplication (client_secret + auth-code-with-PKCE
via a local loopback redirect), matching exactly how the backend
(email_identities.py's _graph_access_token) later redeems the resulting
refresh token — also as a confidential client with the same secret.

This deliberately does NOT use PublicClientApplication / device-code /
"Allow public client flows" — Azure AD treats that as an all-or-nothing
setting: once an app allows public client flows, it REJECTS any client
secret presented for ANY token request from that app (error AADSTS700025),
which breaks the backend's confidential-client redemption. Keep "Allow
public client flows" set to No on this app registration.

Requires the Azure AD app registration to have a "Web" platform (not
"Mobile and desktop applications") configured with redirect URI
http://localhost:8765 (Authentication -> Add a platform -> Web).
"""
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

CLIENT_ID = os.environ.get("MS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET", "")
TENANT_ID = os.environ.get("MS_TENANT_ID", "")
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"

SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
]
# offline_access is deliberately NOT listed here — msal treats it as a
# reserved scope and adds it automatically for any flow that can return a
# refresh token, so passing it explicitly raises a ValueError.

if not CLIENT_ID or not CLIENT_SECRET or not TENANT_ID:
    print("Set MS_CLIENT_ID, MS_CLIENT_SECRET, and MS_TENANT_ID env vars.")
    raise SystemExit(1)

try:
    import msal
except ImportError:
    print("Run:  pip install msal")
    raise SystemExit(1)

app = msal.ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
)

flow = app.initiate_auth_code_flow(scopes=SCOPES, redirect_uri=REDIRECT_URI)

_captured = {}


class _RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        _captured.update({k: v[0] for k, v in query.items()})
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>Signed in. You can close this tab and return to the terminal.</body></html>")

    def log_message(self, *args):
        pass  # silence default request logging


server = HTTPServer(("localhost", REDIRECT_PORT), _RedirectHandler)

print(f"Opening a browser window to sign in — log in as the mailbox you're adding.\n{flow['auth_uri']}")
webbrowser.open(flow["auth_uri"])

server.handle_request()  # blocks until the browser hits the redirect exactly once

result = app.acquire_token_by_auth_code_flow(flow, _captured)

if "refresh_token" not in result:
    print(f"Auth failed: {result.get('error_description', result)}")
    raise SystemExit(1)

print("\n" + "=" * 60)
print("NEW REFRESH TOKEN:")
print("=" * 60)
print(result["refresh_token"])
print("=" * 60)
print("\nPaste this into the '+ Add Identity' form as the OAuth refresh token,")
print(f"along with ms_tenant_id = {TENANT_ID} (or your single shared MS_TENANT_ID env var).")
