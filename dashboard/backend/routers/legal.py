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
<p class="updated">Last updated: June 25, 2026</p>

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

<h2>6. Data Retention</h2>
<p>We retain contact information for as long as necessary to provide our services or as required
by law. You may request deletion of your data at any time by emailing us.</p>

<h2>7. Your Rights</h2>
<p>You may request access to, correction of, or deletion of your personal information by
contacting us at <a href="mailto:dylangroenendijk@gmail.com">dylangroenendijk@gmail.com</a>.</p>

<h2>8. Changes to This Policy</h2>
<p>We may update this Privacy Policy from time to time. The "last updated" date at the top of
this page reflects the most recent revision.</p>
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
