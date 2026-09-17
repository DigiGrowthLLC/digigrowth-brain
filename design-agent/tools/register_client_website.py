import sys
import subprocess
import requests


def doppler_secret(name):
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--project", "digigrowth", "--config", "prd", "--plain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    if len(sys.argv) < 4:
        print("Usage: python register_client_website.py <client_id> <label> <url>")
        sys.exit(1)

    client_id, label, url = sys.argv[1], sys.argv[2], sys.argv[3]

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")

    resp = requests.post(
        f"{dashboard_url}/api/clients/{client_id}/websites",
        json={"label": label, "url": url},
        auth=("admin", password),
        timeout=15,
    )
    resp.raise_for_status()
    row = resp.json()

    print(f"WEBSITE_ID: {row['id']}")
    print(f"LABEL: {row['label']}")
    print(f"URL: {row['url']}")
    print()
    print("Embed this before </body> in the generated page (uses this exact")
    print("WEBSITE_ID) — see funnel-building SKILL.md step 4b:")
    print(f"""
<script>
(function(){{
  var WEBSITE_ID = "{row['id']}";

  // Genuine Meta (Facebook/Instagram) origin, detected client-side — a
  // paid-ad click carries fbclid automatically; organic Meta traffic
  // (bio link, shared post) won't have fbclid but does carry a matching
  // document.referrer. Used for the "viewers/booked from Meta" stats on
  // this client's portal Website tab, NOT just "assume all traffic is ads."
  function fromMeta(){{
    try {{
      if (new URLSearchParams(window.location.search).has("fbclid")) return true;
      var ref = (document.referrer || "").toLowerCase();
      return ["facebook.com","fb.com","instagram.com","l.facebook.com","lm.facebook.com","m.facebook.com"]
        .some(function(d){{ return ref.indexOf(d) !== -1; }});
    }} catch(e) {{ return false; }}
  }}
  var FROM_META = fromMeta();

  function send(type){{
    try {{
      navigator.sendBeacon(
        "{dashboard_url}/track/view-event",
        new Blob([JSON.stringify({{source:"client_website", event_type:type, content_key:WEBSITE_ID, from_meta:FROM_META}})], {{type:"application/json"}})
      );
    }} catch(e) {{}}
  }}
  send("view");
  // "conversion" (Booked Consultations) is recorded server-side only when
  // a Calendly booking is actually confirmed (routers/calendly_webhooks.py) —
  // no click-based send() here, a click isn't a real booked consultation.

  // Thread the Meta-origin signal through to that eventual booking: Calendly
  // echoes utm_content back in its invitee.created webhook payload's
  // `tracking` object (routers/calendly_webhooks.py reads it there) — that's
  // the only way to attribute a REAL confirmed booking to Meta, since the
  // booking itself completes on Calendly's own domain, not this page.
  if (FROM_META) {{
    document.querySelectorAll('a[href*="calendly.com"]').forEach(function(el){{
      try {{
        var url = new URL(el.href);
        url.searchParams.set("utm_content", "meta");
        el.href = url.toString();
      }} catch(e) {{}}
    }});
  }}
}})();
</script>
""")


if __name__ == "__main__":
    main()
