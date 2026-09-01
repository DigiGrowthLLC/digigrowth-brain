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
        print("Usage: python publish_to_watch.py <video.mp4> <slug> [title]")
        sys.exit(1)

    video_path = pathlib.Path(sys.argv[1])
    slug = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else slug

    if not video_path.exists():
        print(f"File not found: {video_path}")
        sys.exit(1)

    dashboard_url = doppler_secret("DASHBOARD_URL").rstrip("/")
    password = doppler_secret("DASHBOARD_PASSWORD")

    with open(video_path, "rb") as f:
        resp = requests.post(
            f"{dashboard_url}/api/watch-videos",
            files={"file": (video_path.name, f, "video/mp4")},
            data={"slug": slug, "title": title},
            auth=("admin", password),
            timeout=120,
        )
    resp.raise_for_status()
    body = resp.json()

    print(f"WATCH_URL: {body['watch_url']}")


if __name__ == "__main__":
    main()
