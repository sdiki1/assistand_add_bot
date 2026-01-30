# random_meme_bot.py
# Telegram bot: sends a random post from a channel by message_id
# Minimal version, no external libraries

import json
import time
import random
import urllib.request

TOKEN = "8562443661:AAFTSLIJYd0kZCI316iyIpJrBBdtUKdK1Y0"
CHANNEL_USERNAME = "krisarium"
MIN_ID = 1

API_URL = f"https://api.telegram.org/bot{TOKEN}"


def api(method, data=None): # чутка подправил метод, выводит ошибку фулл, а не слетает
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(f"{API_URL}/{method}", data=payload)
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            return json.loads(f.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Telegram API error {e.code}: {body}")

        if e.code == 409:
            time.sleep(2)
            return {"ok": False, "result": []}

        raise

def send_message(chat_id, text):
    api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False
    })


offset = 0
last_known_id = 5000 

print("Bot started...")

api("deleteWebhook", {"drop_pending_updates": True}) # - Удаляет вебхук и сбрасывает обновления

while True:
    updates = api("getUpdates", {
        "offset": offset,
        "timeout": 30
    })

    for update in updates.get("result", []):
        offset = update["update_id"] + 1

        if "message" not in update:
            continue

        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").lower()

        if text in ("/start", "мем", "mem"):
            post_id = random.randint(MIN_ID, last_known_id)
            link = f"https://t.me/{CHANNEL_USERNAME}/{post_id}"
            send_message(chat_id, f"🎲 Лови случайный мем:\n{link}")

    time.sleep(1)
