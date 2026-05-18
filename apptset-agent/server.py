"""
SMS Agent — Flask webhook server

Receives inbound SMS webhooks from GHL and routes them to the AI appointment agent.

Usage:
  python server.py           Start server + ngrok tunnel
  python server.py --no-ngrok  Start server only (if you manage your own tunnel)

First time setup:
  1. cp .env.example .env and fill in keys
  2. pip install -r requirements.txt
  3. Set webhook_base_url in config.json to your ngrok/public URL
  4. python server.py
  5. In GHL → Settings → Integrations → Webhooks → Add webhook:
       URL: https://<your-url>/sms/incoming
       Events: InboundMessage
"""

import json
import os
import sys
import threading

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

    # Only handle SMS inbound messages
    if data.get("type") != "InboundMessage" or data.get("messageType", "SMS") != "SMS":
        return jsonify({"status": "ignored"}), 200

    from_phone = data.get("phone", "")
    body       = (data.get("body") or data.get("message") or "").strip()

    if from_phone and body:
        threading.Thread(
            target=sms_agent.handle_reply,
            args=(from_phone, body, config),
            daemon=True,
        ).start()

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


if __name__ == "__main__":
    use_ngrok = "--no-ngrok" not in sys.argv
    port      = config.get("webhook_port", 5001)

    print("\n─────────────────────────────────────")
    print("  SMS Appointment Agent")
    print("─────────────────────────────────────")

    public_url = config.get("webhook_base_url", "").rstrip("/")
    if use_ngrok:
        public_url = _start_tunnel()

    sms_url = f"{public_url}/sms/incoming"
    print(f"\n📱 Webhook URL: {sms_url}")
    print("   Set this in GHL → Settings → Integrations → Webhooks (event: InboundMessage)")
    print("   Press Ctrl+C to stop\n")

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
