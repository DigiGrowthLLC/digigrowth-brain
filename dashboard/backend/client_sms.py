"""
Provisions a REAL client's own Twilio number — deliberately separate from
routers/sms.py, which sends/receives on DigiGrowth's own shared Twilio
number for DigiGrowth's own outreach. Nothing here ever touches
TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN's number (os.environ["TWILIO_PHONE_NUMBER"])
or writes to sms_messages/sms_conversations.

Uses a Twilio Subaccount per client (created under DigiGrowth's master
Twilio account via TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN) so each client's
usage/billing is cleanly isolated and a client's number can be fully
suspended/closed without touching any other client's or DigiGrowth's own
Twilio usage.
"""
import os

from twilio.rest import Client as TwilioClient

from db import get_pool


def _master_client() -> TwilioClient:
    return TwilioClient(
        os.environ["TWILIO_ACCOUNT_SID"],
        os.environ["TWILIO_AUTH_TOKEN"],
    )


async def provision_client_number(client_id: int, area_code: str | None = None) -> dict:
    """
    Idempotent: if the client already has a subaccount/number in
    client_marketing_config, returns the existing values instead of buying a
    second number. Buys the first available local number in `area_code` (or
    Twilio's default search if omitted) under a new (or existing) subaccount
    named for the client.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        client = await conn.fetchrow("SELECT id, name FROM clients WHERE id = $1", client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")

        config = await conn.fetchrow(
            "SELECT twilio_subaccount_sid, twilio_number FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
        if config and config["twilio_subaccount_sid"] and config["twilio_number"]:
            return dict(config)

        master = _master_client()

        subaccount_sid = config["twilio_subaccount_sid"] if config else None
        if not subaccount_sid:
            subaccount = master.api.accounts.create(
                friendly_name=f"DigiGrowth Client — {client['name']}"
            )
            subaccount_sid = subaccount.sid

        # Number purchases must be made as the subaccount, using its own
        # auth token (not the master's) — Twilio subaccounts have their own
        # auth_token, fetched via the master client.
        subaccount_client = TwilioClient(
            subaccount_sid,
            master.api.accounts(subaccount_sid).fetch().auth_token,
        )

        search_kwargs = {"limit": 1}
        if area_code:
            search_kwargs["area_code"] = area_code
        candidates = subaccount_client.available_phone_numbers("US").local.list(**search_kwargs)
        if not candidates:
            raise RuntimeError(f"No available Twilio numbers found for client {client_id}")

        purchased = subaccount_client.incoming_phone_numbers.create(
            phone_number=candidates[0].phone_number,
            sms_url=f"{os.environ.get('DASHBOARD_URL', '').rstrip('/')}/webhooks/client-sms/{client_id}",
        )

        row = await conn.fetchrow(
            """
            INSERT INTO client_marketing_config (client_id, twilio_subaccount_sid, twilio_number, updated_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (client_id) DO UPDATE
                SET twilio_subaccount_sid = EXCLUDED.twilio_subaccount_sid,
                    twilio_number = EXCLUDED.twilio_number,
                    updated_at = now()
            RETURNING *
            """,
            client_id, subaccount_sid, purchased.phone_number,
        )
        return dict(row)


async def send_client_sms(client_id: int, to_number: str, body: str, stage: str | None = None) -> None:
    """Sends from the client's own provisioned number, via their own subaccount."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT twilio_subaccount_sid, twilio_number FROM client_marketing_config WHERE client_id = $1",
            client_id,
        )
        if not config or not config["twilio_subaccount_sid"] or not config["twilio_number"]:
            raise RuntimeError(f"Client {client_id} has no provisioned Twilio number yet")

        master = _master_client()
        subaccount_client = TwilioClient(
            config["twilio_subaccount_sid"],
            master.api.accounts(config["twilio_subaccount_sid"]).fetch().auth_token,
        )
        message = subaccount_client.messages.create(
            to=to_number, from_=config["twilio_number"], body=body,
        )

        await conn.execute(
            """
            INSERT INTO client_sms_messages (client_id, from_number, to_number, direction, body, twilio_sid, stage)
            VALUES ($1, $2, $3, 'outbound', $4, $5, $6)
            """,
            client_id, config["twilio_number"], to_number, body, message.sid, stage,
        )
