"""
Automatic bookkeeping for DigiGrowth's own money (2026-11-22).

Where the numbers come from:
  - Business spending = the Novo bank account. Novo has no API and Plaid
    never approved us, so Zapier's Novo "New Transaction" trigger appends a
    row to a Google Sheet (Dylan's personal Google account, the one the OS
    already reads Drive with), and sync_sheet() pulls that sheet every hour.
    A Novo CSV export can be uploaded too (history from before Zapier, or a
    backup); both land in `transactions` and dedupe against each other.
  - Revenue = Stripe (clients pay through Stripe, Stripe pays out to Novo).
    sync_stripe() reads the platform balance transactions: each payment is
    Client Revenue matched to a client, Stripe's fee is an expense. The
    Stripe -> Novo deposits in the bank feed are 'Transfer' and never count.
  - Per-client costs = real numbers, not the old flat $500 Meta / $30 Twilio
    estimates: Meta spend (ad_campaign_stats), Twilio usage of the client's
    subaccount, Retell call cost (client_voice_calls.cost_cents). Posted to
    client_transactions once per client per month (auto_key, re-upserted).

Sorting: a bank row first goes through Dylan's rules (merchant -> category,
learned every time he re-categorises a row), then Claude. Anything Claude
isn't sure of lands in the Finances tab's "Needs a look" list.

Monthly: on the 1st a To-Do with last month's revenue, spend by category,
profit per client and what still needs a look.
"""

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from db import get_pool

ET = ZoneInfo("America/New_York")

EXPENSE_CATEGORIES = [
    "Ad Spend", "Software & Tools", "AI & APIs", "Phone & SMS", "Contractors",
    "Payment & Bank Fees", "Refunds", "Office & Equipment", "Education",
    "Travel & Meals", "Taxes & Legal", "Other",
]
INCOME_CATEGORIES = ["Client Revenue", "Other Income"]
TRANSFER = "Transfer"
NOT_COUNTED = ("Transfer", "Transfers")  # 'Transfers' = the old manual-ledger name
ALL_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES + [TRANSFER]

_MODEL = os.environ.get("FINANCE_AI_MODEL", "claude-haiku-5-5")
_CONFIDENT = 0.75
_STRIPE_START = date(2026, 1, 1)
_FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "me.com", "live.com", "msn.com"}


async def ensure_schema(conn) -> None:
    await conn.execute("""
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source       TEXT NOT NULL DEFAULT 'manual';
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS external_id  TEXT;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS client_id    INTEGER REFERENCES clients(id) ON DELETE SET NULL;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS merchant_key TEXT;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counterparty TEXT;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS needs_review BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reviewed     BOOLEAN NOT NULL DEFAULT false;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS ai_note      TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_external ON transactions(external_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_review ON transactions(needs_review) WHERE needs_review;

        -- Learned from Dylan's corrections: this merchant is always this category.
        CREATE TABLE IF NOT EXISTS finance_rules (
            id           SERIAL PRIMARY KEY,
            merchant_key TEXT NOT NULL UNIQUE,
            category     TEXT NOT NULL,
            example      TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        -- Stripe customer -> client, saved when Dylan assigns one by hand.
        CREATE TABLE IF NOT EXISTS finance_client_links (
            counterparty TEXT PRIMARY KEY,
            client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE
        );
        -- Imported rows Dylan deleted, so the next sheet sync doesn't bring them back.
        CREATE TABLE IF NOT EXISTS finance_deleted_ids (external_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS finance_settings (
            id               INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            sheet_id         TEXT,
            sheet_synced_at  TIMESTAMPTZ,
            sheet_error      TEXT,
            stripe_synced_at TIMESTAMPTZ,
            stripe_cursor    BIGINT,
            stripe_error     TEXT,
            costs_synced_at  TIMESTAMPTZ,
            costs_error      TEXT
        );
        INSERT INTO finance_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

        -- Who pays a client's Meta ads: true = Dylan's card (pilots), so the
        -- spend is a DigiGrowth cost in profit-per-client.
        ALTER TABLE clients ADD COLUMN IF NOT EXISTS ads_on_our_card BOOLEAN NOT NULL DEFAULT true;
        ALTER TABLE client_transactions ADD COLUMN IF NOT EXISTS auto_key TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_client_transactions_auto ON client_transactions(auto_key);
        ALTER TABLE client_voice_calls ADD COLUMN IF NOT EXISTS cost_cents NUMERIC(10,2);

        -- The flat Meta $500 / Twilio $30 placeholders are replaced by real
        -- monthly numbers (post_client_costs).
        DELETE FROM client_transactions
         WHERE notes = 'Default monthly allocation (auto-added)'
           AND description IN ('Meta ad spend', 'Twilio');
    """)


# ── Helpers ──────────────────────────────────────────────────────────────────

_NOISE = {"POS", "PURCHASE", "DEBIT", "CARD", "ACH", "WITHDRAWAL", "DEPOSIT", "PAYMENT", "RECURRING",
          "ONLINE", "TRANSFER", "PENDING", "CHECKCARD", "VISA", "MASTERCARD", "PMT", "TRANSACTION", "FROM", "TO"}


def merchant_key(desc: str | None) -> str:
    """Stable merchant name from a bank line: 'FACEBK *8YX2K fb.me/ads CA' -> 'FACEBK FB'."""
    words = []
    for tok in re.split(r"\s+", (desc or "").upper()):
        if not tok or re.search(r"\d", tok):
            continue  # reference numbers change every charge
        tok = re.sub(r"[^A-Z&]+", " ", tok).strip()
        for w in tok.split():
            if w not in _NOISE and len(w) > 1:
                words.append(w)
    return " ".join(words[:2]) or (desc or "").strip().upper()[:20]


def _parse_amount(raw) -> float | None:
    s = str(raw or "").strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-") or s.endswith("-")
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _parse_date(raw) -> date | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo:
            dt = dt.astimezone(ET)
        return dt.date()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s.split(" ")[0] if fmt.count(" ") == 0 else s, fmt).date()
        except ValueError:
            continue
    return None


def _col(headers: list[str], *names: str) -> int | None:
    low = [h.strip().lower() for h in headers]
    for n in names:
        if n in low:
            return low.index(n)
    for n in names:
        for i, h in enumerate(low):
            if n in h:
                return i
    return None


def parse_bank_csv(text: str) -> list[dict]:
    """Novo export or the Zapier sheet. Needs a date, a description and either
    a signed amount or debit/credit columns; an optional type/direction column
    ('debit', 'withdrawal', 'out') flips an unsigned amount negative."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    hi = next((i for i, r in enumerate(rows[:10])
               if _col(r, "date", "posted", "created") is not None and _col(r, "amount", "debit", "credit", "value") is not None), None)
    if hi is None:
        raise ValueError("Couldn't find a header row with a Date column.")
    h = rows[hi]
    c_date = _col(h, "date", "posted", "created")
    c_desc = _col(h, "description", "merchant", "name", "memo", "counterparty", "details")
    c_amt = _col(h, "amount", "value")
    c_debit = _col(h, "debit", "withdrawal", "money out")
    c_credit = _col(h, "credit", "deposit", "money in")
    c_type = _col(h, "type", "direction", "transaction type")
    if c_desc is None or (c_amt is None and c_debit is None and c_credit is None):
        raise ValueError("Need Description and Amount (or Debit/Credit) columns. Found: " + ", ".join(h))

    out = []
    for r in rows[hi + 1:]:
        get = lambda i: r[i] if i is not None and i < len(r) else ""
        d = _parse_date(get(c_date))
        if not d:
            continue
        if c_amt is not None and _parse_amount(get(c_amt)) is not None:
            amt = _parse_amount(get(c_amt))
            kind = get(c_type).lower()
            if amt > 0 and any(k in kind for k in ("debit", "withdraw", "out", "purchase", "sent")):
                amt = -amt
        else:
            debit, credit = _parse_amount(get(c_debit)), _parse_amount(get(c_credit))
            if debit:
                amt = -abs(debit)
            elif credit:
                amt = abs(credit)
            else:
                continue
        if not amt:
            continue
        out.append({"date": d, "description": get(c_desc).strip()[:300], "amount": round(amt, 2)})
    return out


def _bank_ids(rows: list[dict]) -> None:
    """Same id for the same transaction whether it came from the sheet or a
    CSV: date + amount + nth occurrence that day (descriptions differ between
    Novo's export and Zapier)."""
    seen = Counter()
    for r in rows:
        k = f"{r['date']}|{r['amount']:.2f}"
        seen[k] += 1
        r["external_id"] = f"bank:{k}|{seen[k]}"


async def ingest_bank_rows(rows: list[dict], source: str) -> dict:
    _bank_ids(rows)
    pool = await get_pool()
    added = 0
    async with pool.acquire() as conn:
        deleted = {r["external_id"] for r in await conn.fetch("SELECT external_id FROM finance_deleted_ids")}
        for r in rows:
            if r["external_id"] in deleted:
                continue
            new_id = await conn.fetchval(
                """INSERT INTO transactions (date, description, amount, is_income, category, source, external_id, merchant_key)
                   VALUES ($1, $2, $3, $4, 'Uncategorized', $5, $6, $7)
                   ON CONFLICT (external_id) DO NOTHING RETURNING id""",
                r["date"], r["description"] or None, r["amount"], r["amount"] > 0, source,
                r["external_id"], merchant_key(r["description"]),
            )
            added += bool(new_id)
    sorted_n = await categorize_pending() if added else 0
    return {"added": added, "skipped": len(rows) - added, "sorted": sorted_n}


# ── Google Sheet (Zapier) ────────────────────────────────────────────────────

def sheet_id_from(url_or_id: str) -> str | None:
    s = (url_or_id or "").strip()
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r"[A-Za-z0-9_-]{20,}", s) else None


def _export_sheet_csv(sheet_id: str) -> str:
    import integrations
    data = integrations._drive_service().files().export(fileId=sheet_id, mimeType="text/csv").execute()
    return data.decode("utf-8") if isinstance(data, bytes) else data


async def sync_sheet() -> dict | None:
    import asyncio
    pool = await get_pool()
    async with pool.acquire() as conn:
        sheet_id = await conn.fetchval("SELECT sheet_id FROM finance_settings WHERE id = 1")
    if not sheet_id:
        return None
    try:
        text = await asyncio.to_thread(_export_sheet_csv, sheet_id)
        rows = parse_bank_csv(text) if text.strip() else []
        result = await ingest_bank_rows(rows, "zapier")
        err = None
    except Exception as e:  # noqa: BLE001 - surfaced in the Finances tab
        result, err = None, str(e)[:500]
        print(f"[finance] sheet sync failed: {e}", flush=True)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE finance_settings SET sheet_synced_at = now(), sheet_error = $1 WHERE id = 1", err)
    if err:
        raise RuntimeError(err)
    return result


# ── Stripe revenue ───────────────────────────────────────────────────────────

async def _stripe_get(http: httpx.AsyncClient, path: str, params: list) -> dict:
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    r = await http.get(f"https://api.stripe.com/v1{path}", params=params, auth=(key, ""))
    if r.status_code >= 400:
        raise RuntimeError(f"Stripe {r.status_code}: {r.text[:300]}")
    return r.json()


async def _client_lookup(conn) -> list[dict]:
    rows = await conn.fetch("SELECT id, name, contact_name, email, portal_emails FROM clients WHERE NOT is_test")
    out = []
    for r in rows:
        emails = {e.lower() for e in [r["email"], *(r["portal_emails"] or [])] if e}
        domains = {e.split("@")[1] for e in emails if "@" in e and e.split("@")[1] not in _FREE_MAIL}
        out.append({"id": r["id"], "name": (r["name"] or "").lower(), "contact": (r["contact_name"] or "").lower(),
                    "emails": emails, "domains": domains})
    return out


def _match_client(clients: list[dict], emails: set[str], names: list[str]) -> int | None:
    emails = {e.lower() for e in emails if e}
    for c in clients:
        if emails & c["emails"]:
            return c["id"]
    doms = {e.split("@")[1] for e in emails if "@" in e}
    for c in clients:
        if doms & c["domains"]:
            return c["id"]
    text = " ".join(n.lower() for n in names if n)
    hits = [c["id"] for c in clients if (c["name"] and c["name"] in text) or (c["contact"] and len(c["contact"]) > 4 and c["contact"] in text)]
    return hits[0] if len(hits) == 1 else None


async def sync_stripe() -> dict | None:
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if not key or key.startswith("sk_test_"):
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        cursor = await conn.fetchval("SELECT stripe_cursor FROM finance_settings WHERE id = 1")
        clients = await _client_lookup(conn)
        links = {r["counterparty"]: r["client_id"] for r in await conn.fetch("SELECT * FROM finance_client_links")}
    since = (cursor - 3 * 86400) if cursor else int(datetime.combine(_STRIPE_START, datetime.min.time(), timezone.utc).timestamp())
    added, newest, err = 0, cursor or 0, None
    customers: dict[str, dict] = {}
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            after = None
            while True:
                params = [("limit", "100"), ("created[gte]", str(since)), ("expand[]", "data.source")]
                if after:
                    params.append(("starting_after", after))
                page = await _stripe_get(http, "/balance_transactions", params)
                async with pool.acquire() as conn:
                    for bt in page.get("data", []):
                        newest = max(newest, bt["created"])
                        src = bt.get("source")
                        if isinstance(src, dict) and isinstance(src.get("customer"), str):
                            cid = src["customer"]
                            if cid not in customers:
                                try:
                                    customers[cid] = await _stripe_get(http, f"/customers/{cid}", [])
                                except RuntimeError:
                                    customers[cid] = {"id": cid}
                            src["customer"] = customers[cid]
                        added += await _store_stripe_txn(conn, bt, clients, links)
                if not page.get("has_more"):
                    break
                after = page["data"][-1]["id"]
    except Exception as e:  # noqa: BLE001
        err = str(e)[:500]
        print(f"[finance] stripe sync failed: {e}", flush=True)
    async with pool.acquire() as conn:
        # Stripe lists newest first: only move the cursor after a full pass,
        # or a failure on an older page would skip those payments for good.
        await conn.execute("UPDATE finance_settings SET stripe_synced_at = now(), stripe_cursor = $1, stripe_error = $2 WHERE id = 1",
                           (newest or cursor) if not err else cursor, err)
    if err:
        raise RuntimeError(err)
    return {"added": added}


async def _store_stripe_txn(conn, bt: dict, clients: list[dict], links: dict) -> int:
    kind = bt.get("type")
    if kind not in ("charge", "payment", "refund", "payment_refund", "stripe_fee", "adjustment"):
        return 0  # payouts show up in the bank feed as Transfer
    src = bt.get("source") if isinstance(bt.get("source"), dict) else {}
    cust = src.get("customer") if isinstance(src.get("customer"), dict) else {}
    billing = src.get("billing_details") or {}
    cust_id = cust.get("id") or (src.get("customer") if isinstance(src.get("customer"), str) else None)
    who = billing.get("name") or cust.get("name") or cust.get("email") or billing.get("email") or src.get("receipt_email")
    counterparty = f"stripe:{cust_id}" if cust_id else (f"stripe:{(billing.get('email') or src.get('receipt_email') or '').lower()}" if (billing.get("email") or src.get("receipt_email")) else None)
    client_id = links.get(counterparty) if counterparty else None
    if not client_id:
        client_id = _match_client(clients, {billing.get("email"), cust.get("email"), src.get("receipt_email")},
                                  [who, cust.get("description"), src.get("description"), bt.get("description")])
    day = datetime.fromtimestamp(bt["created"], ET).date()
    gross, fee = bt["amount"] / 100, bt.get("fee", 0) / 100
    label = (src.get("description") or bt.get("description") or "").strip()
    added = 0

    async def put(ext, desc, amount, income, cat, needs, cp, cid):
        nonlocal added
        if await conn.fetchval("SELECT 1 FROM finance_deleted_ids WHERE external_id = $1", ext):
            return
        new = await conn.fetchval(
            """INSERT INTO transactions (date, description, amount, is_income, category, source, external_id,
                                         client_id, counterparty, needs_review, ai_note, merchant_key)
               VALUES ($1, $2, $3, $4, $5, 'stripe', $6, $7, $8, $9, $10, 'STRIPE')
               ON CONFLICT (external_id) DO NOTHING RETURNING id""",
            day, desc[:300], amount, income, cat, ext, cid, cp, needs,
            "Which client paid this?" if needs else None,
        )
        added += bool(new)

    if kind in ("charge", "payment"):
        await put(f"stripe:{bt['id']}", f"Stripe payment: {who or 'unknown'}" + (f" ({label})" if label else ""),
                  round(gross, 2), True, "Client Revenue", client_id is None, counterparty, client_id)
    elif kind in ("refund", "payment_refund"):
        await put(f"stripe:{bt['id']}", f"Stripe refund: {who or 'unknown'}", round(-abs(gross), 2), False,
                  "Refunds", False, counterparty, client_id)
    else:
        await put(f"stripe:{bt['id']}", bt.get("description") or f"Stripe {kind}", round(gross, 2), gross > 0,
                  "Other Income" if gross > 0 else "Payment & Bank Fees", False, None, None)
    if fee and kind not in ("stripe_fee", "adjustment"):
        await put(f"stripe-fee:{bt['id']}", f"Stripe fee: {who or 'payment'}", round(-abs(fee), 2), False,
                  "Payment & Bank Fees", False, None, client_id)
    return added


# ── AI sorting ───────────────────────────────────────────────────────────────

async def categorize_pending(limit: int = 200) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = [dict(r) for r in await conn.fetch(
            """SELECT id, date, description, amount, merchant_key FROM transactions
               WHERE category = 'Uncategorized' AND source <> 'stripe' AND NOT reviewed
               ORDER BY date DESC LIMIT $1""", limit)]
        rules = {r["merchant_key"]: r["category"] for r in await conn.fetch("SELECT merchant_key, category FROM finance_rules")}
        done = 0
        left = []
        for r in rows:
            desc = (r["description"] or "").upper()
            if "STRIPE" in desc:
                cat, note = TRANSFER, "Stripe payout (revenue is counted from Stripe itself)"
            elif r["merchant_key"] in rules:
                cat, note = rules[r["merchant_key"]], "Your rule"
            else:
                left.append(r)
                continue
            await conn.execute("UPDATE transactions SET category = $1, ai_note = $2, needs_review = false WHERE id = $3",
                               cat, note, r["id"])
            done += 1
        examples = [dict(r) for r in await conn.fetch(
            "SELECT merchant_key, category FROM finance_rules ORDER BY updated_at DESC LIMIT 60")]
    for i in range(0, len(left), 40):
        done += await _ai_sort(left[i:i + 40], examples)
    return done


async def _ai_sort(rows: list[dict], examples: list[dict]) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return 0
    import anthropic
    api = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    lines = "\n".join(f'{r["id"]} | {r["date"]} | {r["amount"]:+.2f} | {r["description"]}' for r in rows)
    learned = "\n".join(f'- {e["merchant_key"]} -> {e["category"]}' for e in examples) or "(none yet)"
    prompt = f"""You sort bank transactions for DigiGrowth, a one-person marketing agency that runs Meta ads,
AI text/voice agents (Twilio, Retell, Anthropic/Claude, OpenAI, fal.ai), booking pages and websites
(Railway, Vercel, Cloudflare, GitHub, Google Workspace, Doppler, Zapier, Make, Calendly) for physical
therapy clinics. This is a business-only account (no personal spending). Clients pay through Stripe.

Categories (use exactly one of these names):
Income: {", ".join(INCOME_CATEGORIES)}
Expense: {", ".join(EXPENSE_CATEGORIES)}
Neither: {TRANSFER} (money moved between accounts, Stripe payouts, owner transfers)

Guide: Facebook/Meta/FACEBK = Ad Spend. Twilio, phone numbers, SMS = Phone & SMS. Anthropic, OpenAI,
Retell, fal.ai, ElevenLabs = AI & APIs. Other SaaS/hosting/domains = Software & Tools. Upwork,
Fiverr, freelancers, payroll apps = Contractors. Bank/wire/card fees = Payment & Bank Fees.
Courses, coaching, books = Education.

Dylan's own past decisions (follow these):
{learned}

Transactions (id | date | amount, negative = money out | description):
{lines}

Reply with ONLY a JSON array, one object per transaction:
[{{"id": 123, "category": "Ad Spend", "confidence": 0.95, "why": "Meta ads charge"}}]
confidence = 0..1, how sure you are. Below 0.75 means Dylan should check it."""
    try:
        msg = await api.messages.create(model=_MODEL, max_tokens=4000, messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        m = re.search(r"\[.*\]", text, re.S)
        results = json.loads(m.group(0)) if m else []
    except Exception as e:  # noqa: BLE001 - rows stay Uncategorized and retry next run
        print(f"[finance] AI sort failed: {e}", flush=True)
        return 0
    valid = set(ALL_CATEGORIES)
    ids = {r["id"] for r in rows}
    pool = await get_pool()
    n = 0
    async with pool.acquire() as conn:
        for res in results:
            try:
                tid = int(res.get("id"))
            except (TypeError, ValueError):
                continue
            cat = res.get("category")
            if tid not in ids or cat not in valid:
                continue
            conf = float(res.get("confidence") or 0)
            await conn.execute(
                "UPDATE transactions SET category = $1, ai_note = $2, needs_review = $3 WHERE id = $4 AND NOT reviewed",
                cat, str(res.get("why") or "")[:200], conf < _CONFIDENT, tid,
            )
            n += 1
    return n


async def apply_correction(conn, txn_id: int, category: str | None, client_id: int | None, set_client: bool) -> None:
    """Dylan fixed a row: mark it reviewed and learn from it."""
    row = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1", txn_id)
    if not row:
        return
    if category:
        await conn.execute("UPDATE transactions SET category = $1, reviewed = true, needs_review = false WHERE id = $2",
                           category, txn_id)
        mk = row["merchant_key"]
        if mk and row["source"] in ("zapier", "csv") and category != "Uncategorized":
            await conn.execute(
                """INSERT INTO finance_rules (merchant_key, category, example) VALUES ($1, $2, $3)
                   ON CONFLICT (merchant_key) DO UPDATE SET category = EXCLUDED.category, example = EXCLUDED.example, updated_at = now()""",
                mk, category, row["description"],
            )
            await conn.execute(
                """UPDATE transactions SET category = $1, needs_review = false, ai_note = 'Your rule'
                   WHERE merchant_key = $2 AND NOT reviewed AND source IN ('zapier', 'csv')""",
                category, mk,
            )
    if set_client:
        await conn.execute("UPDATE transactions SET client_id = $1, reviewed = true, needs_review = false WHERE id = $2",
                           client_id, txn_id)
        cp = row["counterparty"]
        if cp and client_id:
            await conn.execute(
                "INSERT INTO finance_client_links (counterparty, client_id) VALUES ($1, $2) "
                "ON CONFLICT (counterparty) DO UPDATE SET client_id = EXCLUDED.client_id", cp, client_id)
            await conn.execute(
                "UPDATE transactions SET client_id = $1, needs_review = false WHERE counterparty = $2 AND client_id IS NULL",
                client_id, cp)


async def confirm(conn, txn_id: int) -> None:
    row = await conn.fetchrow("SELECT category FROM transactions WHERE id = $1", txn_id)
    if row:
        await apply_correction(conn, txn_id, row["category"], None, False)


# ── Real per-client costs ────────────────────────────────────────────────────

def _month_bounds(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    nxt = (start + timedelta(days=32)).replace(day=1)
    return start, nxt


async def _twilio_month_cost(http: httpx.AsyncClient, sub_sid: str, start: date, end: date) -> float | None:
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if not (sid and tok):
        return None
    r = await http.get(
        f"https://api.twilio.com/2010-04-01/Accounts/{sub_sid}/Usage/Records.json",
        params={"Category": "totalprice", "StartDate": str(start), "EndDate": str(end - timedelta(days=1))},
        auth=(sid, tok),
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Twilio {r.status_code}: {r.text[:200]}")
    recs = r.json().get("usage_records") or []
    return round(sum(abs(float(x.get("price") or 0)) for x in recs), 2)


async def _backfill_retell_costs(conn, http: httpx.AsyncClient, limit: int = 60) -> None:
    key = os.environ.get("RETELL_API_KEY")
    if not key:
        return
    rows = await conn.fetch(
        """SELECT id, retell_call_id FROM client_voice_calls
           WHERE retell_call_id IS NOT NULL AND cost_cents IS NULL AND status IN ('done', 'failed')
             AND created_at > now() - interval '75 days' ORDER BY created_at DESC LIMIT $1""", limit)
    for r in rows:
        try:
            resp = await http.get(f"https://api.retellai.com/v2/get-call/{r['retell_call_id']}",
                                  headers={"Authorization": f"Bearer {key}"})
            if resp.status_code == 404:
                await conn.execute("UPDATE client_voice_calls SET cost_cents = 0 WHERE id = $1", r["id"])
                continue
            if resp.status_code >= 400:
                continue
            cost = (resp.json().get("call_cost") or {}).get("combined_cost")
            if cost is not None:
                await conn.execute("UPDATE client_voice_calls SET cost_cents = $1 WHERE id = $2", float(cost), r["id"])
        except httpx.HTTPError:
            continue


async def post_client_costs() -> None:
    """This month's and last month's real Meta / Twilio / Retell cost per
    client, as one auto row each in that client's Finance ledger."""
    today = datetime.now(ET).date()
    months = [_month_bounds(today), _month_bounds(today.replace(day=1) - timedelta(days=1))]
    pool = await get_pool()
    errors = []
    async with httpx.AsyncClient(timeout=30) as http, pool.acquire() as conn:
        await _backfill_retell_costs(conn, http)
        clients = await conn.fetch(
            """SELECT c.id, m.twilio_subaccount_sid FROM clients c
               LEFT JOIN client_marketing_config m ON m.client_id = c.id
               WHERE NOT c.is_test""")
        for c in clients:
            for start, end in months:
                label = start.strftime("%b %Y")
                last_day = min(end - timedelta(days=1), today)
                meta = await conn.fetchval(
                    "SELECT COALESCE(SUM(spend), 0) FROM ad_campaign_stats WHERE client_id = $1 AND stat_date >= $2 AND stat_date < $3",
                    c["id"], start, end)
                retell = await conn.fetchval(
                    "SELECT COALESCE(SUM(cost_cents), 0) / 100.0 FROM client_voice_calls WHERE client_id = $1 AND created_at >= $2 AND created_at < $3",
                    c["id"], datetime.combine(start, datetime.min.time(), ET), datetime.combine(end, datetime.min.time(), ET))
                twilio = None
                if c["twilio_subaccount_sid"]:
                    try:
                        twilio = await _twilio_month_cost(http, c["twilio_subaccount_sid"], start, end)
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"client {c['id']} Twilio: {e}")
                for kind, amount, desc, cat in (
                    ("meta", meta, f"Meta ad spend ({label}, actual)", "Ad Spend"),
                    ("twilio", twilio, f"Twilio texts + calls ({label}, actual)", "Software & Tools"),
                    ("retell", retell, f"AI voice agent calls ({label}, actual)", "Software & Tools"),
                ):
                    if amount is None:
                        continue
                    amount = round(float(amount), 2)
                    key = f"{kind}:{c['id']}:{start}"
                    if amount <= 0:
                        await conn.execute("DELETE FROM client_transactions WHERE auto_key = $1", key)
                        continue
                    await conn.execute(
                        """INSERT INTO client_transactions (client_id, date, description, amount, is_income, category, notes, auto_key)
                           VALUES ($1, $2, $3, $4, false, $5, 'Real monthly cost (auto-updated daily)', $6)
                           ON CONFLICT (auto_key) DO UPDATE SET amount = EXCLUDED.amount, date = EXCLUDED.date, description = EXCLUDED.description""",
                        c["id"], last_day, desc, -amount, cat, key)
        await conn.execute("UPDATE finance_settings SET costs_synced_at = now(), costs_error = $1 WHERE id = 1",
                           "; ".join(errors)[:500] or None)


# ── Reports ──────────────────────────────────────────────────────────────────

async def profit_by_client(conn, start: date, end: date) -> list[dict]:
    rows = await conn.fetch(
        """
        WITH rev AS (
            SELECT client_id, SUM(amount) AS revenue FROM transactions
             WHERE is_income AND client_id IS NOT NULL AND date >= $1 AND date < $2
               AND category NOT IN ('Transfer', 'Transfers')
             GROUP BY client_id
        ), cost AS (
            SELECT t.client_id,
                   ABS(SUM(t.amount) FILTER (WHERE t.category = 'Ad Spend')) AS ads,
                   ABS(SUM(t.amount) FILTER (WHERE t.category <> 'Ad Spend')) AS other
              FROM client_transactions t
             WHERE NOT t.is_income AND t.date >= $1 AND t.date < $2
             GROUP BY t.client_id
        ), fees AS (
            SELECT client_id, ABS(SUM(amount)) AS fees FROM transactions
             WHERE NOT is_income AND client_id IS NOT NULL AND date >= $1 AND date < $2
             GROUP BY client_id
        )
        SELECT c.id, c.name, c.status, c.ads_on_our_card,
               COALESCE(rev.revenue, 0) AS revenue, COALESCE(cost.ads, 0) AS ads,
               COALESCE(cost.other, 0) AS other, COALESCE(fees.fees, 0) AS fees
          FROM clients c
          LEFT JOIN rev  ON rev.client_id = c.id
          LEFT JOIN cost ON cost.client_id = c.id
          LEFT JOIN fees ON fees.client_id = c.id
         WHERE NOT c.is_test AND (c.status = 'active' OR rev.revenue IS NOT NULL OR cost.client_id IS NOT NULL)
         ORDER BY COALESCE(rev.revenue, 0) DESC, c.name
        """, start, end)
    out = []
    for r in rows:
        ads = float(r["ads"]) if r["ads_on_our_card"] else 0.0
        costs = ads + float(r["other"]) + float(r["fees"])
        rev = float(r["revenue"])
        out.append({
            "client_id": r["id"], "name": r["name"], "status": r["status"], "ads_on_our_card": r["ads_on_our_card"],
            "revenue": round(rev, 2), "ad_spend": round(float(r["ads"]), 2), "tools": round(float(r["other"]), 2),
            "fees": round(float(r["fees"]), 2), "costs": round(costs, 2), "profit": round(rev - costs, 2),
        })
    return out


async def month_report(conn, start: date, end: date) -> dict:
    tot = await conn.fetchrow(
        """SELECT COALESCE(SUM(amount) FILTER (WHERE is_income), 0) AS income,
                  COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income)), 0) AS expenses
             FROM transactions WHERE date >= $1 AND date < $2 AND category NOT IN ('Transfer', 'Transfers')""",
        start, end)
    cats = await conn.fetch(
        """SELECT category, ABS(SUM(amount)) AS total FROM transactions
            WHERE NOT is_income AND date >= $1 AND date < $2 AND category NOT IN ('Transfer', 'Transfers')
            GROUP BY category ORDER BY total DESC""", start, end)
    review = await conn.fetchval("SELECT COUNT(*) FROM transactions WHERE needs_review OR category = 'Uncategorized'")
    return {"income": float(tot["income"]), "expenses": float(tot["expenses"]),
            "categories": [(r["category"], float(r["total"])) for r in cats],
            "clients": await profit_by_client(conn, start, end), "needs_review": review}


async def monthly_summary_todo() -> None:
    today = datetime.now(ET).date()
    start, end = _month_bounds(today.replace(day=1) - timedelta(days=1))
    await run_sync()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rep = await month_report(conn, start, end)
        label = start.strftime("%B %Y")
        net = rep["income"] - rep["expenses"]
        lines = [f"Revenue ${rep['income']:,.2f} · Spent ${rep['expenses']:,.2f} · Profit ${net:,.2f}", "", "Where the money went:"]
        lines += [f"- {c}: ${t:,.2f}" for c, t in rep["categories"][:8]] or ["- nothing recorded"]
        lines += ["", "Profit per client:"]
        lines += [f"- {c['name']}: paid ${c['revenue']:,.2f}, cost ${c['costs']:,.2f}, profit ${c['profit']:,.2f}"
                  for c in rep["clients"] if c["revenue"] or c["costs"]] or ["- no client activity"]
        if rep["needs_review"]:
            lines += ["", f"{rep['needs_review']} transaction(s) still need a look in Finances."]
        text = f"{label} finances: profit ${net:,.0f}"
        if await conn.fetchval("SELECT 1 FROM todos WHERE text = $1", text):
            return
        await conn.execute("INSERT INTO todos (text, description, due_date) VALUES ($1, $2, $3)",
                           text, "\n".join(lines), today)


async def run_sync() -> dict:
    """Hourly: sheet + Stripe, then sort anything still unsorted."""
    out = {}
    for name, fn in (("sheet", sync_sheet), ("stripe", sync_stripe)):
        try:
            out[name] = await fn()
        except Exception as e:  # noqa: BLE001 - recorded on finance_settings
            out[name] = {"error": str(e)[:300]}
    try:
        out["sorted"] = await categorize_pending()
    except Exception as e:  # noqa: BLE001
        out["sorted"] = {"error": str(e)[:300]}
    return out
