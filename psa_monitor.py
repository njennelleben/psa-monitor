import time
import threading
import requests
import re
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler

# === CONFIG ===
BOT_TOKEN = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID = "6145988808"
CHECK_URL = "https://psa.wf/"
SLEEP_SEC = 3  # check every 3 seconds
MAX_SCAN = 300
# ==============

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

# Ignore these sections
IGNORE_PATTERN = re.compile(r"(TV[\s\-]*PACK|Re[\s\-]*Upload\s*Center)", re.I)

monitoring_active = False
seen = {}


# === Telegram Functions ===

def send_telegram(msg):
    """Send Telegram alert message."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Telegram send error:", e)


def format_message(title, url):
    """Telegram message format."""
    return f"📄 {title}\n🔗 Open URL - {url}"


# === Scraper Core ===

def extract_posts(html):
    """Extracts each post title + the <p class='caption'> update line only."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for h2 in soup.find_all("h2", class_="entry-title"):
        a = h2.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = urljoin(CHECK_URL, a["href"])

        if IGNORE_PATTERN.search(title):
            continue

        # Look only for <p class="caption">
        update_text = ""
        caption_tag = h2.find_next("p", class_="caption")
        if caption_tag:
            text = caption_tag.get_text(" ", strip=True)
            # Remove any leading "UPDATE ->" or similar
            update_text = re.sub(r"^UPDATE\s*[-–>]+\s*", "", text, flags=re.I).strip()

        final_title = f"{title} — {update_text}" if update_text else title
        posts.append((final_title, href))

    return posts


def monitor_loop():
    """Background monitoring loop."""
    global seen, monitoring_active

    while True:
        if monitoring_active:
            try:
                html = scraper.get(CHECK_URL, timeout=20).text
                posts = extract_posts(html)

                for title, url in reversed(posts):
                    if url not in seen:
                        seen[url] = title
                        send_telegram(format_message(title, url))
                        print(f"🆕 New post: {title}")
                    elif seen[url] != title:
                        seen[url] = title
                        send_telegram(format_message(title, url))
                        print(f"♻️ Updated: {title}")

            except Exception as e:
                print("Error:", e)

        time.sleep(SLEEP_SEC)


# === Telegram Bot Controls ===

def start_bot(update: Update, context: CallbackContext):
    global monitoring_active
    monitoring_active = True
    update.message.reply_text("✅ Monitoring started")

def stop_bot(update: Update, context: CallbackContext):
    global monitoring_active
    monitoring_active = False
    update.message.reply_text("🛑 Monitoring stopped")

def status(update: Update, context: CallbackContext):
    state = "🟢 Active" if monitoring_active else "🔴 Stopped"
    update.message.reply_text(f"Status: {state}")

def button_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Start", callback_data="start"),
         InlineKeyboardButton("Stop", callback_data="stop"),
         InlineKeyboardButton("Status", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("PSA Monitor ready ✅", reply_markup=reply_markup)

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    cmd = query.data
    if cmd == "start":
        start_bot(update, context)
    elif cmd == "stop":
        stop_bot(update, context)
    elif cmd == "status":
        status(update, context)

def telegram_listener():
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("menu", button_menu))
    dp.add_handler(CommandHandler("start", start_bot))
    dp.add_handler(CommandHandler("stop", stop_bot))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CallbackQueryHandler(button_handler))
    updater.start_polling()
    updater.idle()


# === Main ===

def initialize_seen():
    """Initializes seen posts to avoid duplicates at startup."""
    global seen
    try:
        html = scraper.get(CHECK_URL, timeout=20).text
        posts = extract_posts(html)
        seen = {url: title for title, url in posts}
        print(f"Initialized with {len(seen)} items.")
        send_telegram(f"✅ PSA Monitor ready\nMonitoring: {CHECK_URL}")
    except Exception as e:
        print("Initialization error:", e)

if __name__ == "__main__":
    initialize_seen()
    threading.Thread(target=monitor_loop, daemon=True).start()
    telegram_listener()
