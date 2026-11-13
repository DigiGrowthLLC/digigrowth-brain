"""Keeps Dylan's own visits out of every client's funnel analytics.

Two lists, both checked by is_excluded():
  - Manual (dialer_settings 'tracking_excluded_ips'): permanent, set from
    POST /api/content-analytics/exclude-my-ip (content_tracking.py).
  - Automatic (dialer_settings 'tracking_auto_excluded_ips'): any IP that
    passes the OS dashboard's password check (main.py require_auth) is
    recorded here with a last-seen time. Only Dylan has that password, so
    whatever network he's on (home, phone, travelling) stops counting the
    moment he opens the OS there. Entries lapse after AUTO_TTL_DAYS without
    a dashboard visit, so a shared mobile/carrier IP he once used doesn't
    hide real patients forever. Client portals use a token, not the
    password, so a clinic's own visits are never excluded by this.

Applied to: funnel page views (content_tracking.py beacon + the server-side
/lp view log), booking-page steps (routers/booking.py, booking_engine.py)
and bookings themselves (bookings.excluded), which the portal funnel
(routers/client_funnel.py) drops.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import Request

from db import get_pool

MANUAL_KEY = "tracking_excluded_ips"
AUTO_KEY = "tracking_auto_excluded_ips"
AUTO_TTL_DAYS = 30
_WRITE_EVERY_SEC = 6 * 3600   # refresh an IP's last-seen at most this often
_CACHE_SEC = 60

# Test phone used for every test lead/booking (memory: default test number).
TEST_PHONE_DIGITS = ("7542485326",)

_cache: tuple[float, set[str]] = (0.0, set())
_last_written: dict[str, float] = {}


def client_ip(request: Request) -> str:
    """Real visitor IP behind Cloudflare / the Vercel funnel proxy / Railway:
    cf-connecting-ip when Cloudflare is in front, else the first
    X-Forwarded-For hop."""
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _load(conn, key: str):
    row = await conn.fetchrow("SELECT value FROM dialer_settings WHERE key = $1", key)
    if not row or not row["value"]:
        return None
    try:
        return json.loads(row["value"])
    except Exception:
        return None


async def _save(conn, key: str, value) -> None:
    await conn.execute(
        "INSERT INTO dialer_settings (key, value, updated_at) VALUES ($1, $2, now()) "
        "ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()",
        key, json.dumps(value),
    )


def _fresh(auto: dict) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=AUTO_TTL_DAYS)
    out = {}
    for ip, seen in (auto or {}).items():
        try:
            if datetime.fromisoformat(seen) >= cutoff:
                out[ip] = seen
        except Exception:
            continue
    return out


async def excluded_ips(conn=None) -> set[str]:
    global _cache
    if time.monotonic() - _cache[0] < _CACHE_SEC:
        return _cache[1]
    try:
        if conn is None:
            pool = await get_pool()
            async with pool.acquire() as c:
                manual, auto = await _load(c, MANUAL_KEY), await _load(c, AUTO_KEY)
        else:
            manual, auto = await _load(conn, MANUAL_KEY), await _load(conn, AUTO_KEY)
    except Exception as e:
        print(f"[tracking_exclusion] load failed: {e}")
        return _cache[1]
    ips = set(manual or []) | set(_fresh(auto if isinstance(auto, dict) else {}).keys())
    _cache = (time.monotonic(), ips)
    return ips


async def is_excluded(request: Request) -> bool:
    ip = client_ip(request)
    return bool(ip) and ip in await excluded_ips()


async def note_admin_ip(request: Request) -> None:
    """Called on every authenticated OS request; writes at most every 6h per IP."""
    global _cache
    ip = client_ip(request)
    if not ip:
        return
    now = time.monotonic()
    if now - _last_written.get(ip, -1e12) < _WRITE_EVERY_SEC:
        return
    _last_written[ip] = now
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            auto = await _load(conn, AUTO_KEY)
            auto = _fresh(auto if isinstance(auto, dict) else {})
            auto[ip] = datetime.now(timezone.utc).isoformat()
            await _save(conn, AUTO_KEY, auto)
        _cache = (0.0, set())  # pick the new IP up immediately
    except Exception as e:
        print(f"[tracking_exclusion] note_admin_ip failed: {e}")


async def auto_list() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        auto = await _load(conn, AUTO_KEY)
    return _fresh(auto if isinstance(auto, dict) else {})
