"""
SMS Agent — Flask webhook server

Receives inbound SMS webhooks from GHL and routes them to the AI appointment agent.

Usage:
  python server.py           Start server + ngrok tunnel
  python server.py --no-ngrok  Start server only (if you manage your own tunnel)

First time setup:
  1. Secrets (ANTHROPIC_API_KEY, GHL_PRIVATE_TOKEN, NOTION_TOKEN, GOOGLE_CREDENTIALS_JSON) live in the
     shared "digigrowth" Doppler vault (config prd_apptset) — run via `doppler run -- python server.py`
  2. pip install -r requirements.txt
  3. Set webhook_base_url in config.json to your ngrok/public URL
  4. doppler run -- python server.py
  5. In GHL → Settings → Integrations → Webhooks → Add two webhooks:
       URL: https://<your-url>/sms/incoming   Events: InboundMessage
       URL: https://<your-url>/tag-update     Events: ContactTagUpdate
"""

import json
import os
import sys
import threading
import time

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from flask import Flask, request, jsonify
from dotenv import load_dotenv

import sms_agent

load_dotenv()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_FILE) as f:
    config = json.load(f)

app = Flask(__name__)


@app.route("/sms/incoming", methods=["POST"])
def sms_incoming():
    """
    GHL fires this for every inbound SMS (InboundMessage webhook event).
    Routes to the AI agent if the sender has the 'sms-handoff' tag in GHL.
    Returns 200 immediately; heavy work runs in a daemon thread.
    """
    data = request.get_json(force=True, silent=True) or {}

    # GHL workflow sends phone in standard data, body nested under 'message'
    from_phone = (data.get("phone") or "").strip()
    body = (
        (data.get("message") or {}).get("body")
        or data.get("body")
        or ""
    ).strip()

    if from_phone and body:
        threading.Thread(
            target=sms_agent.handle_reply,
            args=(from_phone, body, config),
            daemon=True,
        ).start()

    return jsonify({"status": "ok"}), 200


@app.route("/tag-update", methods=["POST"])
def tag_update():
    """
    GHL workflow webhook — fires when sms-handoff tag is added to a contact.
    Accepts GHL's standard workflow payload (contact_id snake_case) or
    the legacy ContactTagUpdate format (contactId camelCase).
    """
    import ghl as ghl_mod

    data = request.get_json(force=True, silent=True) or {}

    # GHL workflow webhooks send contact_id (snake_case); legacy uses contactId
    contact_id = (
        data.get("contact_id") or
        data.get("contactId") or
        data.get("id", "")
    )
    if not contact_id:
        print(f"  ⚠️  /tag-update: no contact_id in payload: {data}")
        return jsonify({"status": "no_contact_id"}), 200

    def _fire():
        contact = ghl_mod.get_contact_by_id(config, contact_id)
        if not contact:
            print(f"  ⚠️  /tag-update: could not fetch contact {contact_id}")
            return
        lead = ghl_mod.contact_to_lead(contact)
        sms_agent.send_outbound(config, contact_id, lead)

    threading.Thread(target=_fire, daemon=True).start()
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


# ── Startup ───────────────────────────────────────────────────────────────────

def _start_tunnel():
    from pyngrok import ngrok, conf as ngrok_conf
    from urllib.parse import urlparse

    auth_token = os.environ.get("NGROK_AUTH_TOKEN", "")
    if auth_token:
        ngrok_conf.get_default().auth_token = auth_token

    base_url = config.get("webhook_base_url", "").rstrip("/")
    port     = config.get("webhook_port", 5001)

    domain = None
    if "ngrok" in base_url:
        domain = urlparse(base_url).netloc

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
        print(f"  ⚠️  Could not start ngrok: {e}")
        sys.exit(1)


def _followup_thread():
    """Background thread: checks for overdue follow-ups every 15 minutes."""
    while True:
        try:
            sms_agent.check_followups(config)
        except Exception as e:
            print(f"  ⚠️  Follow-up thread error: {e}")
        time.sleep(15 * 60)


if __name__ == "__main__":
    use_ngrok = "--no-ngrok" not in sys.argv
    port      = config.get("webhook_port", 5001)

    print("\n─────────────────────────────────────")
    print("  SMS Appointment Agent")
    print("─────────────────────────────────────")

    public_url = config.get("webhook_base_url", "").rstrip("/")
    if use_ngrok:
        public_url = _start_tunnel()

    sms_url    = f"{public_url}/sms/incoming"
    tag_url    = f"{public_url}/tag-update"
    print(f"\n📱 SMS webhook:       {sms_url}")
    print(f"🏷️  Tag-update webhook: {tag_url}")
    print("   Register both in GHL → Settings → Integrations → Webhooks")
    print("   Press Ctrl+C to stop\n")

    # Start follow-up background thread
    t = threading.Thread(target=_followup_thread, daemon=True)
    t.start()
    print("  ✅ Follow-up scheduler started (every 15 min)\n")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
