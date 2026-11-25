---
name: service-delivery-setup
description: Walk Dylan step by step through getting a new client's service delivery ready for launch (number, AI text agent, booking, funnel, Meta access, sequences, AI voice agent, database reactivation, social media DM agent + organic posts, tests), scanning what's already done and ticking each step off in the dashboard's Marketing Setup tab as it's completed. Use when Dylan says "help me set up service delivery for <client>", "onboard <client>", "what's left to launch <client>", or similar.
---

# Service Delivery Setup

Gets a client from "closed" to "ready to launch ads" in the most efficient order, one
step at a time, with Dylan. The campaign build itself comes LAST and is handed to the
media-buying agent's `build-campaign-plan` skill (gated, see memory "Campaign Work Is
Gated").

The source of truth for what needs doing is the dashboard's **Setup** checklist (client →
Details → Setup; ~18 steps in 5 phases, defined in `dashboard/backend/setup_steps.py`,
served at `GET /api/clients/{id}/setup`). Steps have stable ids (`autobuild`, `review`,
`meta_access`, `calendar`, `dns`, `booking_domain`, `a2p`, `lists`, `booking`, `reviews`, `lead_form`, `pixel`, `voice`,
`social`, `ad_cap`, `campaign`, `organic`, `test`, `reactivation`, `golive`). Growth-only
steps are hidden for a Foundations client (`PUT /api/clients/{id}/setup/package`). This
skill never keeps its own list: it reads that one, so adding a step there adds it here.

## 1. Scan

```bash
doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py "<client name or id>"
```

Most steps prove themselves from live data every time the checklist is read (funnel +
number + agent + messages built, booking live, relay + form built, cap checked, ads
spending...; `signals()` in `setup_steps.py`); the funnel domain is checked by the
autocheck the script runs first. It prints the checklist by phase with `[x]`/`[ ]`, each
step's id and its proof or how-to, the outstanding **client ask** (one message listing only
what's still missing), the client's portal action items, onboarding form progress, the
client-visible launch checklist, Resources (including the auto-detected **DNS host**) and
the key config.

Buttons on the Setup tab that you can also call: `POST /api/clients/{id}/setup/booking-autofill`
(drafts hours, appointment type, patient contact info, page details), `.../setup/instant-form`
(builds the Meta Instant Form with the consent line), `.../setup/voice-agent` (builds/syncs
the Retell agent), `.../setup/test` then `.../setup/test/cleanup` (one-click end-to-end test on
+17542485326 and its cleanup).

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

1. **Long-lead steps first, always (Dylan, 2026-11-25).** Anything that needs someone
   else's approval or waits on time goes before everything else, because it can't be
   rushed at the last minute. These are the **long-lead steps** (the calendar-management
   skill uses the same list):
   - `a2p`: Twilio A2P 10DLC. **Never ask the client for the legal name / EIN before reading
     the status script's "A2P details" section** (their portal onboarding form, Legal section:
     legal name, business type, EIN, industry, website, address; Dylan, 2026-11-25). Ask only
     for what's blank there. Check the number is local first (a non-local number means swap
     it before registering, since the registration is tied to the number). Register the Brand right away. Submit the Campaign only once
     the Instant Form with its consent disclaimer is published and screenshotted: follow
     `onboarding-agent/context/a2p-registration-sop.md` (a campaign without public opt-in
     proof was rejected for Pinnacle, costing weeks). Publishing that form is long-lead too.
   - `meta_access`: the partner invite / ad account permissions (took Pinnacle weeks of
     back and forth), plus Meta Business verification and system-user access.
   - `campaign`: ads need Meta review. Upload at least 2 days before launch.
   - `dns` / `booking_domain`: DNS propagation.
   - Any **client ask** (calendar share, Stripe connect and its verification, DNS records,
     lists, EIN): batch every outstanding ask into ONE text/email draft for Dylan to send
     **the same session** (written for the client: plain characters only, no em dashes or
     curly quotes, per the SMS GSM-7 rule; short). Don't text the client yourself (memory
     "Don't Text Clients Unless Necessary").
   - Anything else waiting on a third-party review or approval (e.g. a provider's API change
     that breaks a live integration, payouts verification).
2. Steps Dylan can do right now with nothing from the client, in Setup Order order.
3. Tests, then pre-launch cleanup, then hand off to the campaign build.

**Booking: DigiGrowth Booking is the default (since 2026-11-06).** The client shares the
Google Calendar they book on with dylanrg@digigrowthllc.com ("Make changes to events",
their portal's "Share Your Google Calendar" step); Dylan sets it up in the OS's Booking Links
tab (calendar, hours, appointment type from the offer presets; page details fill themselves
from the portal, website and funnel), then turns it on. Paid visits: the client clicks
"Connect Stripe to Get Paid" in their portal (needs STRIPE_SECRET_KEY on the server). Check
which calendars the booking account sees with `GET /api/booking/google`. Response AI step 6
tick themselves once it's live (`calendar`, `booking`). Calendly/GoHighLevel only for a
client already running on them (GHL only when the client explicitly said so).

**Reviews loaded (`reviews` step, 2026-11-22): overload the booking page with every 5-star
Google review.** Dylan wants the booking page's social proof stacked as high as it goes (the
page shows one review; the rest open under "View more reviews"). Do this as soon as the booking
page exists. Google's API returns only 5 and logged-out Google Maps shows only 5, so:
1. Find the clinic's listing (Places text search, or the Booking step's Fetch from Google, which
   also saves the rating and pulls the API's 5). Note rating + total review count.
2. In Dylan's signed-in Chrome (Claude in Chrome, new tab):
   `https://www.google.com/maps/place/?q=place_id:<PLACE_ID>&hl=en` → Reviews tab. With
   `javascript_tool`: scroll the reviews pane (the scrollable ancestor of `div.jftiEf`) to the
   bottom until the count of `div.jftiEf` stops growing; click every `div.jftiEf` button whose
   text is "More" (skip ones inside owner responses, `.CDe7pd`) so full text shows; collect
   `{name: .d4r55, stars: span[role=img][aria-label*=star], text: .wiI7pd}` and keep only
   "5 stars" with text. Tool output caps around 1,000 characters and clipboard/localhost/
   download writes from page JS hang, so: replace the page body with one `<article>` holding
   `@@<n>|<name>|<text with newlines as " ¶ ">` per line plus a final `@@END`, click the page,
   press ctrl+a, ctrl+c (real key presses), then save the clipboard to a scratch file with
   PowerShell `Get-Clipboard -Raw` (UTF-8). Close the tab.
3. `doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/import_google_reviews.py <id> <file> --count <total> --rating <rating> --dry-run`,
   check, then run without `--dry-run`. It keeps what's on file first (the first review is the
   one the page shows), adds the rest deduplicated, first names only, drops full-name
   sign-offs. Words are never edited beyond that: real reviews only, word for word.
The step ticks itself at 20 reviews on file (or all of them when the clinic has fewer).
Website testimonials the page autofill finds count too.

**Clinic not on Google Calendar** (Outlook/Microsoft 365, Apple iCloud, practice software,
Yahoo etc.; the portal guide has a tab for each): the booking engine only reads/writes Google,
so the clinic sends a read-only ICS/webcal link instead of sharing. Dylan then, in the
dylanrg@ Google Calendar: (1) Other calendars → + → From URL, paste their link (swap
`webcal://` for `https://` if Google rejects it); (2) create a calendar "<Clinic> New Patients"
(owned by dylanrg@, so writable); (3) in Booking Links pick that new calendar under "Book
appointments into" and tick the subscribed one under "Also block times that are busy on…";
(4) send the clinic the new calendar's "Secret address in iCal format" so bookings show in
their Outlook/Apple calendar. Google refreshes URL subscriptions only every few hours, so
same-day blocks the clinic adds can be missed; they've been told to text us for short-notice
blocks. No calendar at all: same, minus steps 1 and the busy tick.

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
  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py <id> --tick a2p --tick review
  ```
  Re-running the script also re-runs autocheck. Only tick steps that can't prove
  themselves (`review`, `a2p`, `campaign`, `organic`, or a step that doesn't apply to this
  client, e.g. `voice` when Dylan keeps it off).
- Writes to production data (configs, deleting test leads, resetting stats, toggling the
  client's booking alert) are fine when they're part of the step Dylan asked for. Say
  what you changed. Anything outward-facing that isn't (texting the client, publishing,
  pushing code) needs his OK first.

The client's portal launch checklist (their To Do tab) ticks itself once the matching
Setup steps are done (`LAUNCH_ITEM_STEPS` in `setup_steps.py`, synced by
`guide_autocheck.sync_launch_checklist`): portal/landing page -> `autobuild`, SMS ->
`autobuild` + `a2p`, response AI -> `review` + `booking`, ad creatives -> `campaign`,
database reactivation -> `reactivation`. Items with no mapping (onboarding call, launch
campaign) are still ticked by hand: `PUT /api/clients/{id}/launch-checklist/{item_id}` with `{"completed": true}`
(ids from the scan).

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
  the Page + Instagram (Full control). Several ad accounts: pick the one with spend history, save its ID.
  Pilot clients: never ask the client for a card on file; the ads always run on Dylan's card
  (Dylan, 2026-11-06), so it's not a setup step or a blocker for them.
- **DNS**: edit records where the nameservers point (the DNS host resource), not
  necessarily the registrar. Wix needs Admin (Co-Owner) because domains count as billing
  permissions. A GoDaddy delegate invite can't be accepted when your login is the same
  GoDaddy account, and it expires in 48 h. Never touch the root `@` records.
- **Funnel domain (default for every client, 2026-10-26)**: the funnel stays in the OS
  (`/lp/<slug>`) and is also served on the client's own `go.<their domain>` through the
  shared `client-funnels` Vercel project (a proxy, not a copy; Railway's plan caps custom
  domains). Save it as `funnel_domain` (`PUT /api/clients/{id}/marketing-config`), run
  `doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/deploy_client_funnels.py`,
  then add a CNAME `go` -> `cname.vercel-dns.com` at the DNS host. Autocheck ticks
  `dns` once `https://go.<domain>/` serves the funnel. Update the portal Website
  tab URL to the new domain so the client sees it.
- **Booking domain (`booking_domain` step, 2026-11-17)**: same DNS access, second record:
  CNAME `book` -> `cname.vercel-dns.com`. Needs the booking page to exist (Booking AUTOFILL).
  Save `booking_domain` (e.g. `book.clientdomain.com`), run the same
  `deploy_client_funnels.py` (it serves `/book/<booking_slug>` at the root of that host).
  Then re-run `service_delivery_status.py` for the client: its autocheck call is the ONLY
  thing that checks this domain (not the 10-minute job). Once it serves their page the step
  ticks and every booking link we hand out switches to `https://book.<domain>`. If the
  domain later breaks, re-run the status script so links fall back to ours.
- **GoHighLevel (only when the client said so)**: one email = one GHL user, so if the
  invite lands in another agency, ask for an invite to `dylanrg+<client>@digigrowthllc.com`
  and open it in incognito. Calendar slugs are global (pick any unique one, the link uses
  the calendar ID). The booking-sync workflow URL comes from
  `GET /api/clients/{id}/ghl-webhook-url` (also shown in the Booking step). The calendar's
  confirmation email to the contact must be ON (it carries the Meet link); GHL reminders
  OFF (the dashboard sends them).
- **Silent end-to-end test**: the Setup tab's RUN TEST / CLEAN UP does this in one click
  (turn the booking alert off first). By hand: `PATCH /api/clients/{id}` `{"booking_notification_enabled": false}`,
  book with your own details, check `GET /portal-api/{token}/appointments`, then
  `POST /api/appointment-reminders/{appt}/cancel` (silent by default), `DELETE
  /api/contacts/{lead}` (removes its appointments), reset funnel stats with `PUT
  /api/clients/{id}/websites/{wid}/stats` `{"views": <current>, "conversions": 0}`, and turn the
  alert back on. Booking from a phone that belongs to another client's contact still lands
  in this client (fixed 2026-10-16).
- **Sequences**: the Sequences tab has on/off switches per message and per sequence. All
  client sequences are SMS only (no client email since 2026-10-28); make the copy match how
  the client works (no "give us a call" if they don't take calls).
- **Calls**: the onboarding Ops question asks where calls should forward; a phone number in
  the answer fills `call_forward_number` automatically. Until answered, calls forward to the
  client's phone on file.

## Voice agent, reactivation, social (added 2026-11-15)

Setup steps `voice`, `reactivation`, `social` + `organic` cover the service upgrades. Each
agent has its own row in the client's Agents & Messages tab.

- **Voice agent (growth package only; hidden for Foundations).** Auto-Setup builds the Retell
  agent on Closed (switched off).
  The call + text flow is Dylan's (memory "voice-agent-call-text-flow"): call ~3 min after a
  Meta lead with no text first, redial, voicemail, then the text opener; retries +2h / next
  day / day after; stops on a text reply or booking. Funnel leads are called only if they
  ticked the booking page's call-consent box. Meta leads are called only after the
  consent line is on their Instant Form AND Dylan clicked CONSENT LINE IS LIVE NOW, so
  never stamp it before the new form is actually live. Status + call log:
  `GET /api/clients/{id}/voice-agent`; rebuild the Retell agent after context edits:
  `POST /api/clients/{id}/voice-agent/sync`; test call: `POST /api/clients/{id}/voice-agent/test-call`
  `{"phone": "+17542485326"}`. Needs `RETELL_API_KEY` in Doppler AND Railway.
- **Reactivation.** The client's exports go in the batched client ask. Lists are texted only,
  never voice-called. Growth: starts itself at the first ad dollar / the cap. Foundations:
  START by hand once lists are in and A2P covers marketing (Dylan, 2026-11-16).
- **Social.** DMs already work through the Meta app (Demo Clinic got real ones). If a
  no-role account's DM never arrives, App Review is the blocker, not setup. Organic posts are
  scheduled by hand in Business Suite Planner for now and are framed as an ad booster.

## Done = ready for the campaign

Every Setup step done, except ones that are genuinely waiting on time (A2P review, DNS propagation). Tell Dylan that clearly, list anything still waiting, and
offer to start `build-campaign-plan` for the client (media-buying agent, gated). Don't start
it unasked.
