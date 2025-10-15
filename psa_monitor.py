#!/usr/bin/env python3
"""
PSA Premium Monitor v4.0 — Reuploads + Smart Detection Edition
---------------------------------------------------------------
✅ Homepage + Recently Reuploaded
✅ Uses cookies.txt (Premium)
✅ Sends 🆕 for new releases, 🔁 for reuploads
✅ Keeps PSA-style release names (no renaming)
✅ Extracts gofile & mega links only
"""

import os, re, time, json, requests, cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# === CONFIG ===
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4")
CHAT_ID     = os.getenv("CHAT_ID", "6145988808")
CHECK_URL   = "https://psa.wf/"
COOKIE_FILE = "cookies.txt"
SEEN_FILE   = "seen.json"
SLEEP_SEC   = 3  # every 1 second
# ==============

scraper = cloudscraper.create_scraper()
scraper.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://google.com",
    "Accept-Language": "en-US,en;q=0.9"
})

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# --- helper functions ------------------------------------------------------

def send_telegram(msg):
    """Send Telegram message safely."""
    try:
        requests.post(
            TG_API,
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "disable_web_page_preview": True,
                "parse_mode": "HTML"
            },
            timeout=10,
        )
    except Exception as e:
        print("Telegram error:", e)


def load_cookies():
    """Load cookies from cookies.txt (Netscape format)."""
    cookies = {}
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
        print(f"✅ Loaded {len(cookies)} cookies.")
    except Exception as e:
        print("❌ Failed to read cookies.txt:", e)
    return cookies


def verify_cookie(cookies):
    """Check if the PSA Premium cookie is valid."""
    for k, v in cookies.items():
        if "wordpress" in k:
            scraper.cookies.set(k, v, domain="psa.wf", path="/")
    try:
        r = scraper.get("https://psa.wf/wp-admin/profile.php", timeout=10)
        if "Profile" in r.text or "Log Out" in r.text:
            print("✅ Premium cookie valid.")
            return True
    except:
        pass
    print("⚠️ Cookie may be invalid or expired.")
    return False


def load_seen():
    try:
        return json.load(open(SEEN_FILE, "r", encoding="utf-8"))
    except:
        return {}


def save_seen(data):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except:
        pass


# --- scraping ---------------------------------------------------------------

def extract_homepage_posts(soup):
    posts = []
    for a in soup.select("article.post a.entry-title, h2.entry-title a"):
        title = a.get_text(" ", strip=True)
        href = urljoin(CHECK_URL, a["href"])
        posts.append({"title": title, "url": href, "type": "new"})
    return posts


def extract_reuploads(soup):
    posts = []
    h2 = soup.find("h2", string=re.compile("Recently Reuploaded", re.I))
    if h2:
        ul = h2.find_next("ul")
        if ul:
            for li in ul.find_all("li"):
                a = li.find("a", href=True)
                if a:
                    title = a.get_text(" ", strip=True)
                    href = urljoin(CHECK_URL, a["href"])
                    posts.append({"title": title, "url": href, "type": "reupload"})
    return posts


def extract_release_links(post_url):
    """Extract all releases and DDLs for a given post."""
    try:
        r = scraper.get(post_url, timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        releases = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            href = a["href"]

            if re.search(r"S\d{2}E\d{2}", text, re.I) and re.search(r"(720p|1080p|2160p|480p)", text, re.I):
                if "goto" in href:
                    final_links = extract_final_links(href)
                    if final_links:
                        releases.append((text, final_links))
        return releases

    except Exception as e:
        print("extract_release_links error:", e)
        return []


def extract_final_links(goto_url):
    """Follow goto → get-to.link → final DDL links."""
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


def format_message(title, releases, is_reupload):
    """Telegram message format (🆕 new / 🔁 reupload)."""
    header = "🔁" if is_reupload else "🆕"
    msg = f"{header} <b>{title}</b>\n"
    for name, links in releases:
        msg += f"\n🦂 {name} :\n"
        for l in links:
            msg += f"{l}\n"
    return msg.strip()


# --- main ------------------------------------------------------------------

def main():
    cookies = load_cookies()
    verify_cookie(cookies)

    seen = load_seen()
    send_telegram("🆕 <b>PSA Premium Monitor v4.0 started</b>")

    while True:
        try:
            html = scraper.get(CHECK_URL, timeout=20).text
            soup = BeautifulSoup(html, "html.parser")

            all_posts = extract_homepage_posts(soup) + extract_reuploads(soup)

            for p in reversed(all_posts):
                if p["url"] in seen:
                    continue

                print("🆕", p["title"])
                releases = extract_release_links(p["url"])
                msg = format_message(p["title"], releases, p["type"] == "reupload")
                send_telegram(msg)

                seen[p["url"]] = p["title"]
                save_seen(seen)

        except Exception as e:
            print("Loop error:", e)
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main()
