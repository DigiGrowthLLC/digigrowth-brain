---
name: funnel-building
description: Given one existing DigiGrowth CLIENT's name, scrape their own website for brand/voice, build a single-page CRO-optimized landing page/funnel for their Meta ads to drive consultation bookings, show it for approval, then walk through deploying it live on Vercel and connecting the client's own domain. Use when Dylan says "build the funnel/landing page for <client>" or asks for an ad-traffic landing page for a specific client.
---

# Client Ad Funnel

Builds a real, live landing page for one of DigiGrowth's own CLIENTS to run Meta
ads traffic into — a single-purpose consultation-booking funnel, not a cold-
outreach mockup. **This is a different job from `landing-page-lead-magnet`**: that
skill impersonates a cold-outreach prospect's own site as a curiosity hook, then
pitches DigiGrowth underneath a "preview ends here" seam. This skill has no
prospect to impersonate and no second audience — the finished page is 100% the
client's own brand, talking to their own patients, driving one action: book a
consultation. Read both this file and `references/cro-funnel-principles.md` before
writing anything — they're a different rulebook from the cold-outreach page's.

**Always run this for one client at a time, in the foreground.** Never background
this skill — a prior incident in this codebase (leadgen-agent) saw a backgrounded
batch job die silently; that's a standing rule here too.

**Never treat the page as live without Dylan's explicit approval first.** Steps
1-5 always run; step 7 (deploy) only runs after he says yes to the preview in step 6.

## Steps

1. **Look up the client.**
   ```bash
   python design-agent/tools/lookup_client.py "<client name>"
   ```
   Gives you `client_id`, `website`, `calendly_url`, and every onboarding answer
   they've submitted (keyed by section — `ideal_patient`, `offer_economics`,
   `differentiation_voice`, etc.). Stop and tell Dylan if the client isn't found,
   has no website on file, or has no `calendly_url` set — the whole page's CTA
   depends on a real booking link existing; don't invent a placeholder one.
   **Read `differentiation_voice.avoid` carefully if present** — it's the
   client's own list of phrases/claims/tone to steer away from, a hard
   constraint on the copy you write, not a suggestion.

2. **Scrape the client's own site.**
   ```bash
   python design-agent/tools/scrape_prospect_site.py "<website>" "<scratch_dir>"
   ```
   Same tool the cold-outreach skill uses, reused here for the same reason: real
   extracted colors (`palette.json`), a real logo + a few real embedded photos
   (`assets.json`, already compressed — cap at 2-3 embedded images for page
   weight), and real page text (`page_text.txt`) — read it for anything usable
   as proof (real reviews, real specific service descriptions) beyond what the
   onboarding answers already gave you. This page is the client's OWN brand, not
   a mockup of it — use their real palette and real logo throughout, not an
   approximation, exactly like Section 1 of the cold-outreach page does.

3. **Read all reference files before writing anything, every run.**
   - `design-agent/references/cro-funnel-principles.md` — the actual rulebook
     for this skill: message-match, the fixed section order, CTA discipline,
     what never to include. This is the primary reference for this skill.
   - `design-agent/references/funnel-best-practices.md` — still relevant for the
     general conversion-copywriting principles (curiosity framing where it's
     honest, trust-signal specificity, mobile-first, form-friction) even though
     its PT-funnel-stage framing (Discovery -> Trust -> ...) and its
     cold-outreach-specific advice don't apply here.
   - `design-agent/references/example-client-funnel.html` — **this skill's own
     worked example, read this one closely.** A real, Dylan-approved client
     funnel (CrosaCore, shipped live) that went through several real rounds of
     feedback before landing here — reuse its structure and CSS wholesale as a
     starting point: the `:root` token system (swap every color for the new
     client's own scraped palette, never keep CrosaCore's forest/cream), the
     Google Fonts pairing approach (pick a real pairing suited to the new
     client's brand, never Georgia/system defaults), the 4-area hero CSS Grid
     (`rating`/`title`/`lead`/`cta` grid-template-areas, photo spanning
     alongside) that lets mobile reorder freely without touching desktop or
     the DOM, the review-wall masonry (`columns: 3 280px`, `break-inside:
     avoid`), the trust bar, and the floating frosted sticky mobile CTA — read
     its inline comments for two specific mistakes already made once, so they
     don't get made again (the sticky-CTA selector bug, and why the hero uses
     named grid areas instead of DOM reordering). **Never reuse this file's
     specific copy, testimonials, font choice, or color values for a
     different client** — re-derive all of that fresh from the new client's
     own scrape and onboarding answers per step 4.
   - `design-agent/references/example-landing-page.html` — the COLD-OUTREACH
     skill's worked example, still worth skimming for two things not covered
     above: the count-up-on-scroll technique and the documented image
     `aspect-ratio`/mobile `min-height` bug fixes. **Do not reuse its section
     structure, its seam, or any of its copy** — that page's whole shape
     (mockup + pitch + seam) is specific to the cold-outreach use case.

4. **Write the page.** One continuous page, the client's own brand throughout, no
   seam, no second audience. Follow `cro-funnel-principles.md`'s fixed section
   order exactly (hero -> trust bar -> problem -> offer -> proof -> FAQ -> final
   CTA), with every CTA button on the page pointing at the client's real
   `calendly_url` from step 1. Ground every specific claim in real data from
   steps 1-2 — the real offer from `offer_economics.specials` (or a plain "free
   consultation" if no special offer exists), real testimonials only if the
   scrape or `differentiation_voice.reviews` produced them (never invent a
   quote), the real pain point from `ideal_patient.best_patient` /
   `drop_off_reason`. No nav menu, no footer link list, no second CTA
   destination — see `cro-funnel-principles.md`'s "what not to do" section.
   Mobile-first, single HTML file, inline CSS, vanilla JS only (no frameworks) —
   same weight discipline as the cold-outreach page, more important here since
   real ad spend pays for every visitor who bounces on a slow load.

5. **Register the website and embed the tracking snippet, before saving the
   final HTML.**
   ```bash
   python design-agent/tools/register_client_website.py "<client_id>" "<label>" "<intended URL>"
   ```
   Use the URL you and Dylan intend to land on (e.g. `https://funnel.<clientdomain>.com`)
   even though it isn't live yet — the row just needs to exist so the tracking
   snippet has a real `WEBSITE_ID` to report against; nothing breaks if the
   final live URL ends up slightly different (Dylan can always fix the label/
   url later from the Websites tab in ClientsPanel). This also makes the site
   appear immediately in the client's own portal under their new Website tab,
   with stats starting at zero until real traffic arrives. Paste the printed
   `<script>` snippet into the page right before `</body>` — it fires a `view`
   beacon on load and a `conversion` beacon on any click of a link to
   `calendly.com` (matches this skill's rule that every CTA points at the
   client's real Calendly link, so no per-button wiring is needed). Save the
   complete HTML, snippet included, to `<scratch_dir>/index.html`.

6. **Show Dylan the page for approval.** Publish the generated HTML file as a
   Claude Artifact so he sees the actual rendered result, not a description of
   it. **Stop here and wait for his explicit yes.** If he asks for changes,
   revise and re-show — never proceed to deployment on a version he hasn't
   actually seen and approved.

7. **On approval, walk Dylan through going live.** This skill does not have API
   access to Vercel or to any client's domain registrar — deployment and DNS are
   Dylan's own actions, guided step by step:

   a. **Create a new Vercel project for this one page** — a dedicated project,
      never a route added onto the corporate `digigrowth-website` site. Point
      Dylan at [vercel.com/new](https://vercel.com/new): the fastest path for a
      single static file is dragging the `<scratch_dir>` folder (containing just
      `index.html`) onto the New Project import screen, or `vercel --prod` run
      from inside that folder if the Vercel CLI is already installed and logged
      in. Either way, this produces a live `*.vercel.app` URL immediately —
      confirm that URL loads and renders correctly before moving to DNS.

   b. **Decide subdomain vs. path, and set expectations correctly.** A DNS
      record can only ever point a **subdomain** (e.g. `funnel.clientdomain.com`
      or `go.clientdomain.com`) at the new Vercel project — it cannot make a
      **path** on the client's existing domain (`clientdomain.com/funnel`) serve
      a different host without whoever runs the client's main site adding a
      reverse-proxy/rewrite rule there, which is specific to that site's own
      host and outside what this skill (or a DNS record alone) can do. Default
      to recommending a subdomain unless Dylan confirms the client's site host
      genuinely supports a path rewrite to an external URL.

   c. **Add the domain in Vercel, then get the DNS record.** In the new Vercel
      project: Settings -> Domains -> Add `<chosen-subdomain>.<clientdomain>`.
      Vercel will display the exact record to add — for a subdomain this is
      always a **CNAME** record (Name = the subdomain label, e.g. `funnel` or
      `go`; Value = `cname.vercel-dns.com`, but read the literal value Vercel
      shows, it can vary). Tell Dylan exactly what Vercel displayed.

   d. **Add that record at the client's registrar** — not DigiGrowth's own
      Cloudflare/Google Workspace admin, the *client's* domain registrar (check
      this client's Registrar Platform link on their Resources tab in the OS if
      Dylan doesn't have it handy). This is the one step Dylan has to do outside
      any DigiGrowth-owned system, same reasoning as the email-marketing
      setup guide's DNS steps.

   e. **Confirm propagation.** DNS can take anywhere from a few minutes to a few
      hours. Vercel's own Domains settings page shows a live "Valid
      Configuration" check once it resolves — have Dylan refresh that page
      rather than guessing from `dig`/browser caching, which can lag behind the
      real DNS state.

   f. **Paste the final live URL into the OS.** Once confirmed live, Dylan sets
      it via the Marketing Setup tab's Landing Page step (SET URL button) —
      `client_marketing_config.landing_page_url` — so the OS's own tracking
      (`done` state, the client's Dashboard/Analytics) picks it up. This skill
      doesn't call that API directly; it's a one-click manual step once the URL
      is confirmed live.

8. Save a short completion note to
   `design-agent/outputs/funnel-<client-slug>-YYYY-MM-DD.md` (today's full
   4-digit year) and end with the completion message.

## What This Skill Does NOT Do

- Doesn't impersonate the client's site as a mockup for someone else, and
  doesn't carry a DigiGrowth pitch underneath a seam — the whole page is the
  client's own brand, full stop.
- Doesn't fabricate a testimonial, a discount/offer, a statistic, or an urgency
  claim the client didn't actually give in onboarding or their own site.
- Doesn't auto-deploy anything — the approval gate in step 6 is not optional,
  and step 7's Vercel/DNS work is Dylan's own hands-on action, not something
  this skill executes for him.
- Doesn't pull real analytics from Vercel — the account is on the Hobby plan,
  where Vercel's own Web Analytics data API is Pro-only. Step 5's tracking
  snippet reports into DigiGrowth's own database instead (same pipeline the
  VSL/outreach-video funnels use), which is what actually powers the
  view/conversion numbers shown in the client's portal Website tab.
- Doesn't touch `client_marketing_config` directly — pasting the final URL into
  the dashboard is a manual last step, same as the existing (pre-automation)
  Landing Page guide already describes.
- Doesn't batch multiple clients in one run — one at a time, by name, every time.

## Completion Message

```
Client Ad Funnel complete — <client name> — YYYY-MM-DD
Preview approved: yes
Deployed: <vercel.app URL, or "pending Dylan's Vercel deploy" if step 7 hasn't happened yet>
Custom domain: <subdomain.clientdomain.com, or "not yet connected">
```

If Dylan didn't approve the preview (revised and re-shown, or declined entirely):
```
Client Ad Funnel — <client name> — not deployed
Reason: [awaiting revision / declined / other]
```
