"""
SMS Agent — analytics reporter.

Queries sms_conversations.db and prints totals matching the KPI table columns
on the Notion Outreach & Appointment Setting page.

Usage:
  python sms_stats.py
  python sms_stats.py --json   (outputs JSON for EA skill to parse)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sms_conversations.db")

THIRTY_DAYS_AGO = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()


def _query(sql, params=()):
    if not os.path.exists(DB_PATH):
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()


def get_stats():
    all_time = {
        "outbound_sent": len(_query(
            "SELECT 1 FROM conversations"
        )),
        "replies": len(_query(
            "SELECT 1 FROM conversations WHERE last_inbound_at IS NOT NULL"
        )),
        "engaged": len(_query(
            "SELECT 1 FROM conversations WHERE stage NOT IN ('opening', 'primed') AND status != 'closed_dead'"
        )),
        "booked": len(_query(
            "SELECT 1 FROM conversations WHERE status = 'closed_booked'"
        )),
        "dead": len(_query(
            "SELECT 1 FROM conversations WHERE status = 'closed_dead'"
        )),
    }

    last_30 = {
        "outbound_sent": len(_query(
            "SELECT 1 FROM conversations WHERE created_at >= ?",
            (THIRTY_DAYS_AGO,)
        )),
        "replies": len(_query(
            "SELECT 1 FROM conversations WHERE last_inbound_at IS NOT NULL AND created_at >= ?",
            (THIRTY_DAYS_AGO,)
        )),
        "engaged": len(_query(
            "SELECT 1 FROM conversations WHERE stage NOT IN ('opening', 'primed') AND status != 'closed_dead' AND created_at >= ?",
            (THIRTY_DAYS_AGO,)
        )),
        "booked": len(_query(
            "SELECT 1 FROM conversations WHERE status = 'closed_booked' AND created_at >= ?",
            (THIRTY_DAYS_AGO,)
        )),
        "dead": len(_query(
            "SELECT 1 FROM conversations WHERE status = 'closed_dead' AND created_at >= ?",
            (THIRTY_DAYS_AGO,)
        )),
    }

    active = _query(
        "SELECT lead_json, stage, updated_at FROM conversations WHERE status = 'active' ORDER BY updated_at DESC LIMIT 20"
    )
    active_list = []
    for row in active:
        lead = json.loads(row["lead_json"])
        active_list.append({
            "name":       lead.get("owner") or "Unknown",
            "business":   lead.get("business") or "",
            "stage":      row["stage"],
            "last_active": row["updated_at"],
        })

    booked_rows = _query(
        "SELECT lead_json, updated_at FROM conversations WHERE status = 'closed_booked' ORDER BY updated_at DESC LIMIT 10"
    )
    bookings = []
    for row in booked_rows:
        lead = json.loads(row["lead_json"])
        bookings.append({
            "name":     lead.get("owner") or "Unknown",
            "business": lead.get("business") or "",
            "date":     row["updated_at"][:10] if row["updated_at"] else "",
        })

    # Booking rates
    def _rate(booked, total):
        return f"{round(booked / total * 100)}%" if total else "0%"

    all_time["booking_rate"] = _rate(all_time["booked"], all_time["outbound_sent"])
    last_30["booking_rate"]  = _rate(last_30["booked"], last_30["outbound_sent"])

    return {
        "all_time":  all_time,
        "last_30":   last_30,
        "active":    active_list,
        "bookings":  bookings,
    }


def print_stats(stats):
    def _row(label, val):
        return f"  {label:<25} {val}"

    print("\n══════════════════════════════════════")
    print("  SMS AGENT — ALL TIME")
    print("══════════════════════════════════════")
    at = stats["all_time"]
    print(_row("Outbound sent:",     at["outbound_sent"]))
    print(_row("Replies:",           at["replies"]))
    print(_row("Engaged (past CTA):", at["engaged"]))
    print(_row("Booked:",            at["booked"]))
    print(_row("Booking rate:",      at["booking_rate"]))
    print(_row("Closed dead:",       at["dead"]))

    print("\n══════════════════════════════════════")
    print("  SMS AGENT — LAST 30 DAYS")
    print("══════════════════════════════════════")
    l30 = stats["last_30"]
    print(_row("Outbound sent:",     l30["outbound_sent"]))
    print(_row("Replies:",           l30["replies"]))
    print(_row("Engaged:",           l30["engaged"]))
    print(_row("Booked:",            l30["booked"]))
    print(_row("Booking rate:",      l30["booking_rate"]))
    print(_row("Closed dead:",       l30["dead"]))

    if stats["active"]:
        print("\n══════════════════════════════════════")
        print("  ACTIVE CONVERSATIONS")
        print("══════════════════════════════════════")
        for c in stats["active"]:
            print(f"  {c['name']:<20} {c['business']:<25} stage={c['stage']}  last={c['last_active'][:16]}")

    if stats["bookings"]:
        print("\n══════════════════════════════════════")
        print("  RECENT BOOKINGS")
        print("══════════════════════════════════════")
        for b in stats["bookings"]:
            print(f"  {b['date']}  {b['name']:<20} {b['business']}")

    print()


if __name__ == "__main__":
    stats = get_stats()
    if "--json" in sys.argv:
        print(json.dumps(stats, indent=2))
    else:
        print_stats(stats)
