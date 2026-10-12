"""
Fast, simple WhatsApp agent (Whapi.cloud).

Setup:
    pip install flask requests
    export WHAPI_TOKEN="your_whapi_token"
    export WHAPI_CHANNEL_ID="your_channel_id"
    # optional - enables AI replies instead of a plain acknowledgement:
    export ANTHROPIC_API_KEY="sk-ant-..."

Run:
    python whatsapp_agent.py

Then expose it publicly (e.g. `ngrok http 5000`) and set the webhook URL in
Whapi dashboard -> your channel -> Settings -> Webhooks:
    https://<your-public-url>/webhook      (event: messages, mode: post)
"""
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import threading

import requests
from flask import Flask, request, jsonify

WHAPI_TOKEN = os.environ["WHAPI_TOKEN"]
WHAPI_CHANNEL_ID = os.environ.get("WHAPI_CHANNEL_ID", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

ACK_MESSAGE = "✅ Got your message! I'll get back to you shortly."
SYSTEM_PROMPT = "You are a helpful WhatsApp assistant. Keep replies short and friendly."

app = Flask(__name__)


def send_whatsapp(chat_id: str, text: str) -> None:
    r = requests.post(
        "https://gate.whapi.cloud/messages/text",
        headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
        json={"to": chat_id, "body": text},
        timeout=15,
    )
    if not r.ok:
        print("Whapi send error:", r.status_code, r.text)


def ai_reply(user_text: str) -> str:
    """Use Claude if a key is set, otherwise return the plain acknowledgement."""
    if not ANTHROPIC_API_KEY:
        return ACK_MESSAGE
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-5-5",
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_text}],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        print("AI error:", e)
        return ACK_MESSAGE


def handle_message(msg: dict) -> None:
    chat_id = msg.get("chat_id")
    text = (msg.get("text") or {}).get("body", "")
    if not chat_id or not text:
        return
    send_whatsapp(chat_id, ai_reply(text))


@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}

    # Ignore events from other channels
    if WHAPI_CHANNEL_ID and data.get("channel_id") not in (None, WHAPI_CHANNEL_ID):
        return jsonify(ok=True)

    for msg in data.get("messages", []):
        # Skip our own messages (prevents reply loops) and non-text
        if msg.get("from_me") or msg.get("type") != "text":
            continue
        # Reply in the background so the webhook returns instantly
        threading.Thread(target=handle_message, args=(msg,), daemon=True).start()

    return jsonify(ok=True)


@app.get("/")
def health():
    return "WhatsApp agent running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
