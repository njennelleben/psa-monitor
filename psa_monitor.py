import time
import requests
import re
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin

# === CONFIG ===
BOT_TOKEN = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID   = "6145988808"
CHECK_URL = "https://psa.wf/"
SLEEP_SEC = 3
MAX_SCAN = 200
# ==============

scraper = cloudscraper.create_scraper()

POSITIVE = [
    "720p", "1080p", "2160p", "4k", "WEB", "WEB-DL", "WEBRIP",
    "BluRay", "HDR", "DVDRip", "BDRip",
    "x264", "x265", "HEVC", "10bit", "S01", "S02", "E01", "Episode", "Season"
]
NEGATIVE = [
    "seed", "seeding", "working download", "magnet", "torrent",
    "category", "tv pack"
]
EXCLUDE_URL_PARTS = ["category", "tag", "/tv-pack", "/movies"]

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Telegram send error:", e)

def looks_like_post(text, url):
    if not text:
        return False
    if any(x in url.lower() for x in EXCLUDE_URL_PARTS):
        return False
    t = text.lower()
    if any(n in t for n in NEGATIVE):
        return False
    return any(p.lower() in t for p in POSITIVE)

def extract_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    all_links = soup.find_all("a", href=True)
    print(f"Found {len(all_links)} total <a> tags")

    for a in all_links[:MAX_SCAN]:
        href = a["href"]
        url = urljoin(CHECK_URL, href)
        text = a.get_text(" ", strip=True)
        if looks_like_post(text, url):
            posts.append((text.strip(), url))

    print(f"Filtered posts: {len(posts)}")
    for t, u in posts[:5]:
        print(f"  -> {t} ({u})")
    return posts

def main():
    seen = {}
    try:
        html = scraper.get(CHECK_URL, timeout=20).text
        print("Fetched page length:", len(html))
        if len(html) < 5000:
            print("⚠️ Cloudflare challenge detected or blank page!")
        posts = extract_posts(html)
        for title, url in posts:
            seen[url] = title
        print(f"Initialized with {len(seen)} items.")
        send_telegram(f"✅ PSA Monitor (debug mode) started\nMonitoring: {CHECK_URL}")
    except Exception as e:
        print("Initial load failed:", e)

    while True:
        try:
            html = scraper.get(CHECK_URL, timeout=20).text
            if len(html) < 5000:
                print("⚠️ Cloudflare page (too short), retrying...")
                time.sleep(10)
                continue
            posts = extract_posts(html)
            for title, url in reversed(posts):
                if url not in seen:
                    seen[url] = title
                    print(f"🆕 New post detected: {title}")
        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
