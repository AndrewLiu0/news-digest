import os
import requests
from datetime import datetime
from config import (
    STATE_MEDIA_PAGES, ENABLE_CHINESE_STATE_MEDIA, LOOKBACK_DAYS
)
from utils import parse_article, canonicalize_url, is_within_lookback
from nodes.collection_agent import structured_llm, filter_markdown
from prompts import HARVESTER_PROMPT

from concurrent.futures import ThreadPoolExecutor

def fetch_chinese_state_media(state):
    """
    Scrapes targeted Chinese state media pages in parallel.
    Uses the same LLM-based extraction logic as the official scrape.
    """
    if not ENABLE_CHINESE_STATE_MEDIA:
        return {"raw_items": []}

    from config import MAX_WORKERS
    all_collected = []
    seen_urls = set()
    jina_api_key = os.getenv("JINA_API_KEY")
    
    print(f"Starting parallel Chinese State Media Scrape for {len(STATE_MEDIA_PAGES)} pages using {MAX_WORKERS} workers...")

    def process_page(url):
        content = ""
        try:
            # 1. Primary: Local Scrape (Free)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            raw_resp = requests.get(url, headers=headers, timeout=10)
            if raw_resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw_resp.content, "html.parser")
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True)
                    if text:
                        href = a['href']
                        if href.startswith('/'):
                            from urllib.parse import urljoin
                            href = urljoin(url, href)
                        a.replace_with(f"[{text}]({href})")
                text = soup.get_text(separator="\n", strip=True)
                content = filter_markdown(text)
        except: pass
            
        if not content or len(content) < 300:
            try:
                headers = {"X-Return-Format": "markdown"}
                if jina_api_key:
                    headers["Authorization"] = f"Bearer {jina_api_key}"
                
                resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=30)
                if resp.status_code == 200:
                    content = filter_markdown(resp.text)
            except: pass
                
        if not content: return []

        try:
            current_date = datetime.now().strftime('%B %d, %Y')
            result = structured_llm.invoke([
                ("system", f"TODAY'S DATE IS {current_date}.\n" + HARVESTER_PROMPT),
                ("human", f"PAGE CONTENT:\n{content[:25000]}")
            ])

            collected = []
            if result and result.articles:
                for art in result.articles:
                    if not is_within_lookback(art.date, art.url):
                        continue
                    collected.append(art)
            return collected
        except Exception as e:
            print(f"  [Error on {url}: {e}]")
            return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(process_page, STATE_MEDIA_PAGES))
        
    for page_articles in results:
        for art in page_articles:
            c_url = canonicalize_url(art.url)
            if c_url not in seen_urls:
                parsed = parse_article({
                    "title": art.title,
                    "url": art.url,
                    "reasoning": art.reasoning,
                    "seendate": art.date 
                }, "chinese_state_media")
                
                if parsed:
                    all_collected.append(parsed)
                    seen_urls.add(c_url)

    print(f"Parallel Chinese State Media collection complete: {len(all_collected)} items captured.")
    return {"raw_items": all_collected}
