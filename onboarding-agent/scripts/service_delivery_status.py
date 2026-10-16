"""
Service-delivery status for one client: runs the dashboard's guide autocheck,
then prints the Marketing Setup "Setup Order" (every step, in order, ticked or
not) plus the client-side blockers (portal action items, onboarding form,
resources). Used by the service-delivery-setup skill to decide what to walk
Dylan through next.

Step text and order are read from dashboard/frontend/src/panels/
ClientsPanel.jsx (MARKETING_GUIDES + SETUP_ORDER_PHASES) so this never drifts
from what the Marketing Setup tab shows.

Run with the dashboard credentials injected, never typed:
  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py "Advantage Therapy"
  ... service_delivery_status.py 4 --tick response_ai:13 --tick sms:1    # mark manual steps done
"""
import argparse
import base64
import json
import os
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "dashboard" / "frontend" / "src" / "panels" / "ClientsPanel.jsx"


def api(method: str, path: str, body=None, auth=True):
    base = os.environ["DASHBOARD_URL"].rstrip("/")
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if auth:
        token = base64.b64encode(f"admin:{os.environ['DASHBOARD_PASSWORD']}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or "null")


def load_guides():
    src = PANEL.read_text(encoding="utf-8")
    block = src[src.index("const MARKETING_GUIDES = {"):src.index("const SETUP_ORDER_PHASES")]
    guides, current = {}, None
    for line in block.splitlines():
        m = re.match(r"^  (\w+): \{$", line)
        if m:
            current = m.group(1)
            guides[current] = {"title": "", "steps": []}
            continue
        if current:
            t = re.match(r'^    title: "(.*)",$', line)
            if t:
                guides[current]["title"] = t.group(1)
            for txt in re.findall(r'\{ text: "((?:[^"\\]|\\.)*)"', line):
                guides[current]["steps"].append(json.loads(f'"{txt}"'))
    order_src = src[src.index("const SETUP_ORDER_PHASES"):src.index("const SETUP_ORDER_GUIDE")]
    phases = []
    for m in re.finditer(r'(\w+): \{\s*title: "([^"]+)",\s*note: "((?:[^"\\]|\\.)*)",\s*steps: \[(.*?)\]\s*,?\s*\}', order_src, re.S):
        refs = [(g, int(i)) for g, i in re.findall(r'\["(\w+)", (\d+)\]', m.group(4))]
        phases.append({"key": m.group(1), "title": m.group(2), "note": json.loads(f'"{m.group(3)}"'), "steps": refs})
    return guides, phases


def find_client(query: str) -> dict:
    clients = api("GET", "/api/clients")
    if query.isdigit():
        hit = [c for c in clients if c["id"] == int(query)]
    else:
        q = query.lower()
        hit = [c for c in clients if q in (c["name"] or "").lower() or q in (c.get("contact_name") or "").lower()]
    if len(hit) != 1:
        sys.exit(f"Client match for {query!r}: {[(c['id'], c['name']) for c in hit] or 'none'}. Be more specific.")
    return hit[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client", help="client id, name or contact name")
    ap.add_argument("--tick", action="append", default=[], help="guide:index to mark done (repeatable)")
    ap.add_argument("--untick", action="append", default=[], help="guide:index to mark not done")
    args = ap.parse_args()

    client = find_client(args.client)
    cid = client["id"]
    if args.tick or args.untick:
        cfg = api("GET", f"/api/clients/{cid}/marketing-config")
        progress = cfg.get("guide_progress") or {}
        for ref, value in [(r, True) for r in args.tick] + [(r, False) for r in args.untick]:
            g, i = ref.split(":")
            progress.setdefault(g, {})[str(int(i))] = value
        api("PUT", f"/api/clients/{cid}/marketing-config", {"guide_progress": progress})
        print(f"Updated guide_progress: +{args.tick} -{args.untick}")

    ticked = api("POST", f"/api/clients/{cid}/marketing-config/autocheck").get("ticked") or {}
    cfg = api("GET", f"/api/clients/{cid}/marketing-config")
    full = api("GET", f"/api/clients/{cid}")
    progress = cfg.get("guide_progress") or {}
    guides, phases = load_guides()

    print(f"# {client['name']} (client {cid}) - contact {client.get('contact_name')}")
    print(f"portal: {full.get('portal_url')}")
    if ticked:
        print(f"auto-ticked just now: {ticked}")
    total = done = 0
    for ph in phases:
        print(f"\n## {ph['title']}\n   {ph['note']}")
        for g, i in ph["steps"]:
            ok = bool(progress.get(g, {}).get(str(i)))
            total += 1
            done += ok
            text = guides[g]["steps"][i] if i < len(guides[g]["steps"]) else "(missing step)"
            print(f"  [{'x' if ok else ' '}] {g}:{i}  ({guides[g]['title']} step {i + 1}) {text[:220]}{'...' if len(text) > 220 else ''}")
    print(f"\nSetup Order: {done}/{total} done")

    token = full.get("portal_token")
    if token:
        items = api("GET", f"/portal-api/{token}/action-items", auth=False)
        print("\n## Client's portal action items")
        for it in items:
            print(f"  [{'x' if it.get('completed_at') else ' '}] {it['title']}")
        ob = api("GET", f"/portal-api/{token}/onboarding", auth=False)
        missing = [s for s in ob["sections"] if s not in (ob.get("responses") or {})]
        print(f"\n## Onboarding form: {ob.get('progress')} sections done; missing: {', '.join(missing) or 'none'}")
        todo = api("GET", f"/portal-api/{token}/todo", auth=False)
        print("\n## Portal launch checklist (client-visible To Do)")
        for it in todo:
            if it.get("phase") == "prelaunch":
                print(f"  [{'x' if it.get('completed_at') else ' '}] id {it['id']}: {it['title']}")
    resources = api("GET", f"/api/clients/{cid}/resources")
    print("\n## Resources")
    for k in ("ads_manager_resource", "registrar_resource", "hosting_resource", "funnel_resource"):
        print(f"  {k}: {full.get(k) or '-'}")
    for r in resources:
        print(f"  {r['label']}: {r['value']}")
    print("\n## Key config")
    for k in ("twilio_number", "call_forward_number", "email_subdomain", "email_dns_status", "gmail_sender_email",
              "meta_ad_account_id", "meta_page_id", "meta_pixel_id", "make_scenario_id", "lead_ads_error",
              "response_ai_enabled", "calendly_event_type_url", "calendly_webhook_error", "ghl_last_webhook_at"):
        print(f"  {k}: {cfg.get(k)}")
    print(f"  booking link (calendly_url): {full.get('calendly_url')}")
    print(f"  booking alert on: {full.get('booking_notification_enabled')}")


if __name__ == "__main__":
    main()
