import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import time

# --- Strict Timeline Sources Test List ---
RSS_FEEDS = [
    "https://www.whitehouse.gov/briefing-room/feed/",
    "https://www.state.gov/feed/",
    "https://home.treasury.gov/news/press-releases.xml",
    "https://www.commerce.gov/news/press-releases/rss.xml",
    "https://www.justice.gov/news/press-releases.xml",
    "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945",
    "https://www.dhs.gov/rss/news-releases.xml",
    "https://ustr.gov/rss.xml",
    "https://rsshub.app/fmprc/mfa_eng", 
    "https://rsshub.app/mofcom/article/m",
    "https://news.google.com/rss/search?q=China+when:24h&hl=en-US&gl=US&ceid=US:en"
]

KEYWORDS = ["US", "U.S.", "CHINA", "CHINESE", "TAIWAN", "SINO", "BEIJING", "WASHINGTON", "XI", "TRUMP"]

def fetch_with_retry(url, max_retries=2):
    for i in range(max_retries):
        try:
            print(f"Testing: {url[:70]}...", end=" ", flush=True)
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                print("[OK]")
                return resp
            print(f"[Error {resp.status_code}]")
        except Exception as e:
            print(f"[Failed: {e}]")
        if i < max_retries - 1: time.sleep(1)
    return None

def test_feeds():
    print(f"--- Strict Timeline Sources Validation at {datetime.now().isoformat()} ---\n")
    
    for url in RSS_FEEDS:
        resp = fetch_with_retry(url)
        if not resp: continue
            
        try:
            root = ET.fromstring(resp.content)
            # Handle both RSS 2.0 and Atom
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
                
            if not items:
                print("    [EMPTY] Feed reached but contains 0 items.\n")
                continue
                
            first_item = items[0]
            title_node = first_item.find("title") or first_item.find("{http://www.w3.org/2005/Atom}title")
            title = title_node.text if title_node is not None else "No Title"
            
            pub_date = "No Date"
            for date_tag in ["pubDate", "published", "{http://www.w3.org/2005/Atom}published", "lastBuildDate"]:
                node = first_item.find(date_tag) or root.find(f".//{date_tag}")
                if node is not None:
                    pub_date = node.text
                    break
            
            print(f"    [LIVE] Latest Item: {title[:60]}...")
            print(f"           Date: {pub_date}")
            
            matches = 0
            for item in items[:15]: 
                tnode = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
                ititle = tnode.text if tnode is not None else ""
                if any(k in ititle.upper() for k in KEYWORDS):
                    matches += 1
            print(f"    [SIGNAL] {matches}/15 recent items match keywords.\n")
            
        except Exception as e:
            print(f"    [PARSE ERROR] {e}\n")

if __name__ == "__main__":
    test_feeds()
