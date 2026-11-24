# Marketing Audit: Data-Backed Changes (2026-11-23, revised)

Full version with evidence and before/after copy: https://claude.ai/artifact/DJDoN1YjvZsaeSQTu2GTgn
ICP research it builds on: `context/icp-pain-points.md`. Every item cites OS data, counted
prospect replies/call quotes, or a fact check. Drafts need Dylan's approval.

## Measured funnel (cold SMS, all threads since Aug 2026)
3,762 sent → 1,347 replied → 746 owners → 150 responded to pitch → 51 wanted a call → 20 booked.

| Version | Owners | Responded to pitch | Wanted a call | Booked | Wanted → booked |
|---|---|---|---|---|---|
| V.1.2 | 64 | 17% | 4 | 2 | 2/4 |
| V.1.3 ("mind if I send a video?") | 45 | 7% | 1 | 0 | 0/1 |
| V.1.4 | 283 | 22% | 20 | 12 | 60% |
| V.1.5 (live) | 353 | 21% | 26 | 6 | 23% |

Follow-ups: T1 "checking you got that last message" 18% reply (621 sent), T2 "two more slots"
8% (321), T3 "last one from me" 4% (532). Discovery calls (real practices): 48 booked, 18 canceled
(38%), at least 7 of those canceled by Dylan; 28 showed, 4 closed.

## Changes, ranked by measured impact
1. **Book the time the owner names.** 13 of 26 V.1.5 owners who wanted a call proposed their own
   day/time and got two different times back, then automated nudges (Move Again, Advance Care,
   Thrive, Flow, Carolina Movement Doc, Mattera never booked).
2. **Stop automated texts firing into live conversations and canceled calls.** 6 "ignore that
   automatic message" apologies; reminders after cancellation (Healix, Core PT, Rise & Reframe);
   Dr. Zachary Kaplan showed up, got a no-show text and ~100 emails, and passed; Kinwell got a
   reminder every 10 minutes.
3. **Protect booked discovery calls from Dylan's side.** At least 7 of the 18 cancellations were
   Dylan's texts.
4. **VSL/Loom: cut "You pay us nothing to find out, nothing after, whether it works or not."** It
   contradicts offer.md ($1,000/month practice-funded budget). Use the setter's structure answer.
5. ~~Loom: record an email ending.~~ Corrected 2026-11-23: the Terminator Loom is a separate
   recording (Loom V.1.1 script) and already ends "just shoot me a quick reply". No change needed.
6. **VSL pain section: replace the physician-retirement pain** with P1-P4 in buyers' words. Only
   Pinnacle of the 4 buyers relies on physicians.
7. **Setter: say "paid" when owners ask what they get** ("local people... pay for their first visit
   before it's on your calendar"). 59 info-request threads, incl. "Not sure what you are promising".
8. **Setter: ask "full" owners if they're hiring.** 62 "full" replies; a hire drove 3 of 4 buys.
9. **Website: show real practices instead of generic AI stats;** line up a client reference.
   2 of 4 buyers asked for references before signing.
10. **Remove AI from the website log, the no-show text and the Loom script.** Prospect/client
   quotes against bots; positioning.md bans it.
11. **Fix live bugs:** emoji in "Sent over some info" (fixed 2026-11-23); "AI Growth Engine" in the
   no-show text (fixed 2026-11-23). `{{company}}` was not a bug: email_handoff_sequence.py resolves
   double braces.
12. **Test (not yet proven):** pain-led T2 follow-up vs. the live 8% T2.

## Keep
Asking for a call (V.1.3's video ask did 7% vs 21-22%); the T1 nudge; the setter's cost-structure
answer; website hero, "You're a PT, Not a Marketing Director", "tried other marketing" FAQ.

## Cut from the first version (no supporting data)
Dropping "not a bot"/"free" (no comparison exists); three new openers (wording change V.1.4→V.1.5
didn't move response); replacing T1; cold email copy rewrite (blocked on deliverability); 24h
reminder rewrite; 45-60 s Loom cut and segment intros; website photo/"text me".

## Data gaps
Who cancels isn't recorded; website booking analytics only started 2026-11-22; 4 closes is too
few to split by source; email copy blocked on deliverability.
