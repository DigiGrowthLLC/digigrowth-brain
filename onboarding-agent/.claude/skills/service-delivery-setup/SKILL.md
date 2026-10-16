---
name: service-delivery-setup
description: Walk Dylan step by step through getting a new client's service delivery ready for launch (number, AI text agent, booking, funnel, Meta access, email, sequences, tests), scanning what's already done and ticking each step off in the dashboard's Marketing Setup tab as it's completed. Use when Dylan says "help me set up service delivery for <client>", "onboard <client>", "what's left to launch <client>", or similar.
---

# Service Delivery Setup

Gets a client from "closed" to "ready to launch ads" in the most efficient order, one
step at a time, with Dylan. The campaign build itself comes LAST and is handed to the
media-buying agent's `build-campaign-plan` skill (gated, see memory "Campaign Work Is
Gated").

The source of truth for what needs doing is the dashboard's **Marketing Setup → Setup
Order** checklist (`MARKETING_GUIDES` + `SETUP_ORDER_PHASES` in
`dashboard/frontend/src/panels/ClientsPanel.jsx`). This skill never keeps its own list:
it reads that one, so adding a step there adds it here.

## 1. Scan

```bash
doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py "<client name or id>"
```

It runs the dashboard's autocheck first (ticks every step the data proves done:
number bought, AI replied to a real text, booking link saved, Lead Ads relay built,
ad account saved, and so on; see `dashboard/backend/guide_autocheck.py`), then prints:
the Setup Order by phase with `[x]`/`[ ]` and each step's `guide:index`, the client's
portal action items, onboarding form progress, the client-visible launch checklist,
Resources (including the auto-detected **DNS host**) and the key config.

Then check the outside world the script can't see, only as far as the next steps need:
- **Inbox** (Gmail connector, dylanrg@): access invites from the client (Meta portfolio,
  Wix/Squarespace/GoDaddy/Cloudflare, Calendly, GoHighLevel/"Activate your account",
  Google). Resources auto-fill from these, but an invite still has to be accepted.
- **Meta** (Meta Ads MCP, read-only): `ads_get_ad_accounts` / `ads_get_user_pages` show
  whether the client's ad account and Page are reachable yet.
- **DNS**: the DNS host resource, or `nslookup -type=NS <domain> 8.8.8.8`.

## 2. Plan, then lead with the next step

Post a short status: what's done (count, not a list), what's blocked on the client (one
line each, with the exact ask), and **the single next step Dylan can do now**. Then walk
that step. Order:

1. Steps Dylan can do right now with nothing from the client, in Setup Order order.
2. Client asks: batch every outstanding ask into ONE text/email draft for Dylan to send
   (written for the client: plain characters only, no em dashes or curly quotes, per the
   SMS GSM-7 rule; short). Don't text the client yourself (memory "Don't Text Clients
   Unless Necessary").
3. Time-gated steps (A2P review, DKIM 24-72 h after MX) get started as early as possible.
4. Tests, then pre-launch cleanup, then hand off to the campaign build.

**Booking: Calendly is the default.** Take the GoHighLevel path (Response AI steps 14-16)
only when the client has explicitly said they book on GoHighLevel. Ask if unsure; never
assume GHL because an invite exists.

## 3. Walk one step at a time

For each step:
- Give the exact clicks/links, the values to paste, and what "done" looks like. Keep it to
  what Dylan needs for this one step; offer the next only after this one is done.
- When Dylan sends a screenshot, read it closely and correct course (wrong panel, wrong
  account, missing field) before moving on.
- Do the parts that can be done from here instead of handing them to Dylan: dashboard API
  calls (via `doppler run`, never a typed password), config saves, autocheck, test-record
  cleanup, DNS lookups, reading invites.
- **Verify, then tick.** Confirm it's actually done (API, Meta MCP, inbox, DNS lookup, or a
  test), then tick it:
  ```bash
  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py <id> --tick response_ai:13 --tick response_ai:14
  ```
  Re-running the script also re-runs autocheck. Ticking a step in Setup Order ticks the
  same slot in its own guide. Mark the unused booking path (Calendly vs GHL steps) done
  once the other path is live, and the take-number step (sms:7) once a number exists.
- Writes to production data (configs, deleting test leads, resetting stats, toggling the
  client's booking alert) are fine when they're part of the step Dylan asked for. Say
  what you changed. Anything outward-facing that isn't (texting the client, publishing,
  pushing code) needs his OK first.

When a whole area is done, also tick the matching item on the client's portal launch
checklist (the client sees it on their To Do tab):
`PUT /api/clients/{id}/launch-checklist/{item_id}` with `{"completed": true}` (ids from
the scan; check the route in `dashboard/backend/routers/clients.py` before calling).

## Playbook: what worked (2026-10-16, Advantage Therapy)

- **Number**: Auto-Setup buys one on Closed. To reuse a former client's A2P-registered
  number instead: `POST /api/clients/{id}/marketing-config/take-number?from_client_id={old}`.
  Never transfer it between Twilio subaccounts (it would lose the registration). Turn the
  old client's AI agent off first, and warn Dylan that the registration still names the old
  business. Test: text the number from the Inbox's New Message box (give it a name so
  it lists) and check the reply is the right client's agent:
  `GET /api/clients/{id}/sms-messages`.
- **Meta**: the client sends a business portfolio invite to dylanrg@. Accept it, then check
  your role under Users → People. "Partial access: Basic" means the client has to assign
  the Page + Instagram (Full control). Several ad accounts: pick the one with spend history
  and a card on file (`ads_get_ad_accounts` shows `has_payment_method`), save its ID.
- **DNS**: edit records where the nameservers point (the DNS host resource), not
  necessarily the registrar. Wix needs Admin (Co-Owner) because domains count as billing
  permissions. A GoDaddy delegate invite can't be accepted when your login is the same
  GoDaddy account, and it expires in 48 h. Email DNS = Google Admin secondary domain on
  DigiGrowth's Workspace, then TXT verify + MX `smtp.google.com` + SPF at the DNS host,
  host `mail`; never touch the root `@` records.
- **GoHighLevel (only when the client said so)**: one email = one GHL user, so if the
  invite lands in another agency, ask for an invite to `dylanrg+<client>@digigrowthllc.com`
  and open it in incognito. Calendar slugs are global (pick any unique one, the link uses
  the calendar ID). The booking-sync workflow URL comes from
  `GET /api/clients/{id}/ghl-webhook-url` (also shown in the guide step). The calendar's
  confirmation email to the contact must be ON (it carries the Meet link); GHL reminders
  OFF (the dashboard sends them).
- **Silent end-to-end test**: `PATCH /api/clients/{id}` `{"booking_notification_enabled": false}`,
  book with your own details, check `GET /portal-api/{token}/appointments`, then
  `POST /api/appointment-reminders/{appt}/cancel` (silent by default), `DELETE
  /api/contacts/{lead}` (removes its appointments), reset funnel stats with `PUT
  /api/clients/{id}/websites/{wid}/stats` `{"views": <current>, "conversions": 0}`, and turn the
  alert back on. Booking from a phone that belongs to another client's contact still lands
  in this client (fixed 2026-10-16).
- **Sequences**: the Sequences tab has on/off switches per message and per sequence; turn
  email steps off until the mailbox is connected, and make the copy match how the client
  works (no "give us a call" if they don't take calls).
- **Calls**: the onboarding Ops question asks where calls should forward; a phone number in
  the answer fills `call_forward_number` automatically. Until answered, calls forward to the
  client's phone on file.

## Done = ready for the campaign

Every Setup Order step ticked, except ones that are genuinely waiting on time (A2P review, DKIM, warm-up). Tell Dylan that clearly, list anything still waiting, and
offer to start `build-campaign-plan` for the client (media-buying agent, gated). Don't start
it unasked.
