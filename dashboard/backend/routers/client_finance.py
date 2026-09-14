"""
Per-client finance ledger — admin-side tracking of what it costs DigiGrowth
to deliver/run a client's campaign (expenses: ad spend, tools, labor) against
the revenue that client's own business generated from it, so ROAS can be
tracked per client. Same manual-ledger shape as routers/finances.py (the
agency-wide P&L) but scoped to client_transactions instead of transactions,
with an added ROAS figure. Mounted with require_auth like clients.py — this
is agency-internal admin tooling, not shown in the client-facing portal.

GET    /clients/{id}/finance/summary?days=30      — revenue / expenses / ad spend / net / ROAS
GET    /clients/{id}/finance/categories?days=30   — expense breakdown by category + daily trend
GET    /clients/{id}/finance/transactions         — paginated transaction list with filters
POST   /clients/{id}/finance/transactions         — add a manual revenue or expense entry
PATCH  /clients/{id}/finance/transactions/{txn_id} — update category or notes
DELETE /clients/{id}/finance/transactions/{txn_id} — remove an entry
"""

from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, HTTPException
from db import get_pool
from models import ClientTransactionCreate, ClientTransactionUpdate

router = APIRouter()

# The one category that counts as ROAS's denominator — every other expense
# category (tools, labor, etc.) still shows up in the P&L but isn't ad spend.
AD_SPEND_CATEGORY = "Ad Spend"
EXPENSE_CATEGORIES = [AD_SPEND_CATEGORY, "Software & Tools", "Labor & Fulfillment", "Other"]
INCOME_CATEGORY = "Client Revenue"


def _since_date(days: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date()


async def _require_client(conn, client_id: int):
    client = await conn.fetchrow("SELECT id FROM clients WHERE id = $1", client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")


@router.get("/clients/{client_id}/finance/summary")
async def client_finance_summary(client_id: int, days: int = 30):
    since = _since_date(days)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE is_income AND date >= $2), 0) AS revenue,
                COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income AND date >= $2)), 0) AS expenses,
                COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income AND category = $3 AND date >= $2)), 0) AS ad_spend
            FROM client_transactions
            WHERE client_id = $1
            """,
            client_id, since, AD_SPEND_CATEGORY,
        )

    revenue  = float(row["revenue"])
    expenses = float(row["expenses"])
    ad_spend = float(row["ad_spend"])
    net      = revenue - expenses
    roas     = round(revenue / ad_spend, 2) if ad_spend else None

    return {
        "revenue":  round(revenue, 2),
        "expenses": round(expenses, 2),
        "ad_spend": round(ad_spend, 2),
        "net":      round(net, 2),
        "roas":     roas,
    }


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _advance(d: date, unit: str) -> date:
    if unit == "week":
        return d + timedelta(weeks=1)
    month = d.month + 1
    year  = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return d.replace(year=year, month=month, day=1)


def _generate_periods(since: date, today: date, trunc: str) -> list:
    periods = []
    if trunc == "day":
        cur = since
        while cur <= today:
            periods.append(cur)
            cur += timedelta(days=1)
    elif trunc == "week":
        cur = _week_start(since)
        end = _week_start(today)
        while cur <= end:
            periods.append(cur)
            cur = _advance(cur, "week")
    else:
        cur = _month_start(since)
        end = _month_start(today)
        while cur <= end:
            periods.append(cur)
            cur = _advance(cur, "month")
    return periods


@router.get("/clients/{client_id}/finance/categories")
async def client_finance_categories(client_id: int, days: int = 30):
    since = _since_date(days)
    today = datetime.now(timezone.utc).date()
    pool  = await get_pool()

    if days <= 30:
        trunc, granularity = "day", "daily"
    elif days <= 90:
        trunc, granularity = "week", "weekly"
    else:
        trunc, granularity = "month", "monthly"

    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        cat_rows = await conn.fetch(
            """
            SELECT category, ABS(SUM(amount)) AS total
            FROM client_transactions
            WHERE client_id = $1 AND NOT is_income AND date >= $2
            GROUP BY category
            ORDER BY total DESC
            """,
            client_id, since,
        )
        trend_rows = await conn.fetch(
            f"""
            SELECT date_trunc('{trunc}', date)::date AS period,
                   COALESCE(SUM(amount) FILTER (WHERE is_income), 0)          AS revenue,
                   COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income)), 0) AS expenses
            FROM client_transactions
            WHERE client_id = $1 AND date >= $2
            GROUP BY period
            ORDER BY period
            """,
            client_id, since,
        )

    total_expenses = sum(float(r["total"]) for r in cat_rows) or 1
    by_period = {r["period"]: r for r in trend_rows}
    cum_revenue = 0.0
    cum_expenses = 0.0
    daily = []
    for p in _generate_periods(since, today, trunc):
        cum_revenue  += float(by_period[p]["revenue"])  if p in by_period else 0.0
        cum_expenses += float(by_period[p]["expenses"]) if p in by_period else 0.0
        daily.append({"date": str(p), "revenue": round(cum_revenue, 2), "expenses": round(cum_expenses, 2)})

    return {
        "expense_breakdown": [
            {
                "category": r["category"],
                "total":    round(float(r["total"]), 2),
                "pct":      round(float(r["total"]) / total_expenses * 100, 1),
            }
            for r in cat_rows
        ],
        "granularity": granularity,
        "daily": daily,
    }


@router.get("/clients/{client_id}/finance/transactions")
async def client_finance_transactions(client_id: int, days: int = 30, limit: int = 50, offset: int = 0, type: str = "all"):
    since = _since_date(days)
    pool  = await get_pool()

    filters = ["client_id = $1", "date >= $2"]
    params  = [client_id, since]
    if type == "income":
        filters.append("is_income = true")
    elif type == "expense":
        filters.append("is_income = false")
    where = "WHERE " + " AND ".join(filters)

    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        total = await conn.fetchval(f"SELECT COUNT(*) FROM client_transactions {where}", *params)
        rows = await conn.fetch(
            f"""
            SELECT id, date, description, amount, is_income, category, notes
            FROM client_transactions {where}
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


@router.post("/clients/{client_id}/finance/transactions")
async def add_client_transaction(client_id: int, body: ClientTransactionCreate):
    description = (body.description or "").strip() or None
    is_income   = body.is_income
    category    = (body.category or "").strip() or (INCOME_CATEGORY if is_income else "Other")
    notes       = (body.notes or "").strip() or None

    try:
        amount_float = float(body.amount)
        txn_date     = date.fromisoformat(body.date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid date or amount")
    if amount_float <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    stored_amount = amount_float if is_income else -amount_float

    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        row = await conn.fetchrow(
            """
            INSERT INTO client_transactions (client_id, date, description, amount, is_income, category, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, date, description, amount, is_income, category, notes
            """,
            client_id, txn_date, description, stored_amount, is_income, category, notes,
        )

    return {
        "id":          row["id"],
        "date":        str(row["date"]),
        "description": row["description"],
        "amount":      float(row["amount"]),
        "is_income":   row["is_income"],
        "category":    row["category"],
        "notes":       row["notes"],
    }


@router.patch("/clients/{client_id}/finance/transactions/{txn_id}")
async def update_client_transaction(client_id: int, txn_id: int, body: ClientTransactionUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        if "category" in fields:
            fields["category"] = (fields["category"] or "Other").strip() or "Other"
        if "notes" in fields:
            fields["notes"] = (fields["notes"] or "").strip() or None
        set_clauses = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(fields))
        row = await conn.fetchrow(
            f"UPDATE client_transactions SET {set_clauses} WHERE id = $1 AND client_id = $2 RETURNING *",
            txn_id, client_id, *fields.values(),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return dict(row)


@router.delete("/clients/{client_id}/finance/transactions/{txn_id}")
async def delete_client_transaction(client_id: int, txn_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _require_client(conn, client_id)
        row = await conn.fetchrow(
            "DELETE FROM client_transactions WHERE id = $1 AND client_id = $2 RETURNING id",
            txn_id, client_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"ok": True}
