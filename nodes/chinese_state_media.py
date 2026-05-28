import os
import requests
from datetime import datetime
from config import (
    STATE_MEDIA_PAGES, ENABLE_CHINESE_STATE_MEDIA, LOOKBACK_DAYS,
    JINA_TIMEOUT, MAX_PAGE_CONTENT_CHARS
)
from utils import parse_article, canonicalize_url, is_within_lookback
from nodes.collection_agent import structured_llm, filter_markdown

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
    
    print(f"🚀 Starting parallel Chinese State Media Scrape for {len(STATE_MEDIA_PAGES)} pages using {MAX_WORKERS} workers...")

    def process_page(url):
        content = ""
        try:
            # 1. Primary: Local Scrape with BeautifulSoup (Free)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.content, "html.parser")
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
        except Exception as e:
            pass # Silent fail to fallback
            
        # 2. Fallback: Jina Reader (Paid/Rate Limited API)
        if not content or len(content) < 200:
            try:
                headers = {"X-Return-Format": "markdown"}
                if jina_api_key:
                    headers["Authorization"] = f"Bearer {jina_api_key}"
                
                resp = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=JINA_TIMEOUT)
                if resp.status_code == 200:
                    content = filter_markdown(resp.text)
            except Exception as e:
                print(f"  ❌ Fallback Error on {url}: {e}")
                
        if not content: return []

        try:
            current_date = datetime.now().strftime('%B %d, %Y')
            system_prompt = (
                "You are a Strategic Intelligence Analyst specializing in Chinese Media.\n"
                f"TODAY'S DATE: {current_date}\n"
                "Extract official statements or news related STRICTURELY to US-China bilateral strategic relations.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Focus on: Bilateral diplomacy, Trade/Tariffs, Tech Competition, and Military Security.\n"
                "2. EXCLUDE: Soft power stories, infrastructure in third countries (BRI general news), and purely domestic Chinese news.\n"
                "3. You MUST extract the EXACT DATE written next to or below the article title.\n"
                "4. DO NOT use the generic 'Published Time' at the top of the page.\n"
                "5. If there is no specific date for the article in the text, you MUST SKIP IT."
            )
            
            result = structured_llm.invoke([
                ("system", system_prompt),
                ("human", f"PAGE CONTENT:\n{content[:MAX_PAGE_CONTENT_CHARS]}")
            ])

            collected = []
            if result and result.articles:
                for art in result.articles:
                    if not is_within_lookback(art.date):
                        continue
                    collected.append(art)
            return collected
        except Exception as e:
            print(f"  ❌ Error on {url}: {e}")
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

    print(f"✅ Parallel Chinese State Media collection complete: {len(all_collected)} items captured.")
    return {"raw_items": all_collected}

