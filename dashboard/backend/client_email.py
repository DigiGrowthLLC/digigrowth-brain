"""
Sends email through a REAL client's OWN Google Workspace mailbox on their
own domain — deliberately separate from integrations.py's gmail_send*
functions, which always send from DigiGrowth's own shared mailbox
(GOOGLE_REFRESH_TOKEN env var). This mirrors that same Gmail-API approach,
but the refresh token is per-client (stored in
client_marketing_config.gmail_refresh_token, obtained by running
reauth_google.py logged into the client's own mailbox) rather than a single
global env var — see the "Set up email marketing" launch-checklist item's
description for the manual setup steps.

Shares the same OAuth app (GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET) as the
internal OS — only the refresh token (i.e. which mailbox) differs per client.
"""
import base64
import os
from email.mime.text import MIMEText

from db import get_pool

_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]


def _client_creds(refresh_token: str):
    from google.oauth2.credentials import Credentials

    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        if not os.environ.get(key):
            raise RuntimeError(f"Missing env var: {key}")

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_GOOGLE_SCOPES,
    )


def _client_gmail_service(refresh_token: str):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=_client_creds(refresh_token), cache_discovery=False)


async def send_client_email(client_id: int, to: str, subject: str, body: str) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT gmail_refresh_token FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
        if not config or not config["gmail_refresh_token"]:
            raise RuntimeError(f"Client {client_id} has no connected Gmail mailbox yet")

        svc = _client_gmail_service(config["gmail_refresh_token"])
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()

        await conn.execute(
            """
            INSERT INTO client_email_messages (client_id, to_email, subject, body, gmail_message_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            client_id, to, subject, body, sent["id"],
        )
        return f"Sent email to {to}: {subject}"
