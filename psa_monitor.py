# psa_monitor.py
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
SLEEP_SEC = 1      # change to 1 if you want 1-second checks (more load)
MAX_SCAN = 200
# ==============

scraper = cloudscraper.create_scraper(timeout=20)

# Positive keywords for actual releases
POSITIVE = [
    "720p","1080p","2160p","4k","WEB","WEB-DL","WEBRIP",
    "BluRay","BRRip","HDR","DVDRip","BDRip",
    "x264","x265","HEVC","10bit","S01","S02","E01","Episode","Season"
]

# Negative words (only for user comment noise)
NEGATIVE = [
    "seed", "seeding", "working download", "use the working",
    "i already", "i didn't try", "download link",
    "magnet", "torrent"
]

quality_re = re.compile(r'\b(19|20)\d{2}\b')  # match a year

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
    # skip obvious comment noise
    for n in NEGATIVE:
        if n in t:
            return False
    # allow "reuploaded" (admins) — do NOT exclude it
    # require any quality word or year
    if any(p.lower() in t for p in POSITIVE):
        return True
    if quality_re.search(t):
        return True
    return False

def anchor_near_image(a_tag):
    # check if anchor itself contains img or nearby contains an img
    if a_tag.find("img"):
        return True
    parent = a_tag.parent
    for _ in range(3):
        if parent is None:
            break
        if parent.find("img"):
            return True
        parent = parent.parent
    sib = a_tag.find_next_sibling()
    if sib and sib.find("img"):
        return True
    return False

def extract_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    results = []
    count = 0
    for a in anchors:
        if count >= MAX_SCAN:
            break
        count += 1
        text = a.get_text(" ", strip=True)
        href = a["href"]
        url = urljoin(CHECK_URL, href)
        # Only posts with release-like text or near an image (homepage tiles)
        if looks_like_post(text) or anchor_near_image(a):
            if len(text) > 6:
                results.append((text, url))
    # dedupe by url preserving order
    seen_local = set()
    out = []
    for t,u in results:
        if u in seen_local:
            continue
        seen_local.add(u)
        out.append((t,u))
    return out

def format_message(title, url):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"🎬 NEW PSA POST\n"
        f"📄 {title}\n"
        f"🔗 {url}\n"
        f"🕒 Detected: {ts}"
    )
    return msg

def main():
    seen = set()
    # initial load: mark existing homepage items as seen
    try:
        html = scraper.get(CHECK_URL).text
        for _, u in extract_posts(html):
            seen.add(u)
        print(f"Initialized with {len(seen)} existing items.")
    except Exception as e:
        print("Initial load failed:", e)

    while True:
        try:
            r = scraper.get(CHECK_URL)
            r.raise_for_status()
            html = r.text
            posts = extract_posts(html)
            # send oldest-first among newly discovered
            for title, url in reversed(posts):
                if url not in seen:
                    seen.add(url)
                    msg = format_message(title, url)
                    print("New ->", title, url)
                    send_telegram(msg)
        except Exception as e:
            print("Error during check:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
