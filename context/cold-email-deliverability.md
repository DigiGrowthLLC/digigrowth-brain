# Cold Email Deliverability: SOP + DigiGrowth Status

Source: Imperium Agency "Deliverability" SOP (PDF Dylan shared 2026-10-29), adapted to DigiGrowth's
own sending stack (Email Handoff sequence, `email_send_identities`, homemade warm-up). Read this before
changing anything about cold email: identities, sequence copy, caps, DNS, or the video link.

**Core rule:** if the video watch rate is weak but the copy and offer are strong, suspect deliverability
first. Zero replies of *any* kind (not even "not interested") over 100+ sends almost always means the
mail isn't reaching the inbox.

## The SOP (condensed)

### Warm-up
- Warm every mailbox for **at least 14 days** before cold sending, on a real warm-up network
  (the SOP uses **Instantly**, Growth plan with unlimited accounts + warm-up; it's used ONLY for warm-up, not sending).
  Instantly settings: "Increase per day" = 1; reply rate 30%, **raised to 40% on accounts that are actively cold-sending**.
- **Warm-up never stops**, even on sending accounts. It runs in the background permanently.
- Subscribe every mailbox to frequent newsletters (Axios, Buzzfeed, The Skimm, Daily Beast, Morning Brew;
  confirm each) so it has real inbound mail. Filter them (and "Dmarc AND report") to skip inbox + mark read.
- Filter warm-up mail by the Instantly warm-up tag into a grey "Instantly Warmup" label.
- Keep **inactive reserve accounts** warming at all times so a burned account can be swapped out without stopping outreach.

### Monitoring
- Daily: warm-up health score per account must be **>= 90%**. Below 90% → finish its follow-ups, put it back in
  warm-up only, and bring in a reserve account.
- Weekly: domain health (mxtoolbox.com/domain, dnschecker.org domain-health-checker).
- On **3+ blacklists**, the domain is done: replace it and let the old one cool off in warm-up.
- Seed test: send the real email (with a real video link) to 4-5 friends' personal Gmail/Outlook addresses and see where it lands.

### Sending checklist (all must be true, otherwise start fresh with new accounts)
- Warmed 2+ weeks and subscribed to newsletters.
- Cold mail only from cold accounts; replies are handled from a warm account.
- SPF, DKIM and DMARC on every sending domain.
- Never used bulk-sending tools from your own domain or IP.
- Bounce rate **< 8%**, every address verified first (NeverBounce or similar). No duplicate sends.
- Copy scores "great" on a spam tester (e.g. mail-tester.com).
- Signature: plain text only. No images, links, social icons or code.
- No short links. **The only link in the first email is the video link. No calendar link in the first email.**
- **<= 20 emails/day per account**, at least 1 min between any two sends and 10 min between sends from the same account.
- Reply to every reply (respectfully); never reply to or follow up with rude ones.
- **No open-tracking pixel.**
- Personalized every time: name, company, video.
- **No weekend sends.** Steady daily volume, never batched or "saved up".
- Send live rather than scheduling.
- Accounts have a profile picture, a real name and a backup email.
- Send to a person (john@) rather than a generic inbox (info@, support@) wherever possible.
- No attachments. Normal capitalization. Simple subject ("Question for {name/company}").
- Avoid login alerts from far-apart IPs.

## How DigiGrowth's setup compares (updated 2026-10-29, after the fixes)

DigiGrowth does NOT pay for Instantly (Dylan, 2026-10-29). `identity_warmup.py` replicates what Instantly
does; see "Instantly replacement" below.

| SOP item | DigiGrowth now | Status |
|---|---|---|
| Warm-up network | Own pool: every mailbox in Email Identities (sending + partner inboxes) emails the others | BUILT. Only as big as the partner inboxes added (Instantly = thousands of strangers) |
| Warm-up content | Claude-written everyday threads (2-4 messages), threaded under the original, 7-char filter tag | BUILT (was 3 canned lines, subject "Re: warmup") |
| Spam/Promotions rescue, open, mark important | Done on every received warm-up email; Gmail fully, Microsoft after Mail.ReadWrite re-consent | BUILT |
| Ramp + reply rate | start 2, +1/day, max 20; reply rate 30%, 40% on active mailboxes | BUILT (settings: `identity_warmup_settings`) |
| Warm-up never stops | Continues at daily limit forever, active or not | BUILT |
| Health score >= 90% daily | Per mailbox, 7-day % not in spam; daily 5:30pm ET check | BUILT |
| < 90% or bounces > 8% → stop sending, use a reserve | Auto-demotes to warming (follow-ups still finish) + To-Do | BUILT. Needs reserve mailboxes to exist |
| Newsletter inflow | Auto-archive + mark read of Axios/Buzzfeed/Skimm/Daily Beast/Morning Brew + DMARC mail (Gmail) | Filtering BUILT; subscribing is manual |
| Reserve accounts | 1 active (Google), 1 warming (Microsoft, history of 550 5.7.708 blocks) | GAP (manual) |
| <= 20/day, ramp | Cap 20; newly activated mailboxes ramp 8 → +2 per business day | BUILT |
| No weekend sends | Cold sends Mon-Fri only | BUILT |
| 10 min between sends | `MIN_SEND_SPACING` = 10 min campaign-wide | OK |
| No open pixel | Removed 2026-09-24 | OK |
| SPF/DKIM/DMARC | All pass; DMARC `p=none` | OK (move to quarantine after clean weeks) |
| Domain blacklists | Spamhaus DBL / SURBL / URIBL checked daily + shown in Domain Health; To-Do if listed | BUILT |
| Verify addresses, bounce < 8% | Free checks before Touch 1 (`email_verify.py`): syntax, domain accepts mail, never bounced, no duplicate. Bounces now recorded and stop the sequence | BUILT (no paid verifier) |
| Person, not info@ | 108/317 recipients generic | GAP (lead sourcing) |
| Simple subject, no formatting | Touch 1 subject "Question for {first_name}", bold removed (2026-10-29) | DONE |
| Spam-tester score "great" | "free" x3 + "guarantee" x2 still in Touch 1 (Dylan's wording) | Dylan to test + decide |
| Only link = video link | `loom.digigrowthllc.com` on a young domain | RISK, accepted |
| Plain signature, profile pic, real name, backup email | Signature plain | Profile/backup: manual |

## Instantly replacement (identity_warmup.py)

- **Pool:** all non-paused rows in Email Identities. Warming/active mailboxes send on the ramp; partner inboxes
  send `partner_daily` (5) openers/day into the sending mailboxes. Recipients rotate, other domains first.
- **Content:** Claude (`claude-haiku-5-5`) writes each opener/reply on a random everyday topic; local phrase bank if the API fails.
  No links or sales words. Last line = 7-char tag (letters + digit) tying it to its thread.
- **Threads:** each opener plans 1 message (no reply) or 2-4 (reply rate %). Replies wait 10-120 min, go out threaded (Gmail In-Reply-To/threadId, Graph /reply).
- **Receiving:** finds warm-up mail in inbox, Promotions or spam; records `placement`; rescues it, marks read + important, files under grey "Warmup" label.
- **Hours:** Mon-Fri 8am-6pm ET, randomly spread. Inbox polling for real lead replies/bounces runs 24/7.
- **Health check:** `run_health_check()` daily 5:30pm ET (or POST /api/email-identities/health-check).
- **Settings:** JSON in `dialer_settings` key `identity_warmup_settings`: start, increase_per_day, daily_limit (max 25), reply_rate, reply_rate_active, partner_daily.
- **Seed tests:** POST /api/dialer/email-handoff-test/{contact_id} with {"to": "seed@address"} sends that prospect's real Touch 1 to a seed inbox.

## Results that triggered this (relaunch 2026-10-20 → 10-29)
- Email Touch 1: **183 sent, 2 video plays (1.1%), 0 replies, 1 positive (manually flagged)**, all from dylan@mail.digigrowthllc.com.
- Domains not on the Spamhaus DBL / SURBL / URIBL lookups; video page loads (200, ~0.25s).
- Read: placement problem (spam/promotions), not a copy problem. Confirm with a seed test before changing copy.

## Where things live
- Sequence + caps: `dashboard/backend/email_handoff_sequence.py` (`DAILY_CAP_PER_IDENTITY`, `daily_cap()`, `is_send_day()`, `MIN_SEND_SPACING`)
- Warm-up: `dashboard/backend/identity_warmup.py` (`_DEFAULT_SETTINGS`, `run_health_check`); mailbox actions in `email_identities.py` (`warmup_scan/engage/reply`)
- Address checks: `dashboard/backend/email_verify.py`; blacklists: `domain_health.check_blacklists`
- Identities / domain health: `GET /api/email-identities`, `GET /api/email-identities/domain-health`
- Email stats: `GET /api/analytics/outreach?days=N` → `email`; video views: `GET /api/content-analytics/loom-outreach`
- Templates: `GET /api/dialer/email-handoff-template` (stored in `dialer_settings`)
- Copy rules: `copy-agent/.claude/skills/cold-email/SKILL.md` (Deliverability rules section)
