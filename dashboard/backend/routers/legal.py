"""
Public legal pages — no auth required.
Served at /privacy and /terms for Twilio campaign registration.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_STYLE = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 760px; margin: 48px auto; padding: 0 24px;
         color: #1a1a2e; line-height: 1.7; }
  h1   { font-size: 1.8rem; margin-bottom: 4px; }
  h2   { font-size: 1.1rem; margin-top: 32px; color: #3a7bd5; }
  p, li { font-size: 0.97rem; }
  .updated { color: #888; font-size: 0.85rem; margin-bottom: 32px; }
  a    { color: #3a7bd5; }
"""


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Privacy Policy — DigiGrowth LLC</title>
<style>{_STYLE}</style></head>
<body>
<h1>Privacy Policy</h1>
<p class="updated">Last updated: November 25, 2026</p>

<h2>1. Who We Are</h2>
<p>DigiGrowth LLC ("DigiGrowth", "we", "our") provides digital marketing and client acquisition
services. Questions? Email us at <a href="mailto:dylangroenendijk@gmail.com">dylangroenendijk@gmail.com</a>.</p>

<h2>2. Information We Collect</h2>
<p>We collect business contact information (name, phone number, email, business name) that you
or your team provide, or that is sourced from publicly available business directories.</p>

<h2>3. How We Use Your Information</h2>
<p>We use your contact information to reach out about our digital marketing services, schedule
consultations, and follow up on inquiries. We may contact you via phone call or SMS text message.</p>

<h2>4. SMS / Text Messaging</h2>
<p><strong>Message frequency:</strong> You may receive up to <strong>5 SMS messages per month</strong>
from DigiGrowth regarding our services, follow-up communications, and appointment reminders.</p>
<p><strong>Message and data rates may apply.</strong> Standard carrier message and data rates apply
to all SMS messages sent and received.</p>
<p><strong>Opt-out:</strong> Reply <strong>STOP</strong> at any time to unsubscribe from SMS
messages. After opting out you will receive one confirmation message and no further texts.</p>
<p><strong>Help:</strong> Reply <strong>HELP</strong> for assistance or contact us at
<a href="mailto:dylangroenendijk@gmail.com">dylangroenendijk@gmail.com</a>.</p>

<h2>5. Non-Sharing of Mobile Numbers</h2>
<p><strong>We do not sell, rent, share, or trade mobile phone numbers or any personally
identifiable information with third parties for their marketing purposes.</strong> Mobile phone
numbers collected by DigiGrowth are used solely for direct communications between DigiGrowth
and the contact, and will never be disclosed to external parties except as required by law.</p>

<h2>6. Facebook and Instagram Data</h2>
<p>We manage Facebook Pages and Instagram business accounts on behalf of the healthcare clinics we
work with (our "clinic clients"), using the Meta Platform under each clinic's authorization. When
someone messages a clinic client's Facebook Page or Instagram account, or submits one of its Facebook
or Instagram lead forms, we receive:</p>
<ul>
  <li>the message content, its timestamp and the Meta-provided ID of the conversation;</li>
  <li>the sender's public name as provided by Meta;</li>
  <li>any details the person chooses to share, such as their phone number or email, and lead form answers.</li>
</ul>
<p><strong>How we use it:</strong> only to reply to that person on the clinic's behalf (including with
an AI assistant that answers questions and helps book an appointment with the clinic), to follow up
with them by text if they gave a phone number, and to show the clinic its conversations and leads.
<strong>We do not sell this data, use it for advertising or profiling, or share it with anyone other
than the clinic the person contacted</strong>, apart from the service providers that run our systems
(hosting, AI processing and messaging), who may use it only to provide those services to us.</p>
<p><strong>Retention:</strong> kept while we provide services to that clinic, and deleted within 30 days
after the clinic stops working with us or a deletion request is received.</p>
<p><strong>Deletion:</strong> anyone can ask us to delete their Facebook or Instagram data. See our
<a href="/data-deletion">Data Deletion Instructions</a>.</p>

<h2>7. Data Retention</h2>
<p>We retain contact information for as long as necessary to provide our services or as required
by law. You may request deletion of your data at any time by emailing us.</p>

<h2>8. Your Rights</h2>
<p>You may request access to, correction of, or deletion of your personal information by
contacting us at <a href="mailto:dylanrg@digigrowthllc.com">dylanrg@digigrowthllc.com</a>.</p>

<h2>9. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. The "last updated" date at the top of
this page reflects the most recent revision.</p>
</body></html>""")


@router.get("/data-deletion", response_class=HTMLResponse, include_in_schema=False)
async def data_deletion():
    """Meta App Review's required User Data Deletion instructions URL."""
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Deletion Instructions — DigiGrowth LLC</title>
<style>{_STYLE}</style></head>
<body>
<h1>Data Deletion Instructions</h1>
<p class="updated">Last updated: November 25, 2026</p>

<p>DigiGrowth LLC answers Facebook and Instagram messages and lead forms on behalf of the healthcare
clinics we work with. If you messaged one of those clinics, or filled out one of their forms, you
can ask us to delete everything we hold about you.</p>

<h2>How to request deletion</h2>
<ol>
  <li>Email <a href="mailto:dylanrg@digigrowthllc.com?subject=Data%20deletion%20request">dylanrg@digigrowthllc.com</a>
      with the subject "Data deletion request".</li>
  <li>Tell us the name of the clinic you contacted and your Facebook or Instagram name (and the phone
      number or email you shared, if any), so we can find your records.</li>
</ol>

<h2>What we delete</h2>
<ul>
  <li>your messages and conversation history with the clinic's Facebook Page or Instagram account;</li>
  <li>your name, Meta conversation ID, phone number, email and any lead form answers;</li>
  <li>any scheduled follow-up messages to you.</li>
</ul>
<p>We confirm by email once it's done, within 30 days of your request.
Appointments you already booked stay with the clinic, since they are the clinic's own records.</p>

<p>See our <a href="/privacy">Privacy Policy</a> for how this data is used.</p>
</body></html>""")


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_and_conditions():
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Terms &amp; Conditions — DigiGrowth LLC</title>
<style>{_STYLE}</style></head>
<body>
<h1>Terms &amp; Conditions</h1>
<p class="updated">Last updated: June 25, 2026</p>

<h2>1. Acceptance of Terms</h2>
<p>By engaging with DigiGrowth LLC ("DigiGrowth") or providing your contact information, you
agree to these Terms and Conditions. If you do not agree, please do not provide your contact
information or engage with our services.</p>

<h2>2. Services</h2>
<p>DigiGrowth provides digital marketing consultation and client acquisition services to
small and medium-sized businesses. Services are provided on a per-engagement basis as agreed
between DigiGrowth and each client.</p>

<h2>3. SMS Communications</h2>
<p>By providing your mobile phone number to DigiGrowth, you consent to receive SMS text
messages from DigiGrowth regarding our services, follow-ups, and appointment scheduling.</p>
<ul>
  <li><strong>Message frequency:</strong> Up to 5 messages per month.</li>
  <li><strong>Message and data rates may apply.</strong></li>
  <li>Reply <strong>STOP</strong> at any time to opt out of SMS messages.</li>
  <li>Reply <strong>HELP</strong> for assistance.</li>
</ul>

<h2>4. No Guarantee of Results</h2>
<p>DigiGrowth does not guarantee specific business outcomes, revenue increases, or lead
generation results. All estimates and projections are illustrative only.</p>

<h2>5. Limitation of Liability</h2>
<p>To the maximum extent permitted by law, DigiGrowth shall not be liable for any indirect,
incidental, or consequential damages arising from use of our services or communications.</p>

<h2>6. Privacy</h2>
<p>Your use of our services is also governed by our
<a href="/privacy">Privacy Policy</a>, which is incorporated into these Terms by reference.</p>

<h2>7. Governing Law</h2>
<p>These Terms shall be governed by the laws of the State of Florida, without regard to its
conflict of law provisions.</p>

<h2>8. Contact</h2>
<p>Questions about these Terms? Email us at
<a href="mailto:dylangroenendijk@gmail.com">dylangroenendijk@gmail.com</a>.</p>
</body></html>""")


@router.get("/privacy/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def clinic_privacy_policy(slug: str):
    """A client clinic's own privacy policy, for its Meta Instant Form
    (setup_automation.create_instant_form) and funnel. Keyed by the funnel
    slug; names the clinic and its patient contact phone/email."""
    import html as _html
    from fastapi import HTTPException
    from db import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT cl.name, cl.email, cl.phone, bs.contact_email, bs.contact_phone
               FROM landing_pages lp JOIN clients cl ON cl.id = lp.client_id
               LEFT JOIN booking_settings bs ON bs.client_id = cl.id WHERE lp.slug = $1""", slug)
    if not row:
        raise HTTPException(404, "Not found")
    name = _html.escape(row["name"])
    email = _html.escape(row["contact_email"] or row["email"] or "")
    phone = _html.escape(row["contact_phone"] or row["phone"] or "")
    contact = " or ".join(x for x in [f'<a href="mailto:{email}">{email}</a>' if email else "", phone] if x) or "the clinic"
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy | {name}</title><style>{_STYLE}</style></head><body>
<h1>Privacy Policy</h1>
<p class="updated">{name}</p>
<h2>What we collect</h2>
<p>When you request an appointment or information through our forms, ads or booking page, we collect your name,
mobile number, email address and anything you choose to tell us about why you're reaching out.</p>
<h2>How we use it</h2>
<p>We use it to contact you about your request: to schedule, confirm and remind you about appointments, and to
follow up by phone (which may include automated or AI-assisted calls) and by text, as you agreed when you
submitted the form. Message and data rates may apply. Reply STOP to any text to opt out, or tell us on a call.</p>
<h2>Who we share it with</h2>
<p>We don't sell your information. We share it only with service providers that help us run scheduling,
texting, calling and payments on our behalf, under confidentiality obligations, or when the law requires it.
Text messaging opt-in data and consent are never shared with third parties for their marketing.</p>
<h2>Retention and your rights</h2>
<p>We keep your information as long as needed for your request and our records, or as the law requires. You can ask
us to access, correct or delete it at any time: contact {contact}.</p>
</body></html>""")
