import time, requests, re, threading
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin

# === CONFIG ===
BOT_TOKEN = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID = "6145988808"
CHECK_URL = "https://psa.wf/"
SLEEP_SEC = 3
# ==============

scraper = cloudscraper.create_scraper()
RUNNING = False
offset = None

def send_telegram(msg, keyboard=None):
    """Send Telegram message with optional inline keyboard."""
    payload = {"chat_id": CHAT_ID, "text": msg}
    if keyboard:
        payload["reply_markup"] = keyboard
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
    except Exception as e:
        print("Telegram error:", e)

def inline_keyboard():
    """Create inline keyboard JSON."""
    return {
        "inline_keyboard": [
            [
                {"text": "🟢 Start", "callback_data": "start"},
                {"text": "🔴 Stop", "callback_data": "stop"},
                {"text": "ℹ️ Status", "callback_data": "status"},
            ]
        ]
    }

def extract_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for h2 in soup.find_all("h2", class_="entry-title"):
        a = h2.find("a", href=True)
        if a:
            title = a.get_text(strip=True)
            href = urljoin(CHECK_URL, a["href"])
            posts.append((title, href))
    return posts

def monitor_loop():
    global RUNNING
    seen = set()
    send_telegram("✅ PSA Monitor ready.", inline_keyboard())
    while True:
        if RUNNING:
            try:
                html = scraper.get(CHECK_URL, timeout=20).text
                posts = extract_posts(html)
                for title, url in posts:
                    if url not in seen:
                        seen.add(url)
                        send_telegram(f"📄 {title}\n🔗 {url}")
            except Exception as e:
                print("Monitor error:", e)
            time.sleep(SLEEP_SEC)
        else:
            time.sleep(2)

def telegram_listener():
    global RUNNING, offset
    while True:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                                params={"offset": offset, "timeout": 30}).json()
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    data = upd["callback_query"]["data"]
                    chat_id = str(upd["callback_query"]["message"]["chat"]["id"])
                    if chat_id != CHAT_ID:
                        continue
                    if data == "start":
                        if not RUNNING:
                            RUNNING = True
                            send_telegram("🟢 Monitoring started.", inline_keyboard())
                        else:
                            send_telegram("ℹ️ Already running.", inline_keyboard())
                    elif data == "stop":
                        if RUNNING:
                            RUNNING = False
                            send_telegram("🔴 Monitoring stopped.", inline_keyboard())
                        else:
                            send_telegram("ℹ️ Already stopped.", inline_keyboard())
                    elif data == "status":
                        status = "✅ Running" if RUNNING else "⏸️ Paused"
                        send_telegram(f"ℹ️ Status: {status}", inline_keyboard())
        except Exception as e:
            print("Listener error:", e)
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=monitor_loop, daemon=True).start()
    telegram_listener()
