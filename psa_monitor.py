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
SLEEP_SEC = 1   # check every 3 seconds  
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
            data={  
                "chat_id": CHAT_ID,  
                "text": msg,  
                "disable_web_page_preview": False  # cleaner look, no preview box  
            }  
        )  
    except Exception:  
        pass  
  
  
def extract_main_posts(soup):  
    """Extract normal homepage posts (Billy the Kid, Tulsa King, etc.)"""  
    posts = []  
    for article in soup.find_all("article", class_=re.compile("post-")):  
        h2 = article.find("h2", class_="entry-title")  
        if not h2:  
            continue  
        a = h2.find("a", href=True)  
        if not a:  
            continue  
  
        title = a.get_text(strip=True)  
        href = urljoin(CHECK_URL, a["href"])  
  
        update_text = ""  
        caption = article.find("p", class_="caption")  
        if caption:  
            raw = caption.get_text(" ", strip=True)  
            m = re.search(r"(?:UPDATE\s*[-–>]*\s*)?(.+)", raw, re.I)  
            if m:  
                update_text = m.group(1).strip()  
  
        full_title = f"{title} — {update_text}" if update_text else title  
        posts.append((full_title, href))  
    return posts  
  
  
def extract_reuploads(soup):  
    """Extract titles from 'Recently Reuploaded' section."""  
    posts = []  
    header = soup.find("h2", string=re.compile("Recently Reuploaded", re.I))  
    if header:  
        ul = header.find_next("ul")  
        if ul:  
            for li in ul.find_all("li"):  
                a = li.find("a", href=True)  
                if not a:  
                    continue  
                title = a.get_text(strip=True)  
                href = urljoin(CHECK_URL, a["href"])  
                posts.append((title, href))  
    return posts  
  
  
def format_message(title, url):  
    """Telegram message format."""  
    return f"📄 {title}\n\n🔗 Open URL - {url}"  # <— added one blank line for cleaner spacing  
  
  
def main():  
    seen = {}  
    try:  
        html = scraper.get(CHECK_URL, timeout=20).text  
        soup = BeautifulSoup(html, "html.parser")  
  
        posts = extract_main_posts(soup)  
        reuploads = extract_reuploads(soup)  
  
        for title, url in posts + reuploads:  
            seen[url] = title  
  
        send_telegram(f"✅ PSA Monitor started\nMonitoring: {CHECK_URL}")  
        print(f"Initialized with {len(seen)} items.")  
  
    except Exception as e:  
        print("Initial load failed:", e)  
  
    while True:  
        try:  
            html = scraper.get(CHECK_URL, timeout=20).text  
            soup = BeautifulSoup(html, "html.parser")  
  
            posts = extract_main_posts(soup)  
            reuploads = extract_reuploads(soup)  
  
            for title, url in reversed(posts + reuploads):  
                if url not in seen:  
                    seen[url] = title  
                    send_telegram(format_message(title, url))  
                    print(f"🆕 New: {title}")  
                elif title != seen[url]:  
                    seen[url] = title  
                    send_telegram(format_message(title, url))  
                    print(f"♻️ Updated: {title}")  
  
        except Exception as e:  
            print("Error:", e)  
        time.sleep(SLEEP_SEC)  
  
  
if name == "main":  
    main()
