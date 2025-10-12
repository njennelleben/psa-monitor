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
MAX_SCAN = 500
# ==============

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Telegram send error:", e)

def looks_like_post(text):
    """Check if link text looks like a release title"""
    if not text:
        return False
    t = text.lower()
    if any(x in t for x in ["category", "pack", "archive", "torrent", "magnet"]):
        return False
    if re.search(r"s\d{1,2}e\d{1,2}", t):  # episode pattern
        return True
    if re.search(r"(720p|1080p|2160p|web|bluray|hdr|x265|10bit)", t):
        return True
    return False

def extract_posts(html):
    """Extract potential posts from entire homepage."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    print(f"Found {len(anchors)} <a> tags")

    posts = []
    seen_titles = set()

    for a in anchors[:MAX_SCAN]:
        text = a.get_text(" ", strip=True)
        if not looks_like_post(text):
            continue
        href = a["href"]
        url = urljoin(CHECK_URL, href)
        if len(text) < 4 or text in seen_titles:
            continue
        seen_titles.add(text)
        posts.append((text, url))

    print(f"Filtered posts: {len(posts)}")
    for t, u in posts[:5]:
        print(f"  -> {t} ({u})")
    return posts

def format_message(title, url):
    return f"📄 {title}\n🔗 Open URL - {url}"

def main():
    seen = {}
    try:
        html = scraper.get(CHECK_URL, timeout=20).text
        print("Fetched page length:", len(html))
        posts = extract_posts(html)
        for title, url in posts:
            seen[url] = title
        send_telegram(f"✅ PSA Monitor started\nMonitoring: {CHECK_URL}")
        print(f"Initialized with {len(seen)} items.")
    except Exception as e:
        print("Initial load failed:", e)

    while True:
        try:
            html = scraper.get(CHECK_URL, timeout=20).text
            posts = extract_posts(html)
            for title, url in reversed(posts):
                if url not in seen:
                    seen[url] = title
                    send_telegram(format_message(title, CHECK_URL))
                    print(f"🆕 New post detected: {title}")
                elif title != seen[url]:
                    seen[url] = title
                    send_telegram(format_message(title, CHECK_URL))
                    print(f"♻️ Updated post detected: {title}")
        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
