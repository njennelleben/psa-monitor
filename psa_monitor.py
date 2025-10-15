#!/usr/bin/env python3
"""
PSA Monitor v3.1
- Detects new posts on PSA website
- Automatically extracts gofile.io and mega.nz final links
- Uses your PSA premium cookies
- Sends formatted Telegram messages

Requirements:
pip install requests cloudscraper beautifulsoup4
"""

import time
import json
import re
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin
import requests
import os

# ========== CONFIG ==========
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4")
CHAT_ID     = os.getenv("CHAT_ID", "6145988808")
CHECK_URL   = "https://psa.wf/"
SLEEP_SEC   = 3  # check interval
COOKIE_FILE = "all_cookies.txt"  # optional backup cookie file
SEEN_FILE   = "seen_v3.json"
# ============================

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== COOKIE LOADER ==========
def load_cookies_from_env():
    """
    If Railway env vars PSA_COOKIE_NAME and PSA_COOKIE_VALUE exist,
    use them directly for premium login.
    """
    cookie_name = os.getenv("PSA_COOKIE_NAME")
    cookie_value = os.getenv("PSA_COOKIE_VALUE")
    if cookie_name and cookie_value:
        print("[+] Using cookie from environment variables.")
        return {cookie_name: cookie_value}
    return {}

def load_cookies_from_file(path):
    cookies = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value
    except FileNotFoundError:
        print(f"[!] Cookie file not found: {path}")
    except Exception as e:
        print("Error reading cookie file:", e)
    return cookies

cookie_map = load_cookies_from_env() or load_cookies_from_file(COOKIE_FILE)
if cookie_map:
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_map.items())
    scraper.headers.update({"Cookie": cookie_header})
    print(f"[+] Loaded {len(cookie_map)} cookie(s).")
else:
    print("[!] No cookies found. Premium-only links may fail.")

# ========== UTILS ==========
def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Could not save seen:", e)

def send_telegram(text):
    try:
        requests.post(
            TG_API + "/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False,
                "parse_mode": "HTML"
            },
            timeout=15,
        )
    except Exception as e:
        print("Telegram send error:", e)

# ========== PARSING ==========
QUALITY_RE = re.compile(r'\b(2160p|1080p|720p|480p|4k|HD)\b', re.I)
EPISODE_RE = re.compile(r'\bS(\d{1,2})E(\d{1,2})\b', re.I)

def parse_update_line(text):
    if not text:
        return False, None, None
    t = text.strip()
    ep_m = EPISODE_RE.search(t)
    qual_m = QUALITY_RE.search(t)
    is_tv = bool(ep_m)
    episode_code = ep_m.group(0).upper() if ep_m else None
    quality = qual_m.group(0).lower() if qual_m else None
    return is_tv, episode_code, quality

def extract_homepage_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for article in soup.find_all("article", class_=re.compile("post-")):
        h2 = article.find("h2", class_="entry-title")
        if not h2:
            continue
        a = h2.find("a", href=True)
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = urljoin(CHECK_URL, a["href"])
        caption = article.find("p", class_="caption")
        update_text = caption.get_text(" ", strip=True) if caption else ""
        posts.append({"title": title, "url": href, "update": update_text})
    return posts

# ========== LINK EXTRACTION ==========
def follow_and_extract_hosts(link_url):
    try:
        r = scraper.get(link_url, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        final = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("https://gofile.io/") or href.startswith("https://mega.nz/"):
                final.append(href)
        if not final:
            text = r.text
            final += re.findall(r'https?://gofile\.io/[A-Za-z0-9_\-]+', text)
            final += re.findall(r'https?://mega\.nz/[A-Za-z0-9_\-./#?=]+', text)
        return list(dict.fromkeys(final))
    except Exception as e:
        print("follow_and_extract_hosts error:", e)
        return []

def extract_final_links_for_post(post_url, is_tv, episode_code, quality):
    try:
        r = scraper.get(post_url, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        anchors = soup.find_all("a", href=True)
        candidates = []
        for a in anchors:
            href = a["href"]
            text = a.get_text(" ", strip=True).lower()
            if "get-to.link" in href or "download" in text:
                candidates.append(urljoin(post_url, href))
        found = []
        for link in candidates:
            hosts = follow_and_extract_hosts(link)
            for h in hosts:
                if h not in found:
                    found.append(h)
            if any("gofile" in x for x in found) and any("mega" in x for x in found):
                break
        return found
    except Exception as e:
        print("extract_final_links_for_post error:", e)
        return []

# ========== TELEGRAM FORMAT ==========
def format_message(title, final_links):
    links_text = "\n".join(final_links) if final_links else "(No gofile/mega links found)"
    return f"🦂 {title}\n\n🔗 DDLs:\n{links_text}"

# ========== MAIN LOOP ==========
def main():
    seen = load_seen()
    try:
        r = scraper.get(CHECK_URL, timeout=25)
        r.raise_for_status()
        posts = extract_homepage_posts(r.text)
        for p in posts:
            seen[p["url"]] = p["title"]
        print(f"[+] Initialized with {len(seen)} existing posts.")
    except Exception as e:
        print("Initial load failed:", e)

    send_telegram("🦂 PSA Premium Monitor v3.1 started")

    while True:
        try:
            r = scraper.get(CHECK_URL, timeout=25)
            r.raise_for_status()
            posts = extract_homepage_posts(r.text)

            for p in posts:
                title = p["title"]
                url = p["url"]
                update_txt = p.get("update", "")
                if url in seen:
                    if seen[url] == title:
                        continue

                is_tv, episode_code, quality = parse_update_line(update_txt or title)
                final_links = extract_final_links_for_post(url, is_tv, episode_code, quality)
                display_title = f"{title} — {update_txt}" if update_txt else title
                msg = format_message(display_title, final_links)
                send_telegram(msg)
                print("Sent:", display_title)
                seen[url] = title
                save_seen(seen)

        except Exception as e:
            print("Main loop error:", e)

        time.sleep(SLEEP_SEC)

# ✅ Safe entry point
if __name__ == "__main__":
    main()
