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

# cloudscraper helps bypass most Cloudflare checks
scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

def send_telegram(msg):
    """Send a message to Telegram chat."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Telegram send error:", e)

def looks_like_post(text, url):
    """Identify real post links based on text patterns."""
    if not text:
        return False
    # ignore obvious category or tag URLs
    if any(x in url.lower() for x in ["category", "tag"]):
        return False
    # detect episode or resolution info
    if re.search(r"(S\d{1,2}E\d{1,2})", text, re.I):
        return True
    if re.search(r"(720p|1080p|2160p|WEB|BluRay|HDR|10bit|x265|x264)", text, re.I):
        return True
    return False

def extract_posts(html):
    """Parse posts from the PSA homepage."""
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

def format_message(title, url):
    """Format Telegram message."""
    return f"📄 {title}\n🔗 Open URL - {url}"

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
        send_telegram(f"✅ PSA Monitor (debug mode) started\nMonitoring: {CHECK_URL}")
        print(f"Initialized with {len(seen)} items.")
    except Exception as e:
        print("Initial load failed:", e)

    # Main loop
    while True:
        try:
            html = scraper.get(CHECK_URL, timeout=20).text
            print("Fetched page length:", len(html))
            if len(html) < 5000:
                print("⚠️ Cloudflare page (too short), retrying in 10s...")
                time.sleep(10)
                continue

            posts = extract_posts(html)
            for title, url in reversed(posts):
                if url not in seen:
                    seen[url] = title
                    msg = format_message(title, CHECK_URL)
                    send_telegram(msg)
                    print(f"🆕 New post detected: {title}")
                elif title != seen[url]:
                    seen[url] = title
                    msg = format_message(title, CHECK_URL)
                    send_telegram(msg)
                    print(f"♻️ Updated post detected: {title}")
        except Exception as e:
            print("Error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
