"""Deploy cloudflare/os-portal-proxy.js and point os. + portal.digigrowthllc.com at it.

    doppler run --project digigrowth --config prd -- python cloudflare/deploy_worker.py

Needs CLOUDFLARE_API_TOKEN with: Zone DNS Edit, Zone Workers Routes Edit,
Account Workers Scripts Edit. Safe to re-run (updates in place).
"""
import json
import os
import pathlib
import sys
import urllib.request

API = "https://api.cloudflare.com/client/v4"
ZONE_NAME = "digigrowthllc.com"
SCRIPT = "os-portal-proxy"
HOSTS = ["os.digigrowthllc.com", "portal.digigrowthllc.com"]
TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]


def call(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        out = json.load(e)
        sys.exit(f"{method} {path} failed: {out.get('errors')}")


zone = call("GET", f"/zones?name={ZONE_NAME}")["result"][0]
zone_id, account_id = zone["id"], zone["account"]["id"]

# 1. Upload the script (ES module).
code = (pathlib.Path(__file__).parent / "os-portal-proxy.js").read_text(encoding="utf-8")
boundary = "----dgworker"
meta = json.dumps({"main_module": "worker.js", "compatibility_date": "2026-11-01"})
raw = (
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n{meta}\r\n"
    f"--{boundary}\r\nContent-Disposition: form-data; name=\"worker.js\"; filename=\"worker.js\"\r\n"
    f"Content-Type: application/javascript+module\r\n\r\n{code}\r\n--{boundary}--\r\n"
).encode()
call("PUT", f"/accounts/{account_id}/workers/scripts/{SCRIPT}", raw=raw, ctype=f"multipart/form-data; boundary={boundary}")
print("script uploaded")

existing_dns = {r["name"]: r for r in call("GET", f"/zones/{zone_id}/dns_records?per_page=200")["result"]}
existing_routes = {r["pattern"]: r for r in call("GET", f"/zones/{zone_id}/workers/routes")["result"]}
for host in HOSTS:
    # 2. A proxied placeholder record so Cloudflare answers for the host
    #    (the Worker handles every request; 192.0.2.1 is never contacted).
    if host not in existing_dns:
        call("POST", f"/zones/{zone_id}/dns_records",
             {"type": "A", "name": host, "content": "192.0.2.1", "proxied": True, "comment": "Worker os-portal-proxy"})
        print("dns added", host)
    # 3. Route all of the host's traffic to the Worker.
    pattern = f"{host}/*"
    if pattern not in existing_routes:
        call("POST", f"/zones/{zone_id}/workers/routes", {"pattern": pattern, "script": SCRIPT})
        print("route added", pattern)
print("done")
