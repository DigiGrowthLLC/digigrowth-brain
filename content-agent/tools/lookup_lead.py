import sys
import subprocess
import requests
from urllib.parse import quote


def doppler_secret(name):
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--project", "digigrowth", "--config", "prd", "--plain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    name = " ".join(sys.argv[1:]).strip()
    if not name:
        print("Usage: python lookup_lead.py <business name>")
        sys.exit(1)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")

    resp = requests.get(
        f"{dashboard_url}/api/contacts",
        params={"search": name, "limit": 1},
        auth=("admin", password),
        timeout=15,
    )
    resp.raise_for_status()
    rows = resp.json()
    if isinstance(rows, dict):
        rows = rows.get("contacts") or rows.get("results") or rows.get("data") or []

    if not rows:
        print(f"NOT FOUND: no contact matching '{name}'")
        sys.exit(2)

    contact = rows[0]
    website = contact.get("website")

    print(f"FOUND: {contact.get('business')}")
    print(f"PHONE: {contact.get('phone')}")
    if not website:
        print("WEBSITE: none on file")
        sys.exit(3)

    print(f"WEBSITE: {website}")


if __name__ == "__main__":
    main()
