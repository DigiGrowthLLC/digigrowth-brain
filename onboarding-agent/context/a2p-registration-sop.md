# A2P 10DLC Registration SOP (Twilio Brand + Campaign)

How to register a client's texting so it is approved the first time. Every client with a
texting service needs it (Setup step `a2p`). Without an approved campaign, texts from
their number get filtered or blocked, including the AI agent's opener.

Written after Pinnacle Physical Therapy's campaign was rejected on 2026-11-16 (error 30909:
"There is no proof provided for fb/insta lead form opt in"). That cost about a week
plus a fresh 2-3 week review.

## The rule that matters most

**Build every opt-in path, with its consent line live, BEFORE you submit the campaign.**
Carriers check the proof you give them. A description of a form that doesn't exist yet,
or one they can't open, gets rejected. Order for every client:

1. Brand (as soon as you have the legal name + EIN: it doesn't depend on anything else)
2. Instant Form with the consent disclaimer (Setup step `lead_form`), and the funnel +
   booking page with their consent checkbox
3. Screenshot of each opt-in, hosted at a public link
4. Then the Campaign

## 1. Brand

- Twilio Console, **in the client's subaccount** (top-left switcher: "DigiGrowth Client –
  <name>"), Messaging → Regulatory Compliance → Brands.
- Legal business name and EIN exactly as on the IRS letter (CP 575 / 147C), same address.
  A mismatch is the main brand rejection.
- Low Volume Standard is enough for one clinic (Pinnacle: approved in 4 days, 11/6 to 11/10).

## 2. Opt-in proof (before the campaign)

**Meta Instant Form** (paid-ads clients):
- Dashboard → client → Setup → `lead_form` → CREATE FORM builds it with the consent
  disclaimer. If that fails (server token can't reach the Page: "pages_read_engagement"
  error), build it by hand in Business Suite → Lead ads forms:
  Privacy policy section → **Add custom disclaimer**, title "Contact consent", text:
  > By submitting, you agree to be contacted by <Practice> by phone, including automated
  > calls, and by text, about your request. Consent isn't required to receive care. Msg &
  > data rates may apply. Reply STOP to opt out.
- **Published forms can't be edited.** If an older form lacks the disclaimer, Duplicate it,
  add the disclaimer, publish, and point the ads at the new form ID (record it in the
  client's campaign-plan.md). The old form is NOT valid proof.
- Lead Ads terms: the Meta Ads MCP field `leadgen_tos_accepted` has reported `false` for a
  Page that had accepted. If the Page's Forms Library already holds working forms, the
  terms are accepted. Don't treat the MCP flag as a blocker.

**Funnel / booking page**: the page's consent checkbox wording is the proof. Use its
public URL directly.

**Screenshot hosting**: crop the form preview so the disclaimer and Submit button are
visible (no browser chrome). Upload to Drive, share "Anyone with the link → Viewer",
then check it opens in a logged-out browser (`curl -L` returns 200 on the /view URL).

## 3. Campaign

- Use case: **Low Volume Mixed** (covers marketing, so reactivation and follow-up texts
  aren't filtered; customer-care only is not enough).
- **"How do end-users consent to receive messages?"** must name EVERY opt-in path, quote
  each consent line word for word, and give a public proof link for each. Template:
  > End users opt in through a Facebook/Instagram Instant Form (lead ad) run by <Practice>
  > for <offer>. The user enters their full name, phone number and email and verifies their
  > phone number by SMS code. Directly above the Submit button the form displays this
  > disclosure: "<exact consent text>". Only users who submit the form are texted.
  > Screenshot of the live form: <public link>.
  > End users can also opt in on <Practice>'s booking page (<URL>) by checking the box
  > "<exact checkbox text>" before booking.
- **Message contents boxes must match the samples.** If any sample has a link (e.g. a
  booking link), tick "Messages will include embedded links". If any has a phone number,
  tick "Messages will include phone numbers". Pinnacle's resubmission went in with the
  links box unticked while sample 3 had a booking link, which is a common rejection reason.
- Samples: the practice name in each one, opt-out wording ("Reply STOP to opt out") in the
  first, placeholders in brackets ([First Name], [booking link]), and they should read like
  the real texts the agent and sequences send.
- Privacy policy + terms URLs: public pages that say mobile numbers and opt-in data are
  never shared with third parties for marketing.

## 4. After submitting

- **The rejection email is the source of truth, not the console.** Twilio's console showed
  Pinnacle's rejected campaign as "In progress" a day after the rejection email. Check
  Gmail (dylanrg@): `from:a2p10dlc@twilio.com <campaign SID>`. The email gives the error
  code and the reviewer's note.
- A rejected campaign is edited and resubmitted in place: open the campaign → Edit
  Campaign → fix → Update. While it's under review every field is locked.
- Review takes 2-3 weeks per submission, so a rejection costs weeks. Getting it right the
  first time matters more than submitting early with gaps.
- Approved = campaign status Verified. Then send a real test text to the client's number,
  check the agent replies, and tick `a2p`.

## Access notes

- Twilio keys are not in Doppler, and the dashboard has no A2P route. The console in Chrome
  is the only path, and Dylan has to be logged in (never type his password).
- The console's new "senders onboarding / checklist" page can crash ("Cannot read
  properties of undefined (reading 'status')"). Use the classic Campaigns list instead:
  console.twilio.com/us1/develop/sms/regulatory-compliance/campaigns
