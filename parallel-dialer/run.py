"""
Parallel Dialer — main entry point

Usage:
  python run.py              Start a dialing session (loads leads from DigiGrowth OS CRM)
  python run.py test         Place a single test call to verify Twilio + webhook

Setup (first time):
  1. Secrets (Twilio + Anthropic keys) live in the shared "digigrowth" Doppler vault
     (config prd_dialer) — run via `doppler run -- python run.py`
  2. Fill in config.json (phone numbers, os_api_url, calendly_url, webhook URL)
  3. pip install -r requirements.txt
  4. Start ngrok: ngrok http 5000
  5. Set webhook_base_url in config.json to your ngrok URL
  6. doppler run -- python run.py test  — verify Twilio is wired up
  7. doppler run -- python run.py       — start dialing
"""

import json
import os
import sys
import time
import uuid
import threading
from datetime import datetime

from dotenv import load_dotenv

import dialer as dialer_mod
import webhook
import leads as leads_mod  # _norm only

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


def _os_get(path, params=None):
    """GET against the DigiGrowth OS dashboard API."""
    os_url = config.get("os_api_url", "").rstrip("/")
    if not os_url:
        return None
    try:
        import requests
        resp = requests.get(
            f"{os_url}{path}",
            params=params,
            auth=("dialer", os.environ.get("OS_API_PASSWORD", "")),
            timeout=10,
        )
        return resp.json() if resp.ok else None
    except Exception as e:
        print(f"  ⚠️  OS API get failed ({path}): {e}")
        return None


def _git_pull():
    import subprocess
    result = subprocess.run(["git", "pull"], capture_output=True, text=True, cwd=BASE_DIR + "/..")
    if result.returncode == 0:
        print(f"  🔄 Git pull: {result.stdout.strip() or 'already up to date'}")
    else:
        print(f"  ⚠️  Git pull failed: {result.stderr.strip()}")


def _git_push(message="Auto-sync session data"):
    import subprocess
    root = BASE_DIR + "/.."
    subprocess.run(["git", "add", "-A"], cwd=root)
    result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=root)
    if "nothing to commit" in result.stdout:
        print("  ✅ Git push: nothing new to commit")
        return
    push = subprocess.run(["git", "push"], capture_output=True, text=True, cwd=root)
    if push.returncode == 0:
        print("  🚀 Git push: session data synced to GitHub")
    else:
        print(f"  ⚠️  Git push failed: {push.stderr.strip()}")


# ════════════════════════════════════════════════════════════════════════════
#  TWIML APP AUTO-CONFIGURE
# ════════════════════════════════════════════════════════════════════════════

def _start_tunnel():
    """
    Start the ngrok tunnel automatically so the user only needs one terminal.
    Uses the static domain from webhook_base_url in config.json.
    Requires NGROK_AUTH_TOKEN (free ngrok account) — set in Doppler.
    """
    from pyngrok import ngrok, conf as ngrok_conf

    auth_token = os.environ.get("NGROK_AUTH_TOKEN", "")
    if auth_token:
        ngrok_conf.get_default().auth_token = auth_token

    base_url = config.get("webhook_base_url", "").rstrip("/")
    port     = config.get("webhook_port", 5000)

    # Extract static domain if the base URL is an ngrok domain
    domain = None
    if "ngrok" in base_url or "ngrok-free" in base_url:
        from urllib.parse import urlparse
        domain = urlparse(base_url).netloc

    # Point pyngrok at the ngrok config where the auth token is stored
    ngrok_cfg = os.path.expanduser("~/Library/Application Support/ngrok/ngrok.yml")
    if os.path.exists(ngrok_cfg):
        ngrok_conf.get_default().config_path = ngrok_cfg

    try:
        kwargs = {"domain": domain} if domain else {}
        tunnel = ngrok.connect(port, **kwargs)
        public_url = tunnel.public_url.replace("http://", "https://")
        print(f"  ✅ Tunnel started → {public_url}")
        return public_url
    except Exception as e:
        print(f"  ⚠️  Could not auto-start ngrok: {e}")
        print(f"     Or start ngrok manually: ngrok http --domain={domain or ''} {port}")
        sys.exit(1)


def _update_twiml_app():
    """
    Auto-point the TwiML App Voice URL at this server's /voice/agent-join.
    Called at session start so ngrok URL changes never require manual Twilio
    Console updates.
    """
    from twilio.rest import Client as TwilioClient

    app_sid   = os.environ.get("TWILIO_TWIML_APP_SID", "")
    base_url  = config.get("webhook_base_url", "").rstrip("/")
    voice_url = f"{base_url}/voice/agent-join"

    if not app_sid:
        print(f"  ⚠️  TWILIO_TWIML_APP_SID not set")
        print(f"     Create a TwiML App in Twilio Console and set its Voice URL to:")
        print(f"     {voice_url}")
        return

    try:
        client = TwilioClient(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"],
        )
        client.applications(app_sid).update(
            voice_url=voice_url,
            voice_method="POST",
        )
        print(f"  ✅ TwiML App Voice URL → {voice_url}")
    except Exception as e:
        print(f"  ⚠️  Could not auto-update TwiML App ({e})")
        print(f"     Set Voice URL manually in Twilio Console: {voice_url}")


# ════════════════════════════════════════════════════════════════════════════
#  MAIN DIALING SESSION
# ════════════════════════════════════════════════════════════════════════════

def run_session():
    _banner(f"Parallel Dialer — {_now()}")

    _git_pull()
    _start_tunnel()
    _update_twiml_app()

    # Load leads from DigiGrowth OS CRM
    print("📋 Loading leads from CRM...")
    result   = _os_get("/api/dialer/leads", params={"limit": 500})
    eligible = result.get("leads", []) if result else []

    if not eligible:
        print("✅ No eligible leads in CRM. Add contacts or wait for the 4-hour cooldown to expire.")
        return

    print(f"📊 {len(eligible)} leads eligible for dialing")

    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    print(f"🆔 Session: {session_id}")

    # Start webhook server in background thread
    webhook.init_session(config, session_id)
    webhook.set_total_leads(len(eligible))
    webhook.set_eligible_leads(eligible)
    server_thread = threading.Thread(
        target=webhook.start_server,
        args=(config,),
        daemon=True
    )
    server_thread.start()
    time.sleep(1)

    port        = config.get("webhook_port", 5000)
    agent_url   = f"http://localhost:{port}/agent"
    print(f"\n🌐 Opening dialer UI: {agent_url}")
    import webbrowser
    webbrowser.open(agent_url)

    # Wait for browser to connect (up to 2 minutes)
    print("   Waiting for you to connect in the browser...")
    for _ in range(120):
        if webhook._session.get("dylan_sid"):
            break
        time.sleep(1)
    else:
        print("❌ You didn't connect in time. Run again when ready.")
        return

    print(f"✅ Connected — starting to dial {len(eligible)} leads")
    print("   Press Ctrl+C to stop\n")

    max_lines    = config.get("max_parallel_lines", 5)
    ring_timeout = config.get("call_timeout_seconds", 30)

    def _wait_for_batch():
        """
        Wait until it's safe to dial the next batch:
        - Always wait for any live call to end and be classified.
        - If the batch had NO answer: also wait the full ring_timeout so unanswered
          leads get their 30 s before being counted / retried.
        - If the batch HAD an answer: overflow calls were canceled immediately, so
          there's no reason to hold after classification is done.
        """
        deadline = time.time() + ring_timeout
        while True:
            with webhook._session["lock"]:
                bridged      = webhook._session.get("bridged")
                show_cls     = webhook._session.get("show_classification")
                had_answer   = webhook._session.get("batch_had_answer", False)
                end_req      = webhook._session.get("end_requested", False)
            if end_req:
                break
            if bridged or show_cls:
                time.sleep(0.5)
                continue
            if had_answer:
                break
            if time.time() >= deadline:
                break
            time.sleep(0.5)

    try:
        i         = 0
        batch_num = 0
        while i < len(eligible):
            # Respect live lines setting from browser dropdown
            with webhook._session["lock"]:
                if webhook._session.get("end_requested"):
                    print("\n⏹️  Session ended from browser")
                    break
                current_max = webhook._session.get("max_lines", max_lines)

            batch      = eligible[i:i + current_max]
            batch_num += 1
            print(f"\n📞 Batch {batch_num}: dialing {len(batch)} lead(s) ({current_max}-line mode)...")

            batch_start = time.time()
            webhook.register_batch_start([l["phone"] for l in batch], batch_start)
            sids = dialer_mod.dial_batch(config, batch, session_id)
            webhook.register_call_sids(sids)

            i += len(batch)
            _wait_for_batch()

            # If this batch had an answered call, give Twilio 3 s to deliver
            # the cancel callbacks for overflow leads before we check retry_phones.
            # Without this, register_batch_start can increment dial_count to 2
            # before the first cancel callback fires, making it count prematurely.
            if webhook._session.get("batch_had_answer"):
                time.sleep(3)

            # Re-dial leads with <30s ring time (max 2 dials total per lead).
            # Fill remaining slots up to max_lines with new leads — redials go first.
            retry_phones = webhook.get_and_clear_retry()
            if retry_phones:
                retry_leads = [l for l in batch if leads_mod._norm(l["phone"]) in retry_phones]
                if retry_leads:
                    slots       = max_lines - len(retry_leads)
                    fill_leads  = eligible[i:i + slots] if slots > 0 else []
                    retry_batch = retry_leads + fill_leads
                    new_count   = len(fill_leads)

                    print(f"  🔄 Re-dialing {len(retry_leads)} + {new_count} new — {len(retry_batch)} total")
                    retry_start = time.time()
                    webhook.register_batch_start([l["phone"] for l in retry_batch], retry_start)
                    retry_sids  = dialer_mod.dial_batch(config, retry_batch, session_id)
                    webhook.register_call_sids(retry_sids)

                    i += new_count
                    _wait_for_batch()
                    webhook.get_and_clear_retry()  # discard; fill leads re-enter naturally

    except KeyboardInterrupt:
        print("\n⏸️  Session stopped by user")

    finally:
        print("\n🔄 Finalizing session...")
        time.sleep(3)  # let any in-flight webhook callbacks complete
        _print_stats()
        webhook.close_session()
        _git_push(f"Session data — {_now()}")


# ════════════════════════════════════════════════════════════════════════════
#  STATUS
# ════════════════════════════════════════════════════════════════════════════

def _print_stats():
    stats = webhook._session.get("stats", {})
    total = webhook._session.get("total_leads", 0)
    _banner("Session Stats")
    print(f"  Total leads  : {total}")
    print(f"  Calls made   : {stats.get('calls_made', 0)}")
    print(f"  DMs reached  : {stats.get('dms_reached', 0)}")


# ════════════════════════════════════════════════════════════════════════════
#  TEST CALL
# ════════════════════════════════════════════════════════════════════════════

def run_test():
    """Start the webhook server and verify browser connection + a single test dial."""
    _banner("Test")
    _start_tunnel()
    _update_twiml_app()
    session_id = "test-" + str(uuid.uuid4())[:4]
    webhook.init_session(config, session_id)

    server_thread = threading.Thread(
        target=webhook.start_server,
        args=(config,),
        daemon=True
    )
    server_thread.start()
    time.sleep(1)

    port      = config.get("webhook_port", 5000)
    agent_url = f"http://localhost:{port}/agent"
    print(f"🌐 Opening: {agent_url}")
    import webbrowser
    webbrowser.open(agent_url)
    print("   Click Connect — you should hear hold music.\n")
    print("   Waiting for browser to connect...")

    for _ in range(120):
        if webhook._session.get("dylan_sid"):
            break
        time.sleep(1)
    else:
        print("❌ Browser didn't connect in time.")
        return

    print("✅ Browser connected — Twilio + webhook are working.")
    input("\nPress Enter to stop the server...")


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

    if cmd == "test":
        run_test()
    else:
        run_session()
