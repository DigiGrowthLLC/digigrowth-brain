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
    if len(sys.argv) < 3:
        print("Usage: python publish_to_watch.py <video.mp4> <slug> [title] [contact_id]")
        sys.exit(1)

    video_path = pathlib.Path(sys.argv[1])
    slug = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else slug
    # Optional — the CRM contact this video was made for (already resolved
    # by lookup_lead.py earlier in the outreach-video skill's workflow).
    # Lets the dashboard's Loom Outreach analytics funnel know this video
    # was sent to a specific prospect, so their later view/engaged/
    # interested/booked progress can be tracked. Omit for a generic/
    # untargeted upload.
    contact_id = sys.argv[4] if len(sys.argv) > 4 else None

    if not video_path.exists():
        print(f"File not found: {video_path}")
        sys.exit(1)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")

    data = {"slug": slug, "title": title}
    if contact_id:
        data["contact_id"] = contact_id

    with open(video_path, "rb") as f:
        resp = requests.post(
            f"{dashboard_url}/api/watch-videos",
            files={"file": (video_path.name, f, "video/mp4")},
            data=data,
            auth=("admin", password),
            timeout=120,
        )
    resp.raise_for_status()
    body = resp.json()

    print(f"WATCH_URL: {body['watch_url']}")


if __name__ == "__main__":
    main()
