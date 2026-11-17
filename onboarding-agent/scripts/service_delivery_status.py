"""
Service-delivery status for one client: runs the dashboard's autocheck, then
prints the Marketing Setup checklist (every step by phase, done or not, with
its proof or how-to) plus the client-side blockers (portal action items,
onboarding form, resources). Used by the service-delivery-setup skill to decide
what to walk Dylan through next.

Steps come from the dashboard itself (GET /api/clients/{id}/setup, defined in
dashboard/backend/setup_steps.py), so this never drifts from the Setup tab.

Run with the dashboard credentials injected, never typed:
  doppler run --project digigrowth --config prd -- python onboarding-agent/scripts/service_delivery_status.py "Advantage Therapy"
  ... service_delivery_status.py 4 --tick a2p --tick review    # mark manual steps done (step ids)
"""
import argparse
import base64
import json
import os
import sys
import urllib.request


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
    ap.add_argument("--tick", action="append", default=[], help="step id to mark done (repeatable)")
    ap.add_argument("--untick", action="append", default=[], help="step id to mark not done")
    args = ap.parse_args()

    client = find_client(args.client)
    cid = client["id"]
    for ref, value in [(r, True) for r in args.tick] + [(r, False) for r in args.untick]:
        api("PUT", f"/api/clients/{cid}/setup/steps/{ref}", {"done": value})
    if args.tick or args.untick:
        print(f"Updated steps: +{args.tick} -{args.untick}")

    ticked = api("POST", f"/api/clients/{cid}/marketing-config/autocheck").get("ticked") or []
    cfg = api("GET", f"/api/clients/{cid}/marketing-config")
    full = api("GET", f"/api/clients/{cid}")
    setup = api("GET", f"/api/clients/{cid}/setup")

    print(f"# {client['name']} (client {cid}) - contact {client.get('contact_name')} - package {setup['package']}")
    print(f"portal: {full.get('portal_url')}")
    print(f"services ({setup.get('services_from')}{', intake not answered yet' if setup.get('intake_pending') else ''}): "
          f"{', '.join(setup.get('services') or [])}")
    if ticked:
        print(f"auto-ticked just now: {ticked}")
    for ph in setup["phases"]:
        steps = [s for s in setup["steps"] if s["phase"] == ph["id"]]
        if not steps:
            continue
        print(f"\n## {ph['title']}" + (f"\n   {ph['note']}" if ph["note"] else ""))
        for st in steps:
            mark = "x" if st["done"] else " "
            how = st["how"][:240] + ("..." if len(st["how"]) > 240 else "")
            extra = st["proof"] or ("ticked by hand" if st["ticked"] else how)
            print(f"  [{mark}] {st['id']}: {st['title']} -- {extra}")
    print(f"\nSetup: {setup['done']}/{setup['total']} done")
    if setup.get("client_ask"):
        print("\n## Client ask still outstanding\n" + setup["client_ask"])

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
    for k in ("twilio_number", "call_forward_number",
              "meta_ad_account_id", "meta_page_id", "meta_pixel_id", "meta_form_id", "make_scenario_id",
              "lead_ads_error", "response_ai_enabled", "voice_agent_enabled", "retell_agent_id",
              "calendly_event_type_url", "ghl_last_webhook_at"):
        print(f"  {k}: {cfg.get(k)}")
    print(f"  booking link (calendly_url): {full.get('calendly_url')}")
    print(f"  booking alert on: {full.get('booking_notification_enabled')}")


if __name__ == "__main__":
    main()
