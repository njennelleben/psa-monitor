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
SLEEP_SEC = 3   # check every 3 seconds
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
        pass


def extract_posts(html):
    """Extract post title, update info, and direct link from PSA homepage."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    # PSA titles are inside <h2 class="entry-title">
    for h2 in soup.find_all("h2", class_="entry-title"):
        a = h2.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = urljoin(CHECK_URL, a["href"])

        # find nearby <p class="caption"> tag with "update" text
        update_tag = h2.find_next("p", class_="caption")
        update_text = ""
        if update_tag:
            raw_text = update_tag.get_text(" ", strip=True)
            m = re.search(r"update\s*[-–>]+\s*(.+)", raw_text, re.I)
            if m:
                update_text = m.group(1).strip()

        # combine
        full_title = f"{title} — {update_text}" if update_text else title

        # Only keep posts that look like releases
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
                # new post
                if url not in seen:
                    seen[url] = title
                    send_telegram(format_message(title, url))
                    print(f"🆕 New post: {title}")
                # updated post
                elif title != seen[url]:
                    seen[url] = title
                    send_telegram(format_message(title, url))
                    print(f"♻️ Updated: {title}")

        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main()
