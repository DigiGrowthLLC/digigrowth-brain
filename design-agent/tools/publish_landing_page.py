"""
Publishes an approved landing page: uploads the hero image to R2 (if one
exists), creates/updates the landing_pages row, and returns the final public
URL. Only ever called AFTER Dylan has approved the page inside the session —
this script has no approval logic of its own, it trusts the caller.

Usage:
    python publish_landing_page.py <slug> <html_file> <business> [contact_id] [hero_image]

<hero_image> is optional — omit it if the generator didn't produce one.
"""
import sys
import subprocess
import pathlib
import requests


def doppler_secret(name):
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--project", "digigrowth", "--config", "prd", "--plain"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main():
    if len(sys.argv) < 4:
        print("Usage: python publish_landing_page.py <slug> <html_file> <business> [contact_id] [hero_image]")
        sys.exit(1)

    slug = sys.argv[1]
    html_path = pathlib.Path(sys.argv[2])
    business = sys.argv[3]
    contact_id = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    hero_image_path = pathlib.Path(sys.argv[5]) if len(sys.argv) > 5 else None

    if not html_path.exists():
        print(f"File not found: {html_path}")
        sys.exit(1)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")
    auth = ("admin", password)

    html_text = html_path.read_text(encoding="utf-8")

    create_resp = requests.post(
        f"{dashboard_url}/api/landing-pages",
        json={"slug": slug, "business": business, "contact_id": contact_id, "html": html_text},
        auth=auth,
        timeout=30,
    )
    create_resp.raise_for_status()

    if hero_image_path and hero_image_path.exists():
        presign_resp = requests.post(
            f"{dashboard_url}/api/landing-pages/{slug}/hero-image/presign",
            json={"slug": slug, "content_type": "image/png"},
            auth=auth,
            timeout=30,
        )
        presign_resp.raise_for_status()
        presign_body = presign_resp.json()
        upload_url = presign_body["upload_url"]
        r2_key = presign_body["r2_key"]

        with open(hero_image_path, "rb") as f:
            put_resp = requests.put(upload_url, data=f, headers={"Content-Type": "image/png"}, timeout=60)
        put_resp.raise_for_status()

        complete_resp = requests.post(
            f"{dashboard_url}/api/landing-pages/{slug}/hero-image/complete",
            json={"slug": slug, "r2_key": r2_key},
            auth=auth,
            timeout=30,
        )
        complete_resp.raise_for_status()

    approve_resp = requests.post(
        f"{dashboard_url}/api/landing-pages/{slug}/approve",
        auth=auth,
        timeout=30,
    )
    approve_resp.raise_for_status()

    try:
        landing_pages_url = doppler_secret("LANDING_PAGES_URL").rstrip("/")
        print(f"URL: {landing_pages_url}/lp/{slug}")
    except subprocess.CalledProcessError:
        # LANDING_PAGES_URL not set in Doppler yet — the branded subdomain
        # hasn't been configured (see design-agent's landing-page-mockup
        # skill, "branded subdomain" setup note). Print the path only.
        print(f"LP_PATH: /lp/{slug}")
        print("LANDING_PAGES_URL isn't set in Doppler yet — prepend the branded "
              "landing-pages domain once it's configured to get the final link.")


if __name__ == "__main__":
    main()
