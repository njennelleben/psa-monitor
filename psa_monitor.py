#!/usr/bin/env python3
"""
PSA Monitor v3.5 — Smart + Cookies.txt Edition
-----------------------------------------------
✅ Reads exported cookies.txt (Netscape format)
✅ Verifies PSA Premium login
✅ Detects TV/movie updates intelligently (SxxEyy + quality)
✅ Follows psa.wf/goto and get-to.link to final gofile/mega
✅ Sends formatted Telegram alerts
"""

import os
import re
import time
import json
import requests
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4")
CHAT_ID = os.getenv("CHAT_ID", "6145988808")
CHECK_URL = "https://psa.wf/"
COOKIE_FILE = "cookies.txt"
SEEN_FILE = "seen.json"
SLEEP_SEC = 5
# --------------

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Telegram ---
def send_telegram(msg):
    try:
        requests.post(
            TG_API + "/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
        )
    except Exception as e:
        print("Telegram error:", e)

# --- Cookie Loader ---
def load_cookies_from_file():
    cookies = {}
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value
        print(f"✅ Loaded {len(cookies)} cookies from file.")
    except Exception as e:
        print(f"[!] Failed to read {COOKIE_FILE}:", e)
    return cookies

def verify_cookie(cookies):
    for name, value in cookies.items():
        if "wordpress_sec_" in name or "wordpress_logged_in_" in name:
            scraper.cookies.clear()
            scraper.cookies.set(name, value, domain="psa.wf", path="/")
            try:
                r = scraper.get("https://psa.wf/wp-admin/profile.php", timeout=15)
                if "Profile" in r.text or "Log Out" in r.text:
                    print(f"✅ Cookie {name} is valid!")
                    send_telegram("🍪 <b>PSA Premium login verified.</b>")
                    return True
            except:
                pass
    print("❌ No valid login cookie found.")
    send_telegram("⚠️ <b>PSA cookie invalid or expired.</b>")
    return False

# --- Utils ---
def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2)

# --- Parsing helpers ---
QUALITY_RE = re.compile(r'\b(2160p|1080p|720p|480p|4k|HD)\b', re.I)
EPISODE_RE = re.compile(r'\bS\d{1,2}E\d{1,2}\b', re.I)

def parse_update_text(text):
    """Extract episode and quality from title or update line"""
    ep = EPISODE_RE.search(text)
    q = QUALITY_RE.search(text)
    return (ep.group(0).upper() if ep else None,
            q.group(0).lower() if q else None)

def extract_homepage_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for article in soup.find_all("article", class_=re.compile("post-")):
        h2 = article.find("h2", class_="entry-title")
        if not h2: continue
        a = h2.find("a", href=True)
        if not a: continue
        title = a.text.strip()
        url = urljoin(CHECK_URL, a["href"])
        caption = article.find("p", class_="caption")
        update = caption.get_text(strip=True) if caption else ""
        posts.append({"title": title, "url": url, "update": update})
    return posts

# --- Link extraction ---
def follow_redirects(url):
    try:
        r = scraper.get(url, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        final = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = urljoin(url, href)
            if "gofile.io" in href or "mega.nz" in href:
                final.append(href)
        return list(dict.fromkeys(final))
    except Exception as e:
        print("follow_redirects error:", e)
        return []

def extract_final_links(post_url, episode, quality):
    try:
        r = scraper.get(post_url, timeout=25)
        soup = BeautifulSoup(r.text, "html.parser")
        candidate_links = []

        # locate the section for this episode if TV
        if episode:
            section = soup.find(lambda tag: tag.name in ("h3", "div", "span") and episode.lower() in tag.get_text(" ", strip=True).lower())
            if section:
                for a in section.find_all("a", href=True):
                    t = a.get_text(" ", strip=True).lower()
                    if not quality or quality in t or "download" in t:
                        candidate_links.append(urljoin(post_url, a["href"]))
        else:
            # movie — look globally for quality
            for a in soup.find_all("a", href=True):
                t = a.get_text(" ", strip=True).lower()
                if not quality or quality in t or "download" in t:
                    candidate_links.append(urljoin(post_url, a["href"]))

        # follow any PSA redirect or get-to.link
        final_links = []
        for c in candidate_links:
            if "goto" in c or "get-to.link" in c:
                final_links.extend(follow_redirects(c))
        return list(dict.fromkeys(final_links))
    except Exception as e:
        print("extract_final_links error:", e)
        return []

# --- Main loop ---
def main():
    cookies = load_cookies_from_file()
    verify_cookie(cookies)

    seen = load_seen()
    send_telegram("🦂 <b>PSA Premium Smart Monitor v3.5 started.</b>")

    while True:
        try:
            r = scraper.get(CHECK_URL, timeout=25)
            posts = extract_homepage_posts(r.text)
            for p in posts:
                if p["url"] in seen:
                    continue

                title, update = p["title"], p.get("update", "")
                episode, quality = parse_update_text(update or title)
                final_links = extract_final_links(p["url"], episode, quality)

                msg = f"🦂 <b>{title}</b>"
                if episode or quality:
                    msg += f" — {episode or ''} {quality or ''}"
                msg += f"\n\n🔗 DDLs:\n" + ("\n".join(final_links) if final_links else "(No gofile/mega links found)")

                send_telegram(msg)
                print("✅ Sent:", title)

                seen[p["url"]] = title
                save_seen(seen)

        except Exception as e:
            print("Main loop error:", e)
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
