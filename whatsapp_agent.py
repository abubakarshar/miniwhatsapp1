"""
Mind Master Operations Challenge - WhatsApp auto-reply bot (Whapi.cloud)

Env vars (set in Railway > Variables):
    WHAPI_TOKEN        your Whapi channel token
    WHAPI_CHANNEL_ID   your channel id (optional, used to filter events)
"""
import os
import time
import threading

import requests
from flask import Flask, request, jsonify


def env(name: str) -> str:
    """Read an env var, tolerating stray spaces/quotes in its name or value."""
    for k, v in os.environ.items():
        if k.strip().strip("\"'").upper() == name:
            return v.strip().strip("\"'")
    return ""


VERSION = "v3"
print(f"whatsapp_agent {VERSION} starting")

WHAPI_TOKEN = env("WHAPI_TOKEN")
WHAPI_CHANNEL_ID = env("WHAPI_CHANNEL_ID")

if not WHAPI_TOKEN:
    # Print variable NAMES only (never values) to help debugging
    print("WARNING: WHAPI_TOKEN not found. Variable names seen:",
          sorted(repr(k) for k in os.environ if "WHAPI" in k.upper() or "TOKEN" in k.upper()))

WELCOME_MESSAGE = """Hi! Thanks for taking the Mind Master Operations Challenge 👋

Please send your score screenshot together with:

Name:
Company & industry:
Role:
One operational problem you’d like to solve:

For example: “We manually enter WhatsApp orders into our ERP, which takes an hour each day.”

Are you looking to improve this within 3 months, within 6 months, or just exploring?

If you’re at the event, drop by our booth so we can check in your entry and discuss your workflow.

We’ll use these details to manage your entry. If you’d also like a tailored demo or workflow review, reply DEMO."""

DEMO_REPLY = "Thanks! 🙌 We've noted your interest in a tailored demo / workflow review. Our team will be in touch shortly."

# Send the welcome message once per chat, then stay quiet for this long
# (so people can reply with their details without being spammed).
COOLDOWN_SECONDS = 24 * 60 * 60
last_welcome = {}  # chat_id -> timestamp (resets if the app restarts)

app = Flask(__name__)


def send_whatsapp(chat_id: str, text: str) -> None:
    try:
        r = requests.post(
            "https://gate.whapi.cloud/messages/text",
            headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
            json={"to": chat_id, "body": text},
            timeout=15,
        )
        if not r.ok:
            print("Whapi send error:", r.status_code, r.text)
    except Exception as e:
        print("Whapi send exception:", e)


def handle_message(msg: dict) -> None:
    chat_id = msg.get("chat_id")
    if not chat_id or chat_id.endswith("@g.us"):  # ignore group chats
        return

    text = ((msg.get("text") or {}).get("body") or "").strip()

    if text.upper() == "DEMO":
        send_whatsapp(chat_id, DEMO_REPLY)
        return

    now = time.time()
    if now - last_welcome.get(chat_id, 0) < COOLDOWN_SECONDS:
        return
    last_welcome[chat_id] = now
    send_whatsapp(chat_id, WELCOME_MESSAGE)


@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}

    if WHAPI_CHANNEL_ID and data.get("channel_id") not in (None, WHAPI_CHANNEL_ID):
        return jsonify(ok=True)

    for msg in data.get("messages", []):
        if msg.get("from_me"):  # never reply to ourselves
            continue
        threading.Thread(target=handle_message, args=(msg,), daemon=True).start()

    return jsonify(ok=True)


@app.get("/")
def health():
    return f"Bot {VERSION} running | token loaded: {bool(WHAPI_TOKEN)} | channel loaded: {bool(WHAPI_CHANNEL_ID)}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
