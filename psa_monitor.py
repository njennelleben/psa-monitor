import time
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin

# === CONFIG ===
BOT_TOKEN = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID   = "6145988808"
CHECK_URL = "https://psa.wf/"
SLEEP_SEC = 3      # check every 3 seconds
MAX_SCAN = 200
# ==============

scraper = cloudscraper.create_scraper()

POSITIVE = [
    "720p","1080p","2160p","4k","WEB","WEB-DL","WEBRIP",
    "BluRay","BRRip","HDR","DVDRip","BDRip",
    "x264","x265","HEVC","10bit","S01","S02","E01","Episode","Season"
]
NEGATIVE = [
    "seed", "seeding", "working download", "use the working",
    "i already", "i didn't try", "download link",
    "magnet", "torrent"
]
quality_re = re.compile(r'\b(19|20)\d{2}\b')

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Telegram send error:", e)

def looks_like_post(text):
    if not text:
        return False
    t = text.lower()
    for n in NEGATIVE:
        if n in t:
            return False
    if any(p.lower() in t for p in POSITIVE):
        return True
    if quality_re.search(t):
        return True
    return False

def extract_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for post in soup.find_all(["article", "div"], class_=re.compile("post")):
        title_tag = post.find("a", href=True)
        if not title_tag:
            continue
        title_text = title_tag.get_text(" ", strip=True)
        if not looks_like_post(title_text):
            continue

        # Try to find the "UPDATE -> ..." or similar line
        update_tag = post.find(string=re.compile("UPDATE", re.I))
        update_text = ""
        if update_tag:
            update_text = re.sub(r"UPDATE\s*->\s*", "", update_tag.strip(), flags=re.I)
        full_text = f"{title_text} — {update_text}" if update_text else title_text
        href = title_tag["href"]
        url = urljoin(CHECK_URL, href)
        posts.append((full_text.strip(), url))

    return posts

def format_message(title, url):
    msg = f"📄 {title}\n🔗 Open URL - {url}"
    return msg

def main():
    seen = {}
    try:
        html = scraper.get(CHECK_URL, timeout=20).text
        for title, url in extract_posts(html):
            seen[url] = title
        send_telegram(f"✅ PSA Monitor started\nMonitoring: {CHECK_URL}")
        print(f"Initialized with {len(seen)} items.")
    except Exception as e:
        print("Initial load failed:", e)

    while True:
        try:
            r = scraper.get(CHECK_URL, timeout=20)
            r.raise_for_status()
            html = r.text
            current = extract_posts(html)

            for title, url in reversed(current):
                if url not in seen:
                    seen[url] = title
                    send_telegram(format_message(title, CHECK_URL))
                elif title != seen[url]:
                    seen[url] = title
                    send_telegram(format_message(title, CHECK_URL))
        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
