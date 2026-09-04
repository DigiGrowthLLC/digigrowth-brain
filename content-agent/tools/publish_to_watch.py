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
    auth = ("admin", password)

    # Two-step publish: get a presigned R2 URL, PUT the video straight to R2
    # (bytes never pass through the dashboard backend's own memory — the
    # old GitHub-Contents-API upload used to OOM-crash the Railway container
    # on anything much above ~30MB, see dashboard/backend/routers/watch.py),
    # then tell the backend the upload finished so it can record the row.
    presign_resp = requests.post(
        f"{dashboard_url}/api/watch-videos/presign",
        json={"slug": slug, "content_type": "video/mp4"},
        auth=auth,
        timeout=30,
    )
    presign_resp.raise_for_status()
    presign_body = presign_resp.json()
    upload_url = presign_body["upload_url"]
    r2_key = presign_body["r2_key"]

    file_size = video_path.stat().st_size
    with open(video_path, "rb") as f:
        put_resp = requests.put(
            upload_url,
            data=f,
            headers={"Content-Type": "video/mp4"},
            timeout=300,
        )
    put_resp.raise_for_status()

    complete_data = {
        "slug": slug,
        "title": title,
        "r2_key": r2_key,
        "file_size": file_size,
        "content_type": "video/mp4",
    }
    if contact_id:
        complete_data["contact_id"] = contact_id

    complete_resp = requests.post(
        f"{dashboard_url}/api/watch-videos/complete",
        json=complete_data,
        auth=auth,
        timeout=30,
    )
    complete_resp.raise_for_status()
    body = complete_resp.json()

    print(f"WATCH_URL: {body['watch_url']}")


if __name__ == "__main__":
    main()
