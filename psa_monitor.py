import time, requests
from bs4 import BeautifulSoup
import cloudscraper

BOT_TOKEN = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID   = "6145988808"
CHECK_URL = "https://psa.wf/"
SLEEP_SEC = 3

scraper = cloudscraper.create_scraper()

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram send error:", e)

def extract_titles(html):
    soup = BeautifulSoup(html, "html.parser")
    titles = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if len(text) < 6: continue
        keywords = ["720p","1080p","WEB","BluRay","HDR","WEB-DL","x264","x265","HEVC","S01","S02","E01","Episode","Season"]
        if any(k.lower() in text.lower() for k in keywords):
            titles.append(text)
    return list(dict.fromkeys(titles))

seen = set()
while True:
    try:
        r = scraper.get(CHECK_URL, timeout=20)
        r.raise_for_status()
        html = r.text
        for title in extract_titles(html):
            if title not in seen:
                seen.add(title)
                msg = f"PSA NEW: {title}"
                print(msg)
                send_telegram(msg)
    except Exception as e:
        print("Error:", e)
    time.sleep(SLEEP_SEC)
