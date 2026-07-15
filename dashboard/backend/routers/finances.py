"""
Finances router — manual ledger.

POST /finances/transactions          — add a manual revenue or expense
DELETE /finances/transactions/{id}   — remove a transaction
PATCH /finances/transactions/{id}    — update category or notes
GET  /finances/summary?days=30       — income / expenses / net / margin
GET  /finances/categories?days=30    — expense breakdown by category + daily trend
GET  /finances/transactions          — paginated transaction list with filters
POST /finances/recurring             — create a recurring rule
GET  /finances/recurring             — list active recurring rules
DELETE /finances/recurring/{id}      — stop a recurring rule
POST /finances/recurring/apply       — generate pending recurring instances
"""

import calendar
from datetime import datetime, timedelta, timezone, date

from fastapi import APIRouter, HTTPException
from db import get_pool

router = APIRouter()

# ── Period helper ─────────────────────────────────────────────────────────────

def _since_date(days: int) -> date:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/finances/summary")
async def summary(days: int = 30):
    since = _since_date(days)
    pool  = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(amount) FILTER (WHERE is_income AND date >= $1), 0) AS income,
                COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income AND date >= $1)), 0) AS expenses
            FROM transactions
            """,
            since,
        )

    income   = float(row["income"])
    expenses = float(row["expenses"])
    net      = income - expenses
    margin   = round(net / income * 100, 1) if income else None

    return {
        "connected": True,
        "income":    round(income, 2),
        "expenses":  round(expenses, 2),
        "net":       round(net, 2),
        "margin":    margin,
    }


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _generate_periods(since: date, today: date, trunc: str) -> list:
    """Every bucket start-date in [since, today], inclusive, at the given
    granularity — so the trend series has one point per period even when a
    period has zero transactions, instead of silently skipping it."""
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
            cur = _advance(cur, "weekly")
    else:
        cur = _month_start(since)
        end = _month_start(today)
        while cur <= end:
            periods.append(cur)
            cur = _advance(cur, "monthly")
    return periods


@router.get("/finances/categories")
async def categories(days: int = 30):
    since = _since_date(days)
    today = datetime.now(timezone.utc).date()
    pool  = await get_pool()

    # Choose aggregation granularity based on time window
    if days <= 30:
        trunc    = "day"
        granularity = "daily"
    elif days <= 90:
        trunc    = "week"
        granularity = "weekly"
    else:
        trunc    = "month"
        granularity = "monthly"

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
        trend_rows = await conn.fetch(
            f"""
            SELECT date_trunc('{trunc}', date)::date AS period,
                   COALESCE(SUM(amount) FILTER (WHERE is_income), 0)          AS income,
                   COALESCE(ABS(SUM(amount) FILTER (WHERE NOT is_income)), 0) AS expenses
            FROM transactions
            WHERE date >= $1
            GROUP BY period
            ORDER BY period
            """,
            since,
        )

    total_expenses = sum(float(r["total"]) for r in cat_rows) or 1

    by_period = {r["period"]: r for r in trend_rows}
    daily = [
        {
            "date":     str(p),
            "income":   round(float(by_period[p]["income"]), 2)   if p in by_period else 0.0,
            "expenses": round(float(by_period[p]["expenses"]), 2) if p in by_period else 0.0,
        }
        for p in _generate_periods(since, today, trunc)
    ]

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


@router.post("/finances/transactions")
async def add_transaction(body: dict):
    date_str    = (body.get("date") or "").strip()
    description = (body.get("description") or "").strip()
    amount_raw  = body.get("amount")
    is_income   = bool(body.get("is_income", False))
    category    = (body.get("category") or "").strip() or ("Revenue" if is_income else "Uncategorized")
    notes       = (body.get("notes") or "").strip() or None

    if not date_str or amount_raw is None:
        raise HTTPException(status_code=400, detail="date and amount required")
    try:
        amount_float = float(amount_raw)
        txn_date     = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid date or amount")
    if amount_float <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    stored_amount = amount_float if is_income else -amount_float

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO transactions (date, description, amount, is_income, category, notes)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, date, description, amount, is_income, category, notes
            """,
            txn_date, description or None, stored_amount, is_income, category, notes,
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


@router.delete("/finances/transactions/{txn_id}")
async def delete_transaction(txn_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM transactions WHERE id=$1", txn_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"ok": True}


# ── Recurring transactions ────────────────────────────────────────────────────

_VALID_FREQUENCIES = {"weekly", "monthly", "yearly"}


def _advance(d: date, frequency: str) -> date:
    if frequency == "weekly":
        return d + timedelta(weeks=1)
    if frequency == "monthly":
        month = d.month + 1
        year  = d.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day   = min(d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    # yearly
    try:
        return date(d.year + 1, d.month, d.day)
    except ValueError:
        return date(d.year + 1, d.month, d.day - 1)


async def _apply_recurring(conn) -> int:
    today = date.today()
    rules = await conn.fetch(
        "SELECT * FROM recurring_transactions WHERE active = true"
    )
    total = 0
    for rule in rules:
        current  = rule["start_date"]
        last     = rule["last_applied"]
        end      = rule["end_date"]
        freq     = rule["frequency"]

        # fast-forward past already-applied dates
        if last is not None:
            while current <= last:
                current = _advance(current, freq)

        new_last = last
        while current <= today and (end is None or current <= end):
            # Idempotency check — skip if already inserted (handles concurrent apply calls)
            exists = await conn.fetchval(
                "SELECT 1 FROM transactions WHERE recurring_id=$1 AND date=$2",
                rule["id"], current,
            )
            if not exists:
                stored = float(rule["amount"]) if rule["is_income"] else -float(rule["amount"])
                await conn.execute(
                    """
                    INSERT INTO transactions (date, description, amount, is_income, category, notes, recurring_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    current, rule["description"], stored,
                    rule["is_income"], rule["category"], rule["notes"], rule["id"],
                )
            new_last = current
            current  = _advance(current, freq)
            total   += 1

        if new_last != last:
            await conn.execute(
                "UPDATE recurring_transactions SET last_applied=$1 WHERE id=$2",
                new_last, rule["id"],
            )

    return total


@router.post("/finances/recurring/apply")
async def apply_recurring():
    pool = await get_pool()
    async with pool.acquire() as conn:
        applied = await _apply_recurring(conn)
    return {"applied": applied}


@router.get("/finances/recurring")
async def list_recurring():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM recurring_transactions WHERE active = true ORDER BY created_at DESC"
        )

    def next_occurrence(row) -> str:
        last = row["last_applied"]
        base = _advance(last, row["frequency"]) if last else row["start_date"]
        return str(base)

    return [
        {
            "id":             r["id"],
            "description":    r["description"],
            "amount":         float(r["amount"]),
            "is_income":      r["is_income"],
            "category":       r["category"],
            "frequency":      r["frequency"],
            "start_date":     str(r["start_date"]),
            "end_date":       str(r["end_date"]) if r["end_date"] else None,
            "last_applied":   str(r["last_applied"]) if r["last_applied"] else None,
            "next_occurrence": next_occurrence(r),
        }
        for r in rows
    ]


@router.post("/finances/recurring")
async def create_recurring(body: dict):
    description    = (body.get("description") or "").strip()
    amount_raw     = body.get("amount")
    is_income      = bool(body.get("is_income", False))
    category       = (body.get("category") or "").strip() or ("Revenue" if is_income else "Uncategorized")
    notes          = (body.get("notes") or "").strip() or None
    frequency      = (body.get("frequency") or "monthly").lower()
    start_date_str = (body.get("start_date") or "").strip()
    end_date_str   = (body.get("end_date") or "").strip() or None

    if frequency not in _VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="frequency must be weekly, monthly, or yearly")
    if not start_date_str or amount_raw is None:
        raise HTTPException(status_code=400, detail="start_date and amount required")
    try:
        amount_float = float(amount_raw)
        start        = date.fromisoformat(start_date_str)
        end          = date.fromisoformat(end_date_str) if end_date_str else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid date or amount")
    if amount_float <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rule = await conn.fetchrow(
            """
            INSERT INTO recurring_transactions
                (description, amount, is_income, category, notes, frequency, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            description or None, amount_float, is_income, category,
            notes, frequency, start, end,
        )
        applied = await _apply_recurring(conn)

    return {"id": rule["id"], "frequency": rule["frequency"], "applied": applied}


@router.delete("/finances/recurring/{rule_id}")
async def delete_recurring(rule_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE recurring_transactions SET active=false WHERE id=$1", rule_id
        )
    return {"ok": True}
