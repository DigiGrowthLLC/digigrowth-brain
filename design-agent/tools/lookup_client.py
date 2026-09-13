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
    name = " ".join(sys.argv[1:]).strip()
    if not name:
        print("Usage: python lookup_client.py <client name>")
        sys.exit(1)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")
    auth = ("admin", password)

    # clients.py's list endpoint has no search param — fetch all and match
    # client-side. The client list is small (agency-scale, not thousands of
    # rows), so this is fine.
    resp = requests.get(f"{dashboard_url}/api/clients", auth=auth, timeout=15)
    resp.raise_for_status()
    clients = resp.json()

    match = next((c for c in clients if c.get("name", "").strip().lower() == name.lower()), None)
    if not match:
        match = next((c for c in clients if name.lower() in c.get("name", "").strip().lower()), None)
    if not match:
        print(f"NOT FOUND: no client matching '{name}'")
        print("Known clients: " + ", ".join(c.get("name", "?") for c in clients))
        sys.exit(2)

    client_id = match["id"]
    detail_resp = requests.get(f"{dashboard_url}/api/clients/{client_id}", auth=auth, timeout=15)
    detail_resp.raise_for_status()
    detail = detail_resp.json()

    # The client's own real website lives on their anchor contact
    # (contacts.website), not on the clients row itself — same contact
    # record lookup_prospect.py already resolves via /api/contacts search,
    # reused here since the anchor contact's business name matches the
    # client's name.
    website = None
    contacts_resp = requests.get(
        f"{dashboard_url}/api/contacts", params={"search": match["name"], "limit": 5}, auth=auth, timeout=15,
    )
    if contacts_resp.ok:
        rows = contacts_resp.json()
        if isinstance(rows, dict):
            rows = rows.get("contacts") or rows.get("results") or rows.get("data") or []
        for c in rows:
            if c.get("website"):
                website = c["website"]
                break

    print(f"CLIENT_ID: {client_id}")
    print(f"NAME: {match['name']}")
    print(f"WEBSITE: {website or 'none on file'}")
    print(f"CALENDLY_URL: {detail.get('calendly_url') or 'none set'}")
    print()
    print("ONBOARDING ANSWERS:")
    onboarding = detail.get("onboarding") or {}
    if not onboarding:
        print("  (none submitted yet)")
    for section, row in onboarding.items():
        answers = row.get("answers") or {}
        if not answers:
            continue
        print(f"  [{section}]")
        for k, v in answers.items():
            if v:
                print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
