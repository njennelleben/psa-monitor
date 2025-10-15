#!/usr/bin/env python3
"""
PSA Monitor v3.0

Smartly targets episode/quality from homepage UPDATE text

Follows nested links (episode -> quality -> download -> get-to.link)

Extracts only gofile.io and mega.nz final links

Sends Telegram message in your requested format


Requirements:
pip install requests cloudscraper beautifulsoup4
(Works on VPS/Railway; put your cookie export file all_cookies.txt in same folder)
"""

import time
import json
import re
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urljoin
import requests
import os
import os

# Load PSA Premium cookie from Railway environment variables
cookie_name = os.getenv("PSA_COOKIE_NAME")
cookie_value = os.getenv("PSA_COOKIE_VALUE")

if cookie_name and cookie_value:
    scraper.cookies.set(cookie_name, cookie_value, domain="psa.wf", path="/")
    print("✅ PSA Premium cookie added successfully")
else:
    print("⚠️ PSA cookie not found — continuing without premium login")

========== CONFIG ==========

BOT_TOKEN   = "8483644919:AAHPam6XshOdY7umlhtunnLRGdgPTETvhJ4"
CHAT_ID     = "6145988808"
CHECK_URL   = "https://psa.wf/"
SLEEP_SEC   = 1                 # default check interval (seconds)
COOKIE_FILE = "all_cookies.txt" # exported Netscape cookie file you used earlier
SEEN_FILE   = "seen_v3.json"

============================

---------------- helpers ----------------

scraper = cloudscraper.create_scraper()
scraper.headers.update({
"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
"Referer": "https://google.com",
"Accept-Language": "en-US,en;q=0.9"
})

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

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

def load_cookies_from_netscape(path):
"""
Reads a Netscape-style cookie file (what cookie-export extensions produce)
and returns a dict name->value. (We only pull cookie name/value pairs.)
"""
cookies = {}
try:
with open(path, "r", encoding="utf-8") as f:
for line in f:
line = line.strip()
if not line or line.startswith("#"):
continue
parts = line.split("\t")
if len(parts) >= 7:
name = parts[5] if len(parts) >= 7 else parts[-2]
value = parts[6] if len(parts) >= 7 else parts[-1]
cookies[name] = value
except FileNotFoundError:
print(f"[!] Cookie file not found: {path}")
except Exception as e:
print("Error reading cookie file:", e)
return cookies

put cookies into scraper session

cookie_map = load_cookies_from_netscape(COOKIE_FILE)
if cookie_map:
# cloudscraper supports requests-like cookie jars; just update header Cookie string for reliability
cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_map.items())
scraper.headers.update({"Cookie": cookie_header})
else:
print("[!] No cookies loaded. Premium-only content may not be available.")

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

---- parsing helpers ----

QUALITY_RE = re.compile(r'\b(2160p|1080p|720p|480p|4k|HD)\b', re.I)
EPISODE_RE = re.compile(r'\bS(\d{1,2})E(\d{1,2})\b', re.I)

def parse_update_line(text):
"""
From the homepage 'update' text, extract episode (SxxEyy) and the preferred quality (first quality found).
Returns (is_tv, episode_code or None, quality or None)
"""
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
"""
Returns a list of dicts: {title, url, update_text}
Looks for article blocks and captures caption/update lines if present.
"""
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
# caption / short update text
update_text = ""
caption = article.find("p", class_="caption")
if caption:
update_text = caption.get_text(" ", strip=True)
# fallback: sometimes update text is in span or small
if not update_text:
small = article.find(lambda tag: tag.name in ("small","span") and "update" in tag.get_text(" ", strip=True).lower())
if small:
update_text = small.get_text(" ", strip=True)
posts.append({"title": title, "url": href, "update": update_text})
return posts

---- final link extraction ----

def find_episode_section_soup(soup, episode_code):
"""
Try a few heuristics to find the DOM node containing the episode block (SxxEyy).
Returns the node (BeautifulSoup tag) or None.
"""
if not episode_code:
return None
# look for text nodes containing episode code
node = soup.find(lambda tag: tag.name in ("h3","h4","div","span","li")
and episode_code.lower() in tag.get_text(" ", strip=True).lower())
if node:
# prefer the parent block that contains links
parent = node
for _ in range(4):
if parent is None:
break
# if parent contains anchor(s)
if parent.find("a", href=True):
return parent
parent = parent.parent
return node
return None

def find_quality_links_in_node(node, quality=None):
"""
From a node (episode block or whole page), find anchors that match the requested quality.
If quality is None, returns anchors that look like download links or contain 'download' text.
"""
anchors = []
if node is None:
return anchors
# gather anchors with href
for a in node.find_all("a", href=True):
text = (a.get_text(" ", strip=True) or "").lower()
href = a["href"]
# normalize href
if href.startswith("/"):
href = urljoin(CHECK_URL, href)
# prefer anchors explicitly mentioning quality
if quality:
if quality.lower() in text or quality.lower() in href.lower():
anchors.append((text, href))
else:
# if no quality requested, consider anchors with 'download' or looks like file host
if re.search(r'(download|get[- ]link|ddl|gofile|mega|mirror|direct)', text, re.I) \
or re.search(r'(get-to.link|download|gofile|mega)', href, re.I):
anchors.append((text, href))
return anchors

def follow_and_extract_hosts(link_url):
"""
Fetch the provided intermediate link (download/get-to.link) and extract gofile & mega URLs from it.
Returns list of matching final URLs.
"""
try:
r = scraper.get(link_url, timeout=25)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")
final = []
for a in soup.find_all("a", href=True):
href = a["href"].strip()
if href.startswith("/"):
href = urljoin(link_url, href)
if href.startswith("https://gofile.io/") or href.startswith("https://mega.nz/"):
final.append(href)
# also, sometimes final links are in data attributes or plain text
# search for gofile/mega in the whole html as a fallback
if not final:
text = r.text
final += re.findall(r'https?://gofile.io/[A-Za-z0-9_-]+', text)
final += re.findall(r'https?://mega.nz/[A-Za-z0-9_-./#?=]+', text)
# dedupe preserving order
seen_l = []
out = []
for u in final:
if u not in seen_l:
seen_l.append(u)
out.append(u)
return out
except Exception as e:
print("follow_and_extract_hosts error:", e)
return []

def extract_final_links_for_post(post_url, is_tv, episode_code, quality):
"""
Smart flow:
- fetch post_url
- if TV: find episode block, locate quality link inside, follow it
- if Movie: look for quality links directly on page, follow matching ones
- fallback: find any download/get-to.link anchor and follow first
- return list of gofile/mega links (may be empty)
"""
try:
r = scraper.get(post_url, timeout=25)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

candidate_links = []  

    if is_tv and episode_code:  
        # find episode block  
        node = find_episode_section_soup(soup, episode_code)  
        if node:  
            # prefer anchors inside the episode block matching quality  
            if quality:  
                candidate_links = [href for (_, href) in find_quality_links_in_node(node, quality=quality)]  
            # fallback: any download-like anchors in the episode block  
            if not candidate_links:  
                candidate_links = [href for (_, href) in find_quality_links_in_node(node, quality=None)]  
    else:  
        # movie: find anchors on page matching quality  
        if quality:  
            candidate_links = [href for (_, href) in find_quality_links_in_node(soup, quality=quality)]  
        if not candidate_links:  
            candidate_links = [href for (_, href) in find_quality_links_in_node(soup, quality=None)]  

    # final fallback: global search for any 'get-to.link' href  
    if not candidate_links:  
        for a in soup.find_all("a", href=True):  
            href = a["href"]  
            if href.startswith("/"):  
                href = urljoin(post_url, href)  
            if "get-to.link" in href or "getto.link" in href or "getto.link" in href:  
                candidate_links.append(href)  

    # follow each candidate (stop early if we find gofile/mega)  
    found = []  
    for cand in candidate_links:  
        hosts = follow_and_extract_hosts(cand)  
        for h in hosts:  
            if h not in found:  
                found.append(h)  
        # if we have both gofile and mega, we can stop early  
        has_gofile = any("gofile.io" in x for x in found)  
        has_mega = any("mega.nz" in x for x in found)  
        if has_gofile and has_mega:  
            break  

    return found  

except Exception as e:  
    print("extract_final_links_for_post error:", e)  
    return []

---------------- main loop ----------------

def format_message(title, final_links):
# title already contains the update text in homepage form (kept tidy)
if final_links:
links_text = "\n".join(final_links)
else:
links_text = "(No gofile/mega links found)"
return f"🦂 {title}\n\n🔗 DDLs:\n{links_text}"

def main():
seen = load_seen()
# initial bootstrap
try:
r = scraper.get(CHECK_URL, timeout=25)
r.raise_for_status()
posts = extract_homepage_posts(r.text)
for p in posts:
seen[p["url"]] = p["title"]  # mark existing as seen
print(f"Initialized, known items: {len(seen)}")
except Exception as e:
print("Initial load failed:", e)

send_telegram("🦂 PSA Premium Monitor v3.0 started")  

while True:  
    try:  
        r = scraper.get(CHECK_URL, timeout=25)  
        r.raise_for_status()  
        posts = extract_homepage_posts(r.text)  

        # iterate oldest->newest so new ones are processed in order  
        for p in posts:  
            title = p["title"]  
            url = p["url"]  
            update_txt = p.get("update", "")  
            if url in seen:  
                # if title changed (update text changed), treat as update  
                if seen[url] != title:  
                    # updated entry — handle similarly as new  
                    pass  
                else:  
                    continue  

            # parse update text to know which episode/quality to target  
            is_tv, episode_code, quality = parse_update_line(update_txt or title)  
            # If quality is like '720p-1080p', QUALITY_RE picks first occurrence; that's intended.  
            # If quality is None, we will fallback to first download we find.  

            # Attempt to extract final links (gofile/mega) following nested links  
            final_links = extract_final_links_for_post(url, is_tv, episode_code, quality)  

            # format title to include update bits for clarity (e.g., "FBI — S08E01.720p...")  
            display_title = title  
            if update_txt:  
                # prefer to show the update fragment if it contains quality/episode info  
                display_title = f"{title} — {update_txt}"  

            msg = format_message(display_title, final_links)  
            send_telegram(msg)  
            print("Sent:", display_title)  

            # mark seen (store the current title so future title-changes are detected)  
            seen[url] = title  
            save_seen(seen)  

    except Exception as e:  
        print("Main loop error:", e)  

    time.sleep(SLEEP_SEC)

if name == "main":
main()
