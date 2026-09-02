import re
import sys
import subprocess
import requests

# Windows terminals default to cp1252, which can't encode the emoji some
# sequence templates contain (e.g. the primed-message "shoot me a thumbs up"
# line) — reconfigure stdout so a print() doesn't crash after the send
# already succeeded.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# The active sequence's "2. Primed Message" step (SEQUENCE_STEPS key "relevance"
# in dashboard/backend/routers/sms.py) is where the Loom/watch link goes —
# e.g. "[Loom link] Shoot me a \U0001F44D once you've watched it". This matches
# any bracket/paren spelling of that placeholder so template edits don't break it.
_LINK_PLACEHOLDER = re.compile(r"[\[\(]\s*loom\s*link\s*[\]\)]", re.IGNORECASE)
_SEQUENCE_STAGE = "relevance"  # "2. Primed Message"


def doppler_secret(name):
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--project", "digigrowth", "--config", "prd", "--plain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    if len(sys.argv) < 3:
        print("Usage: python send_outreach_sms.py <phone> <watch_url>")
        sys.exit(1)

    phone = sys.argv[1]
    watch_url = sys.argv[2]

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")
    auth = ("admin", password)

    sequences = requests.get(f"{dashboard_url}/api/sms-sequences", auth=auth, timeout=15).json()
    active = next((s for s in sequences if s.get("is_active")), None)
    if not active:
        print("NO ACTIVE SEQUENCE: no sms_sequences row has is_active=true")
        sys.exit(2)

    template = (active.get("steps") or {}).get(_SEQUENCE_STAGE, "")
    if not _LINK_PLACEHOLDER.search(template):
        print(f"NO LOOM PLACEHOLDER: '{active['name']}' primed-message step has no [Loom link] placeholder")
        print(f"TEMPLATE WAS: {template!r}")
        sys.exit(3)

    body = _LINK_PLACEHOLDER.sub(watch_url, template).strip()

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

    print(f"SENT to {phone} using sequence '{active['name']}' (2. Primed Message)")
    print(f"BODY: {body}")


if __name__ == "__main__":
    main()
