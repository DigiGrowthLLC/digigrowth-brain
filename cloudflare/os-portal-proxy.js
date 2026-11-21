// Cloudflare Worker "os-portal-proxy" (2026-11-21).
//
// os.digigrowthllc.com (the OS) and portal.digigrowthllc.com (client portals)
// both forward to the same Railway service through pages.digigrowthllc.com,
// because Railway's plan caps the service at 2 custom domains (pages. + loom.).
// The frontend picks OS vs portal from the browser's hostname
// (dashboard/frontend/src/main.jsx), so nothing here needs to know the
// difference. Deploy: cloudflare/deploy_worker.py (routes os.* and portal.*).

const ORIGIN = "https://pages.digigrowthllc.com";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = ORIGIN + url.pathname + url.search;
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.host);
    headers.set("X-Forwarded-Proto", "https");
    // The Worker's own IP replaces the visitor's as cf-connecting-ip on the
    // subrequest; tracking_exclusion.client_ip reads this instead.
    const ip = request.headers.get("cf-connecting-ip");
    if (ip) headers.set("X-DG-Client-IP", ip);
    headers.delete("host");

    const resp = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual",
    });

    // Keep redirects on the host the person is using.
    const loc = resp.headers.get("location");
    if (loc && loc.startsWith(ORIGIN)) {
      const out = new Response(resp.body, resp);
      out.headers.set("location", `https://${url.host}${loc.slice(ORIGIN.length)}`);
      return out;
    }
    return resp;
  },
};
