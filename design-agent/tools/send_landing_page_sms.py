"""
Sends the short, locked "here's the link" message for a published landing
page, then marks the page as sent. Same bypass pattern as
content-agent/tools/send_outreach_sms.py's Loom send: a hardcoded template,
not read from the sms_sequences table, so a sequence edit can never silently
break this flow.

For prospects run through the landing-page-mockup skill, this message
REPLACES the sequence's long curiosity_opener pitch — it isn't appended to
it (see design-agent's landing-page-mockup SKILL.md for why: the campaign
report found that long pitch causing most of the funnel's drop-off).

Usage: python send_landing_page_sms.py <phone> <name> <business> <url> <slug>
"""
import sys
import subprocess
import requests

_SEQUENCE_STAGE = "relevance"  # "2. Primed Message" — see SEQUENCE_STEPS in dashboard/backend/routers/sms.py


def doppler_secret(name):
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--project", "digigrowth", "--config", "prd", "--plain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    if len(sys.argv) < 6:
        print("Usage: python send_landing_page_sms.py <phone> <name> <business> <url> <slug>")
        sys.exit(1)

    phone, name, business, url, slug = sys.argv[1:6]

    # Safety check — never fire off a link that doesn't actually resolve.
    # Real risk while the branded subdomain's DNS/SSL cert is still
    # propagating (see the "Setup note" in landing-page-mockup's SKILL.md).
    try:
        check = requests.head(url, timeout=10, allow_redirects=True)
        if check.status_code >= 400:
            print(f"REFUSING TO SEND: {url} returned HTTP {check.status_code}. "
                  f"Check `railway domain status pages.digigrowthllc.com` before retrying.")
            sys.exit(5)
    except requests.RequestException as e:
        print(f"REFUSING TO SEND: {url} is unreachable ({e}). "
              f"Check `railway domain status pages.digigrowthllc.com` before retrying.")
        sys.exit(5)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")
    auth = ("admin", password)

    # Plain hyphen, not an em dash — GSM-7 only (an em dash forces UCS-2
    # encoding, which cuts the segment size roughly in half and doubles
    # Twilio cost; see the SMS GSM-7 encoding rule this codebase follows
    # elsewhere for cold outreach).
    # Says "pilot program" deliberately — the landing page's Section 2
    # ("what this is") refers back to that exact phrase, so the two need
    # to match; see design-agent's landing-page-mockup SKILL.md.
    body = f"Hey {name} - mocked up what the pilot program could look like for {business}: {url}"

    resp = requests.post(
        f"{dashboard_url}/api/sms/send",
        json={"phone": phone, "body": body, "stage": _SEQUENCE_STAGE},
        auth=auth,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        print(f"SEND FAILED: {result.get('error')}")
        sys.exit(4)

    sent_resp = requests.post(f"{dashboard_url}/api/landing-pages/{slug}/sent", auth=auth, timeout=30)
    sent_resp.raise_for_status()

    print(f"SENT to {phone}")
    print(f"BODY: {body}")


if __name__ == "__main__":
    main()
