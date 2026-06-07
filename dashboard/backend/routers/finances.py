"""
Finances router — Plaid-powered Novo transaction sync.

POST /finances/plaid/link-token   — create Plaid link_token for frontend
POST /finances/plaid/exchange     — exchange public_token for access_token
POST /finances/plaid/sync         — pull new transactions from Plaid (incremental)
GET  /finances/summary?days=30    — income / expenses / net / margin
GET  /finances/categories?days=30 — expense breakdown by category + daily trend
GET  /finances/transactions       — paginated transaction list with filters
PATCH /finances/transactions/{id} — update category or notes
"""

import os
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, HTTPException
from db import get_pool

router = APIRouter()

# ── Plaid client (lazy-initialised so missing env vars don't crash at import) ──

def _plaid_client():
    try:
        from plaid.api import plaid_api
        from plaid.configuration import Configuration
        from plaid.api_client import ApiClient

        env_map = {
            "sandbox":     "https://sandbox.plaid.com",
            "development": "https://development.plaid.com",
            "production":  "https://production.plaid.com",
        }
        host = env_map.get(os.environ.get("PLAID_ENV", "development"), env_map["development"])
        config = Configuration(
            host=host,
            api_key={
                "clientId": os.environ["PLAID_CLIENT_ID"],
                "secret":   os.environ["PLAID_SECRET"],
            },
        )
        return plaid_api.PlaidApi(ApiClient(config))
    except KeyError as e:
        raise HTTPException(status_code=503, detail=f"Plaid not configured: {e}")


# ── Auto-categorization ───────────────────────────────────────────────────────

_CATEGORY_RULES = [
    (["aws", "railway.app", "vercel", "supabase", "heroku", "digitalocean", "linode"], "Hosting & Infrastructure"),
    (["twilio", "bandwidth", "vonage"], "Communications"),
    (["anthropic", "openai", "claude", "gpt"], "AI Tools"),
    (["google ads", "meta ads", "facebook ads", "instagram ads"], "Advertising"),
    (["notion", "slack", "zoom", "loom", "figma", "airtable"], "SaaS Tools"),
    (["stripe fee", "paypal fee", "square fee"], "Payment Processing"),
]

_INCOME_KEYWORDS = ["client", "payment", "invoice", "retainer", "deposit", "zelle", "ach credit", "wire credit"]


def _categorize(description: str, amount: float) -> tuple[str, bool]:
    """Return (category, is_income) for a transaction."""
    desc = (description or "").lower()

    # Plaid: positive amount = money in (income), negative = money out (expense)
    is_income = amount > 0

    # Override is_income if description screams income
    if any(kw in desc for kw in _INCOME_KEYWORDS):
        is_income = True

    if is_income:
        return "Revenue", True

    for keywords, category in _CATEGORY_RULES:
        if any(kw in desc for kw in keywords):
            return category, False

    return "Miscellaneous", False


# ── Sync helper ───────────────────────────────────────────────────────────────

def _txn_date(d) -> date:
    """Coerce Plaid date field to Python date."""
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d))


async def _do_sync(conn, access_token: str, cursor) -> tuple[int, int, int, str]:
    """Pull transactions from Plaid using /transactions/sync. Returns (added, modified, removed, new_cursor)."""
    from plaid.model.transactions_sync_request import TransactionsSyncRequest

    client   = _plaid_client()
    added    = 0
    modified = 0
    removed  = 0
    has_more = True

    while has_more:
        kwargs = {"access_token": access_token}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.transactions_sync(TransactionsSyncRequest(**kwargs))

        for txn in resp.added or []:
            # Plaid: positive amount = debit (money out). We flip: negative stored = expense.
            raw_amount    = float(txn.amount)
            stored_amount = -raw_amount
            name          = getattr(txn, "name", None) or getattr(txn, "merchant_name", None) or ""
            category, is_income = _categorize(name, stored_amount)
            await conn.execute(
                """
                INSERT INTO transactions (plaid_transaction_id, date, description, amount, is_income, category)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (plaid_transaction_id) DO NOTHING
                """,
                txn.transaction_id,
                _txn_date(txn.date),
                name,
                stored_amount,
                is_income,
                category,
            )
            added += 1

        for txn in resp.modified or []:
            raw_amount    = float(txn.amount)
            stored_amount = -raw_amount
            name          = getattr(txn, "name", None) or getattr(txn, "merchant_name", None) or ""
            category, is_income = _categorize(name, stored_amount)
            await conn.execute(
                """
                UPDATE transactions
                SET date=$2, description=$3, amount=$4, is_income=$5, category=$6
                WHERE plaid_transaction_id=$1
                """,
                txn.transaction_id,
                _txn_date(txn.date),
                name,
                stored_amount,
                is_income,
                category,
            )
            modified += 1

        for txn in resp.removed or []:
            await conn.execute(
                "DELETE FROM transactions WHERE plaid_transaction_id=$1",
                txn.transaction_id,
            )
            removed += 1

        cursor   = resp.next_cursor
        has_more = resp.has_more

    return added, modified, removed, cursor


# ── Period helper ─────────────────────────────────────────────────────────────

def _since_date(days: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/finances/plaid/link-token")
async def create_link_token():
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products
    from plaid.model.country_code import CountryCode

    client = _plaid_client()
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id="dylan"),
        client_name="DigiGrowth OS",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    resp = client.link_token_create(req)
    return {"link_token": resp.link_token}


@router.post("/finances/plaid/exchange")
async def exchange_token(body: dict):
    public_token     = body.get("public_token", "")
    institution_name = body.get("institution_name", "Novo")

    if not public_token:
        raise HTTPException(status_code=400, detail="public_token required")

    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    client = _plaid_client()
    resp   = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    access_token = resp.access_token
    item_id      = resp.item_id

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Save token first — connection succeeds even if initial sync fails
        await conn.execute(
            """
            INSERT INTO plaid_config (access_token, item_id, institution_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (item_id) DO UPDATE
              SET access_token=$1, institution_name=$3
            """,
            access_token, item_id, institution_name,
        )
        # Initial sync — wrap in try/except so token save isn't rolled back on sync error
        added = 0
        try:
            added, _mod, _rem, cursor = await _do_sync(conn, access_token, None)
            await conn.execute(
                "UPDATE plaid_config SET cursor=$1, last_synced_at=now() WHERE item_id=$2",
                cursor, item_id,
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return {"ok": True, "added": 0, "sync_error": str(exc)}

    return {"ok": True, "added": added}


@router.post("/finances/plaid/sync")
async def sync_transactions():
    pool = await get_pool()
    async with pool.acquire() as conn:
        cfg = await conn.fetchrow("SELECT * FROM plaid_config ORDER BY id LIMIT 1")
        if not cfg:
            raise HTTPException(status_code=404, detail="No Plaid account connected")

        added, modified, removed, cursor = await _do_sync(
            conn, cfg["access_token"], cfg["cursor"]
        )
        await conn.execute(
            "UPDATE plaid_config SET cursor=$1, last_synced_at=now() WHERE id=$2",
            cursor, cfg["id"],
        )

    return {"added": added, "modified": modified, "removed": removed}


@router.get("/finances/summary")
async def summary(days: int = 30):
    since = _since_date(days)
    pool  = await get_pool()

    async with pool.acquire() as conn:
        cfg = await conn.fetchrow("SELECT institution_name, last_synced_at FROM plaid_config ORDER BY id LIMIT 1")
        if not cfg:
            return {"connected": False, "income": 0, "expenses": 0, "net": 0, "margin": None,
                    "institution_name": None, "last_synced_at": None}

        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE is_income AND date >= $1), 0) AS income,
                COALESCE(ABS(SUM(amount)) FILTER (WHERE NOT is_income AND date >= $1), 0) AS expenses
            FROM transactions
            """,
            since,
        )

    income   = float(row["income"])
    expenses = float(row["expenses"])
    net      = income - expenses
    margin   = round(net / income * 100, 1) if income else None

    return {
        "connected":        True,
        "institution_name": cfg["institution_name"],
        "last_synced_at":   cfg["last_synced_at"].isoformat() if cfg["last_synced_at"] else None,
        "income":           round(income, 2),
        "expenses":         round(expenses, 2),
        "net":              round(net, 2),
        "margin":           margin,
    }


@router.get("/finances/categories")
async def categories(days: int = 30):
    since = _since_date(days)
    pool  = await get_pool()

    async with pool.acquire() as conn:
        cat_rows = await conn.fetch(
            """
            SELECT category,
                   ABS(SUM(amount)) AS total
            FROM transactions
            WHERE NOT is_income AND date >= $1
            GROUP BY category
            ORDER BY total DESC
            """,
            since,
        )
        daily_rows = await conn.fetch(
            """
            SELECT date,
                   COALESCE(SUM(amount) FILTER (WHERE is_income), 0)          AS income,
                   COALESCE(ABS(SUM(amount)) FILTER (WHERE NOT is_income), 0) AS expenses
            FROM transactions
            WHERE date >= $1
            GROUP BY date
            ORDER BY date
            """,
            since,
        )

    total_expenses = sum(float(r["total"]) for r in cat_rows) or 1

    return {
        "expense_breakdown": [
            {
                "category": r["category"],
                "total":    round(float(r["total"]), 2),
                "pct":      round(float(r["total"]) / total_expenses * 100, 1),
            }
            for r in cat_rows
        ],
        "daily": [
            {
                "date":     str(r["date"]),
                "income":   round(float(r["income"]), 2),
                "expenses": round(float(r["expenses"]), 2),
            }
            for r in daily_rows
        ],
    }


@router.get("/finances/transactions")
async def transactions(
    days: int = 30,
    limit: int = 50,
    offset: int = 0,
    type: str = "all",
):
    since = _since_date(days)
    pool  = await get_pool()

    filters = ["date >= $1"]
    params  = [since]

    if type == "income":
        filters.append("is_income = true")
    elif type == "expense":
        filters.append("is_income = false")

    where = "WHERE " + " AND ".join(filters)

    async with pool.acquire() as conn:
        total = await conn.fetchval(f"SELECT COUNT(*) FROM transactions {where}", *params)
        rows  = await conn.fetch(
            f"""
            SELECT id, date, description, amount, is_income, category, notes
            FROM transactions {where}
            ORDER BY date DESC, id DESC
            LIMIT ${len(params)+1} OFFSET ${len(params)+2}
            """,
            *params, limit, offset,
        )

    return {
        "total": total,
        "transactions": [
            {
                "id":          r["id"],
                "date":        str(r["date"]),
                "description": r["description"],
                "amount":      float(r["amount"]),
                "is_income":   r["is_income"],
                "category":    r["category"],
                "notes":       r["notes"],
            }
            for r in rows
        ],
    }


@router.patch("/finances/transactions/{txn_id}")
async def update_transaction(txn_id: int, body: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if "category" in body:
            await conn.execute(
                "UPDATE transactions SET category=$1 WHERE id=$2",
                (body["category"] or "Miscellaneous").strip(), txn_id,
            )
        if "notes" in body:
            await conn.execute(
                "UPDATE transactions SET notes=$1 WHERE id=$2",
                (body["notes"] or "").strip() or None, txn_id,
            )
    return {"ok": True}
