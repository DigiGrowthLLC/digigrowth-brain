"""
Serves every client's funnel on their own subdomain (funnel_domain on the
Marketing Setup tab, e.g. go.advantagetherapy.vegas) through ONE Vercel
project, "client-funnels". It doesn't copy the page: host-matched rewrites
proxy / to pages.digigrowthllc.com/lp/<slug> and pass /lp/... (book, chat,
images) and the view beacon through, so booking, chat and Website stats keep
working and edits in the OS show up immediately. Railway's plan caps custom
domains per service, hence Vercel.

Rebuilds client-funnels/vercel.json from the dashboard, deploys it to
production and adds any new domain to the project. Then the DNS host needs a
CNAME: host = the label ("go"), value = cname.vercel-dns.com.

  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/deploy_client_funnels.py
"""
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from service_delivery_status import api  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJECT_DIR = ROOT / "client-funnels"
PROJECT = "client-funnels"
SCOPE = "digi-growth"


def bare_host(value: str) -> str:
    return re.sub(r"^https?://", "", (value or "").strip().lower()).split("/")[0].split(":")[0]


def funnels() -> dict[str, str]:
    """{funnel host: landing page slug} for every client with a funnel_domain."""
    hosts = {}
    for client in api("GET", "/api/clients"):
        cfg = api("GET", f"/api/clients/{client['id']}/marketing-config") or {}
        host = bare_host(cfg.get("funnel_domain") or "")
        m = re.search(r"/lp/([^/?#]+)", cfg.get("landing_page_url") or "")
        if host and m:
            hosts[host] = m.group(1)
        elif host:
            print(f"! {client['name']}: funnel_domain {host} set but landing_page_url has no /lp/<slug>, skipped")
    return hosts


def vercel(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["vercel", *args, "--scope", SCOPE], cwd=PROJECT_DIR,
                          capture_output=True, text=True, shell=os.name == "nt")


def main():
    pages = (os.environ.get("LANDING_PAGES_URL") or "https://pages.digigrowthllc.com").rstrip("/")
    hosts = funnels()
    if not hosts:
        sys.exit("No client has a funnel_domain saved yet.")

    rewrites = [
        {"source": "/", "has": [{"type": "host", "value": host}], "destination": f"{pages}/lp/{slug}"}
        for host, slug in sorted(hosts.items())
    ] + [
        {"source": "/lp/:path*", "destination": f"{pages}/lp/:path*"},
        {"source": "/track/view-event", "destination": f"{pages}/track/view-event"},
    ]
    PROJECT_DIR.mkdir(exist_ok=True)
    (PROJECT_DIR / "vercel.json").write_text(json.dumps({"rewrites": rewrites}, indent=2) + "\n", encoding="utf-8")
    for host, slug in sorted(hosts.items()):
        print(f"{host} -> {pages}/lp/{slug}")

    if not (PROJECT_DIR / ".vercel" / "project.json").exists():
        r = vercel("link", "--yes", "--project", PROJECT)
        if r.returncode:
            sys.exit(r.stderr)
    r = vercel("deploy", "--prod", "--yes")
    if r.returncode:
        sys.exit(r.stderr)
    print("deployed:", r.stdout.strip().splitlines()[-1])

    for host in sorted(hosts):
        r = vercel("domains", "add", host, PROJECT)
        out = (r.stdout + r.stderr).strip()
        if r.returncode and "already" not in out.lower():
            print(f"! {host}: {out.splitlines()[-1] if out else 'domains add failed'}")
        else:
            print(f"{host}: on {PROJECT}. DNS: CNAME {host.split('.')[0]} -> cname.vercel-dns.com")


if __name__ == "__main__":
    main()
