"""
Run this locally to get a refresh token for ONE Microsoft 365 mailbox, to
paste into the "+ Add Identity" form (SOPsPanel.jsx -> Outreach Templates ->
Email Handoff -> View Warm-Up Status), or POST /api/email-identities
directly.

Usage (PowerShell):
  $env:MS_CLIENT_ID = "..."
  $env:MS_TENANT_ID = "..."
  python reauth_microsoft.py

Uses an interactive browser login (msal's acquire_token_interactive, a local
loopback redirect) rather than the device-code flow — device code is
increasingly blocked by default Conditional Access policies on new tenants
(a known anti-phishing measure, since device code doesn't show the familiar
browser address bar), which is what error AADSTS530035 means if you hit it.
Interactive browser login is the standard sign-in experience and essentially
never gets blocked by default policies.

Requires the Azure AD app registration to have a "Mobile and desktop
applications" platform configured with the redirect URI
http://localhost (Authentication -> Add a platform -> Mobile and desktop
applications -> check the http://localhost option, or add it manually).
Also still requires "Allow public client flows" = Yes (same as before).
"""
import os

CLIENT_ID = os.environ.get("MS_CLIENT_ID", "")
TENANT_ID = os.environ.get("MS_TENANT_ID", "")

SCOPES = [
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Mail.Read",
]
# offline_access is deliberately NOT listed here — msal's PublicClientApplication
# treats it as a reserved scope and adds it automatically for any flow that can
# return a refresh token, so passing it explicitly raises a ValueError.

if not CLIENT_ID or not TENANT_ID:
    print("Set MS_CLIENT_ID and MS_TENANT_ID env vars.")
    raise SystemExit(1)

try:
    import msal
except ImportError:
    print("Run:  pip install msal")
    raise SystemExit(1)

app = msal.PublicClientApplication(
    client_id=CLIENT_ID,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
)

print("Opening a browser window to sign in — log in as the mailbox you're adding.")
result = app.acquire_token_interactive(scopes=SCOPES)

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
