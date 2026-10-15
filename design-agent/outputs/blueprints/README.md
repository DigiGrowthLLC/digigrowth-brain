# Patient Acquisition Blueprints

One folder per prospect. The live page is what you open on the sales call; the folder is the source, so the page can be edited and republished later.

| Prospect | Practice | Package | Live blueprint |
|---|---|---|---|
| Brian Murphy | Pinnacle Physical Therapy, Little Rock AR | Main offer (ads + guarantee) | https://pages.digigrowthllc.com/lp/pinnacle-physical-therapy-blueprint |
| Samantha Newell | Exceptional Solutions PT, Grand Rapids MI | Foundations ($500/mo, no ads, no guarantee) | https://pages.digigrowthllc.com/lp/exceptional-solutions-pt-blueprint |

Neither link has been sent to the prospect yet.

---

## Brian Murphy · Pinnacle Physical Therapy

`pinnacle-physical-therapy-blueprint/` · full notes: [../blueprint-pinnacle-physical-therapy-blueprint-2026-10-08.md](../blueprint-pinnacle-physical-therapy-blueprint-2026-10-08.md)

**On the page:** engine diagram · 3 ads cut from his own YouTube videos (Ned Perme testimonial, "I've been to PT before", TMJ) · 3 AI UGC ads (tried everything, back by Thursday, back to square one) · $49 Discovery Visit funnel in laptop + phone · live AI text agent · reactivation · nothing leaks · the guarantee.

**Worth knowing for the call**
- He already sells a $49 Discovery Visit, so the offer fits his practice as-is.
- His site never says whether he takes insurance; the chat says the team will confirm. Ask him.
- Ned Perme is a public figure: fine for the preview, get his consent before his video runs as a paid ad.
- The live chat is a demo: booking is simulated, nothing hits a calendar.

---

## Samantha Newell · Exceptional Solutions PT

`exceptional-solutions-pt-blueprint/` · full notes: [../blueprint-exceptional-solutions-pt-blueprint-2026-10-08.md](../blueprint-exceptional-solutions-pt-blueprint-2026-10-08.md)

**On the page:** engine diagram · 10-page SEO website (click through it in the preview) · live AI text agent (books a free Google Meet consult) · reactivation · nothing leaks · the math (7.5 hrs back, ~$1,980/mo, 1/3 fewer no-shows, 4x, each with how it's estimated) · what's included + $500/month.

**Worth knowing for the call**
- She's the only employee; that's the pitch (the agent replies while she's treating).
- The math rests on assumptions (30 inquiries/month, 15 min each, 2 extra patients, her $910 package). Ask her real inquiry volume and adjust on the spot if it's different.
- Open items: are appointment reminders part of Foundations? Foundations isn't written into `context/offer.md` yet.

---

## Editing and republishing a blueprint

From the repo root (Doppler supplies the keys):

```bash
python design-agent/tools/build_blueprint.py design-agent/outputs/blueprints/<slug>/blueprint.json <out_dir>
doppler run --project digigrowth --config prd -- python design-agent/tools/publish_landing_page.py "<slug>" "<out_dir>/page.html" "<Business>" "<contact_id>" --chat-context "<out_dir>/chat_context.txt"
```

Contact ids: Pinnacle `2f90a865-e412-4508-8fdb-b9a922af97c8`, Exceptional Solutions `68881152-2562-4587-94e9-c04f909c1984`.

Republishing without `--assets` keeps the videos already in R2. **Pinnacle's ad videos aren't in this folder** (about 20 MB). To rebuild Pinnacle locally, download them back from the live page first: `/lp/pinnacle-physical-therapy-blueprint/a/video1.mp4` … `video6.mp4` are, in order, `social/cut1.mp4`, `social/cut2.mp4`, `social/cut3.mp4`, `libads/pinnacle-ugc-tried-everything-web.mp4`, `libads/pinnacle-ugc-thursday-web.mp4`, `libads/pinnacle-ugc-squareone-web.mp4` (the paths `blueprint.json` expects).

`built/page.html` in each folder is the exact page that's live, kept as a backup.
