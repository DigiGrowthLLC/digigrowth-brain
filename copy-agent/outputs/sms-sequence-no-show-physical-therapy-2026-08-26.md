# No-Show Sequence — Independent PT Practice Owners (DigiGrowth's Own Discovery-Call Funnel)

**For:** DigiGrowth's own outbound funnel targeting independent PT practice owners (the `leadgen-agent`/dialer ICP)
**Audience:** a PT practice owner who booked a discovery call with DigiGrowth (via the dialer / cold outreach) and no-showed — **not** a patient, and not a mid-treatment relationship
**Structure:** matches the DigiGrowth OS's `no_show_sequence.py` engine — 4 touches, same 0h/3h/24h/72h timing, same channel-per-touch pattern, same stop-on-reply behavior. Drops into Business Resources → Outreach Templates → No Show (Touch 1-4).

**Merge fields used:** `{first_name}`, `{link}` → `integrations.CALENDLY_URL`

**Offer this leans on** (`outputs/offer-mobile-pt-testimonial-2026-07-30.md`, `outputs/cold-calling-script-v1.0-physical-therapy-2026-07-30.md`): done-for-you, pay-by-performance client acquisition filling the referral-cycle gap with 15-30 new-patient consultations/month.

**Revision 3 (2026-08-26)** — full rebuild against `.claude/skills/outbound-sequences/references/no-show-psychology.md`, not a patch on v2. Every line below is there because of a specific mechanism in that research, not house style:

| Mechanism | Where it shows up |
|---|---|
| Weak commitment (passive link click) is *why* they didn't show | Every touch replaces "click a link" with "tell me a day/time" as the primary ask — link is the fallback, not the headline action |
| Active + verbal commitment cuts no-shows ~30% (restaurant study, healthcare pilot) | Touch 1 and the rebooking confirmation both use a yes/no question format ("Does Tuesday still work for you?") instead of a statement |
| Specific loss beats generic reminder (8.2% vs 9.9% no-show rate) | Every touch names the 15-30/month figure or "referral-cycle gap" — never a bare "let's reschedule" |
| Temporal discounting — the original pain decays fast | Touch 1 reactivates the pain within the first line, before mentioning the miss at all |
| Shame increases avoidance, not follow-through | Zero guilt/confessional language anywhere; miss is acknowledged once, briefly, never dwelt on |
| Dissonance hardens into "not interested" the longer it sits | Touch 1 fires same-day (0h) — unchanged from the OS default, now understood as load-bearing, not just "fast is nice" |

---

## Touch 1 — 0h (SMS + Email)
Opens on the pain, not the miss. Acknowledges the no-show in one clause, then asks a direct yes/no-style question instead of handing over a bare link.

**SMS:**
> {first_name} — most PT practices lose real volume in the gap between referral cycles. That's what today's call was about. Does tomorrow around this time work instead?

**Email subject:** {first_name} — still want to close the referral-gap conversation

**Email body:**
> Hey {first_name},
>
> Didn't want to let this drop — the reason I called is that most independent PT practices lose real new-patient volume in the slow stretches between referral cycles, and that's fixable without adding to your plate.
>
> We missed each other today, no issue at all. Does tomorrow around the same time work, or is there a better day this week? Reply here, or grab a time directly: {link}
>
> Talk soon,
> Dylan

---

## Touch 2 — 3h (SMS only)
SMS-only by design (same-day second channel reads as pressure). States the specific number and asks for a one-word commitment.

**SMS:**
> {first_name} — every month without something in place is 15-30 new-patient consultations you're not booking. Worth 15 min to see if it fits? Reply YES and I'll grab you a time: {link}

---

## Touch 3 — 24h (SMS + Email)
Normalizes the miss briefly, restates the specific loss, keeps the reply-first / link-fallback pattern.

**SMS:**
> {first_name}, discovery calls fall through the cracks for a lot of clinic owners — the referral-gap doesn't close itself in the meantime though. What's a good day this week? ({link} if easier)

**Email subject:** The gap's still there, {first_name}

**Email body:**
> Hey {first_name},
>
> You're not the first clinic owner to miss this one — happens constantly running a full patient schedule. The thing worth 15 minutes hasn't changed though: closing the gap between referral cycles with 15-30 direct-to-consumer consultations a month.
>
> Reply with a day/time that works, or grab one directly: {link}
>
> If it's genuinely not a priority right now, just say so and I'll close this out — no hard feelings.

---

## Touch 4 — 72h (SMS + Email)
The "breakup" touch. No pressure, no guilt, reply-first still, closes the loop cleanly.

**SMS:**
> {first_name} — closing this out unless I hear back. No pressure — just reply here if it's still worth 15 min, or grab a time: {link}

**Email subject:** Closing your file, {first_name}

**Email body:**
> Hey {first_name},
>
> Haven't heard back, so I'll close this out on my end for now. If the timing's just bad right now, that's completely fine — reply here whenever it opens up, or grab a time directly: {link}
>
> Dylan

---

## Rebooking confirmation (when they reply with a day/time)
Not one of the 4 timed touches, but the moment the active-commitment research cares about most — this is where a real verbal "yes" gets attached to the new slot, same mechanism as the restaurant study's "*will you* call if your plans change?" Don't just confirm the time; ask for the commitment explicitly:

> Great, locking in {when} — does that still work on your end? [wait for yes] Perfect, see you then — and if anything comes up, just reply here so we can find another time instead of missing it.

This closes the exact loop the research identifies: the first booking failed because it was a passive click with no active "yes" attached. The rebooked slot shouldn't repeat that.

## Notes
- **Open gap, flagged again:** this sequence's core mechanism — "reply with a day/time" — only works if a freeform SMS reply actually gets turned into a rebooked appointment quickly (ideally a human or automation acting on it same-day), not left sitting in the SMS inbox unread. Confirm this before running it live; if replies currently just land as inbound messages nobody's watching closely, the active-commitment ask is copy without a system behind it.
- Sequence still stops immediately on any reply, either channel, per the OS engine's `stop_sequence_for_reply` — every touch above stands alone.
- Don't judge this off a few days of data (2-4 week lag, per the cold-calling script's Prime Directive). Log actual reply/rebook rates back into `no-show-psychology.md`'s Update Log once it's run.
