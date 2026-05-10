"""
Parallel Dialer — main entry point

Usage:
  python run.py              Start a dialing session
  python run.py status       Show session stats
  python run.py retry        Re-dial leads with < 3 attempts and no disposition
  python run.py handoff      Trigger SMS handoff for all 3-strike leads
  python run.py test         Place a single test call to Dylan's phone

Setup (first time):
  1. cp .env.example .env and fill in Twilio + GHL keys
  2. Fill in config.json (phone numbers, sheet ID, webhook URL)
  3. Copy credentials.json from lead-qualifier/ (same Google service account)
  4. pip install -r requirements.txt
  5. Start ngrok: ngrok http 5000
  6. Set webhook_base_url in config.json to your ngrok URL
  7. python run.py
"""

import json
import os
import sys
import time
import uuid
import threading
from datetime import datetime

from dotenv import load_dotenv

import leads as leads_mod
import dialer as dialer_mod
import ghl as ghl_mod
import webhook

load_dotenv()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_FILE) as f:
    config = json.load(f)


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _banner(text):
    print(f"\n{'─' * 50}")
    print(f"  {text}")
    print(f"{'─' * 50}")


# ════════════════════════════════════════════════════════════════════════════
#  FLUSH PENDING DISPOSITIONS TO SHEETS
# ════════════════════════════════════════════════════════════════════════════

def flush_dispositions(ws, headers):
    """Write any pending dispositions from state.json back to Google Sheets."""
    state = leads_mod.load_state()
    flushed = 0
    for phone, data in state["leads"].items():
        if not data.get("pending_write"):
            continue
        disposition = data.get("disposition", "")
        attempts    = data.get("attempts", 0)
        row_index   = data.get("row_index")
        if row_index:
            leads_mod.update_disposition(ws, headers, row_index, disposition, attempts)
            state["leads"][phone]["pending_write"] = False
            flushed += 1
    if flushed:
        leads_mod.save_state(state)
        print(f"  ✅ Flushed {flushed} disposition(s) to sheet")


# ════════════════════════════════════════════════════════════════════════════
#  SMS HANDOFF — leads with 3 strikes
# ════════════════════════════════════════════════════════════════════════════

def run_handoffs(ws=None, headers=None):
    """Trigger GHL SMS handoff for all leads that exhausted their call attempts."""
    max_attempts = config.get("max_call_attempts", 3)
    state        = leads_mod.load_state()
    handed_off   = 0

    if ws is None or headers is None:
        _, ws, headers = leads_mod.load_leads(config)

    for phone, data in state["leads"].items():
        if leads_mod.needs_handoff(state, phone, max_attempts):
            lead = {"phone": phone, **data}
            ghl_mod.trigger_sms_handoff(config, lead)
            state["leads"][phone]["handed_off"]    = True
            state["leads"][phone]["disposition"]   = "SMS Handoff"
            state["leads"][phone]["pending_write"] = True
            handed_off += 1

    if handed_off:
        leads_mod.save_state(state)
        flush_dispositions(ws, headers)
        print(f"  📱 {handed_off} lead(s) handed off to SMS agent")
    else:
        print("  ✅ No leads pending handoff")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN DIALING SESSION
# ════════════════════════════════════════════════════════════════════════════

def run_session():
    _banner(f"Parallel Dialer — {_now()}")

    # Load leads
    print("📋 Loading leads from Google Sheets...")
    eligible, ws, headers = leads_mod.load_leads(config)

    if not eligible:
        print("✅ No eligible leads to dial. Run 'python run.py status' for details.")
        return

    print(f"📊 {len(eligible)} leads eligible for dialing")

    # Init state for each lead
    state = leads_mod.load_state()
    for lead in eligible:
        leads_mod.init_lead_state(state, lead)
    leads_mod.save_state(state)

    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    print(f"🆔 Session: {session_id}")

    # Start webhook server in background thread
    webhook.init_session(config, session_id)
    webhook.set_total_leads(len(eligible))
    server_thread = threading.Thread(
        target=webhook.start_server,
        args=(config,),
        daemon=True
    )
    server_thread.start()
    time.sleep(1)  # give Flask a moment to start

    port = config.get("webhook_port", 5000)
    print(f"\n🌐 Open your browser: http://localhost:{port}/agent")
    print("   Click 'Connect' to join the session through your PC\n")

    # Wait for browser to connect (up to 2 minutes)
    print("   Waiting for you to connect...")
    for _ in range(120):
        if webhook._session.get("dylan_sid"):
            break
        time.sleep(1)
    else:
        print("❌ You didn't connect in time. Run again when ready.")
        return

    print(f"✅ Connected — starting to dial {len(eligible)} leads")
    print("   Press Ctrl+C to stop\n")

    max_lines  = config.get("max_parallel_lines", 10)
    call_delay = 2  # seconds between batches

    try:
        i = 0
        while i < len(eligible):
            # Flush any dispositions written by webhook between batches
            flush_dispositions(ws, headers)

            # Handle any new 3-strike leads
            run_handoffs(ws, headers)

            batch = eligible[i:i + max_lines]
            print(f"\n📞 Batch {i // max_lines + 1}: dialing {len(batch)} lead(s)...")

            # Dial batch — webhook handles bridging + classification
            sids = dialer_mod.dial_batch(config, batch, session_id)
            webhook.register_call_sids(sids)

            # Wait for this batch to settle before moving on
            # (classification comes back async via webhook)
            time.sleep(call_delay + config.get("call_timeout_seconds", 30))

            i += max_lines

    except KeyboardInterrupt:
        print("\n⏸️  Session stopped by user")

    finally:
        print("\n🔄 Finalizing session...")
        time.sleep(3)  # let any in-flight webhooks finish
        flush_dispositions(ws, headers)
        run_handoffs(ws, headers)
        webhook.close_session()
        _print_stats()


# ════════════════════════════════════════════════════════════════════════════
#  STATUS
# ════════════════════════════════════════════════════════════════════════════

def _print_stats():
    state = leads_mod.load_state()
    leads = state.get("leads", {})

    total       = len(leads)
    attempted   = sum(1 for v in leads.values() if v.get("attempts", 0) > 0)
    booked      = sum(1 for v in leads.values() if v.get("disposition") == "Appointment Booked")
    follow_up   = sum(1 for v in leads.values() if v.get("disposition") == "Follow Up")
    not_int     = sum(1 for v in leads.values() if v.get("disposition") == "Not Interested")
    send_info   = sum(1 for v in leads.values() if v.get("disposition") == "Send Info")
    no_answer   = sum(1 for v in leads.values() if v.get("disposition") == "No Answer")
    handed_off  = sum(1 for v in leads.values() if v.get("handed_off"))
    undialed    = sum(1 for v in leads.values() if v.get("attempts", 0) == 0)

    _banner("Session Stats")
    print(f"  Total leads tracked : {total}")
    print(f"  Attempted           : {attempted}")
    print(f"  Undialed            : {undialed}")
    print()
    print(f"  Appointment Booked  : {booked}")
    print(f"  Follow Up           : {follow_up}")
    print(f"  Send Info           : {send_info}")
    print(f"  Not Interested      : {not_int}")
    print(f"  No Answer           : {no_answer}")
    print(f"  SMS Handoff         : {handed_off}")


# ════════════════════════════════════════════════════════════════════════════
#  TEST CALL
# ════════════════════════════════════════════════════════════════════════════

def run_test():
    """Call Dylan's phone to verify Twilio credentials and webhook are working."""
    _banner("Test Call")
    session_id = "test-" + str(uuid.uuid4())[:4]
    webhook.init_session(config, session_id)

    server_thread = threading.Thread(
        target=webhook.start_server,
        args=(config,),
        daemon=True
    )
    server_thread.start()
    time.sleep(1)

    sid = dialer_mod.dial_dylan(config, session_id)
    if sid:
        print(f"✅ Test call placed — SID: {sid}")
        print("   Answer your phone. You should hear hold music.")
        print("   If you hear hold music, Twilio is configured correctly.")
    else:
        print("❌ Test call failed — check your Twilio credentials and phone numbers in config.json")

    input("\nPress Enter to stop the server...")


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

    if cmd == "status":
        _print_stats()
    elif cmd == "retry":
        print("📋 Loading leads for retry...")
        eligible, ws, headers = leads_mod.load_leads(config)
        print(f"  {len(eligible)} leads eligible for retry")
        run_session()
    elif cmd == "handoff":
        print("📱 Running SMS handoffs...")
        run_handoffs()
    elif cmd == "test":
        run_test()
    else:
        run_session()
