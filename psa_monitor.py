#!/usr/bin/env python3
"""
PSA Premium Monitor v3.8 — Full Title + Reupload Support
--------------------------------------------------------
✅ Uses cookies.txt (Premium login)
✅ Detects new posts + "Recently Reuploaded" section
✅ Extracts full PSA release names (exact format)
✅ Follows /goto → get-to.link → final gofile/mega links
✅ Sends clean Telegram messages
"""

import os
import re
import time
import json
import requests
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4")
CHAT_ID = os.getenv("CHAT_ID", "6145988808")
CHECK_URL = "https://psa.wf/"
COOKIE_FILE = "cookies.txt"
SEEN_FILE = "seen.json"
SLEEP_SEC = 3
# ==============

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


# --- COOKIE HANDLING ---
def load_cookies_from_file():
    cookies = {}
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value
        print(f"✅ Loaded {len(cookies)} cookies from cookies.txt")
    except Exception as e:
        print("[!] Cookie load failed:", e)
    return cookies


def verify_cookie(cookies):
    for name, value in cookies.items():
        if "wordpress" in name:
            scraper.cookies.set(name, value, domain="psa.wf", path="/")

    try:
        r = scraper.get("https://psa.wf/wp-admin/", timeout=10)
        if any(k in r.text for k in ["Dashboard", "Logout", "Profile", "Users"]):
            print("✅ Premium cookie valid!")
            return True
        else:
            print("⚠️ Could not confirm login — continuing anyway.")
            return True  # continue even if unsure
    except Exception as e:
        print("Cookie test failed:", e)
    print("⚠️ Cookie test uncertain; proceeding.")
    return True


# --- TELEGRAM ---
def send_telegram(msg):
    try:
        requests.post(
            TG_API,
            data={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


# --- UTILITIES ---
def load_seen():
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f, indent=2)
    except:
        pass


# --- PARSING ---
def extract_homepage_posts(html):
    """Extract normal posts + reuploads."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    # Regular new posts
    for article in soup.find_all("article", class_=re.compile("post-")):
        h2 = article.find("h2", class_="entry-title")
        if not h2:
            continue
        a = h2.find("a", href=True)
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        href = urljoin(CHECK_URL, a["href"])
        posts.append({"title": title, "url": href, "type": "new"})

    # Recently reuploaded section
    reup_div = soup.find("div", id=re.compile("recently", re.I))
    if reup_div:
        for a in reup_div.find_all("a", href=True):
            title = a.get_text(" ", strip=True)
            href = urljoin(CHECK_URL, a["href"])
            posts.append({"title": f"♻️ Reupload — {title}", "url": href, "type": "reupload"})

    return posts


def extract_all_quality_links(post_url):
    """Extracts full PSA release names and DDLs."""
    try:
        r = scraper.get(post_url, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        results = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if "goto" in href and re.search(r"\b(480p|720p|1080p|2160p)\b", text, re.I):
                release_name = text.strip()
                final_links = extract_final_links(href)
                if final_links:
                    results.append((release_name, final_links))
        return results
    except Exception as e:
        print("extract_all_quality_links error:", e)
        return []


def extract_final_links(goto_url):
    """Follow PSA /goto/... → get-to.link → final gofile/mega links."""
    links = []
    try:
        r = scraper.get(goto_url, timeout=25, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "gofile.io" in href or "mega.nz" in href:
                links.append(href)
        if not links:
            found = re.findall(r'https?://(?:gofile\.io|mega\.nz)/[A-Za-z0-9_\-./#?=]+', r.text)
            links.extend(found)
        return list(dict.fromkeys(links))
    except Exception as e:
        print("extract_final_links error:", e)
        return []


def format_message(title, quality_links):
    """Formats message with exact release titles and links."""
    msg = f"🆕 <b>{title}</b>\n"
    for release_name, links in quality_links:
        msg += f"\n🦂 <b>{release_name}</b> :\n"
        for l in links:
            msg += f"{l}\n"
    return msg.strip()


# --- MAIN LOOP ---
def main():
    cookies = load_cookies_from_file()
    verify_cookie(cookies)

    seen = load_seen()
    send_telegram("🦂 <b>PSA Premium Monitor v3.8 started (with Reupload Support)</b>")

    while True:
        try:
            html = scraper.get(CHECK_URL, timeout=20).text
            posts = extract_homepage_posts(html)

            for p in reversed(posts):
                if p["url"] in seen:
                    continue
                print("🆕 Found new:", p["title"])
                quality_links = extract_all_quality_links(p["url"])
                if not quality_links:
                    continue
                msg = format_message(p["title"], quality_links)
                send_telegram(msg)
                seen[p["url"]] = p["title"]
                save_seen(seen)
        except Exception as e:
            print("Main loop error:", e)
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main()
