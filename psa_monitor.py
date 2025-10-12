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
    """Send Telegram alert message."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception:
        pass  # don't crash on temporary network failures

def extract_posts(html):
    """Extract post title, update info, and direct link from PSA homepage."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for block in soup.find_all("h2"):
        a = block.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = urljoin(CHECK_URL, a["href"])

        # find the next sibling containing update text
        update = ""
        nxt = block.find_next_sibling()
        if nxt:
            m = re.search(r"UPDATE\s*[-–>]+\s*(.+)", nxt.get_text(" ", strip=True), re.I)
            if m:
                update = m.group(1).strip()

        if update:
            full_title = f"{title} — {update}"
        else:
            full_title = title

        if re.search(r"(S\d{1,2}E\d{1,2}|720p|1080p|2160p|WEB|BluRay|10bit|Reuploaded|WEBRip)", full_title, re.I):
            posts.append((full_title, href))

    return posts

def format_message(title, url):
    """Telegram message format."""
    return f"📄 {title}\n🔗 Open URL - {url}"

def main():
    seen = {}
    try:
        html = scraper.get(CHECK_URL, timeout=20).text
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
                    send_telegram(format_message(title, url))
                    print(f"🆕 {title}")
                elif title != seen[url]:
                    seen[url] = title
                    send_telegram(format_message(title, url))
                    print(f"♻️ Updated {title}")

        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
