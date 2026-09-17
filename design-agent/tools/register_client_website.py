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
  function send(type){{
    try {{
      navigator.sendBeacon(
        "{dashboard_url}/track/view-event",
        new Blob([JSON.stringify({{source:"client_website", event_type:type, content_key:WEBSITE_ID}})], {{type:"application/json"}})
      );
    }} catch(e) {{}}
  }}
  send("view");
  // "conversion" (Consultation Requests) is recorded server-side only when
  // a Calendly booking is actually confirmed (routers/calendly_webhooks.py) —
  // no click-based send() here, a click isn't a real consultation request.
}})();
</script>
""")


if __name__ == "__main__":
    main()
