import os
import json
import requests
import re
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from llm import fast_model as base_model
from config import (
    OFFICIAL_PAGES, LOOKBACK_DAYS, ENABLE_OFFICIAL_SCRAPE,
    MAX_PAGE_CONTENT_CHARS, JINA_TIMEOUT
)
from utils import parse_article, canonicalize_url, is_within_lookback

load_dotenv()

class Article(BaseModel):
    title: str = Field(description="Headline of the news item")
    url: str = Field(description="Full URL to the article")
    reasoning: str = Field(description="Brief explanation of why this is relevant to US-China relations")
    date: str = Field(description="Date found EXPLICITLY NEXT TO the article snippet. If no date is written right next to the title, YOU MUST LEAVE THIS BLANK OR SAY 'Unknown'.")

class ExtractionResults(BaseModel):
    articles: List[Article] = Field(default_factory=list)

structured_llm = base_model.with_structured_output(ExtractionResults)

def filter_markdown(text: str) -> str:
    if not text: return ""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[\s*\]\(.*?\)', '', text)
    lines = text.split('\n')
    
    cleaned = []
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for l in lines:
        l = l.strip()
        if not l: continue
        
        has_link = ('[' in l and '](' in l)
        is_long = len(l) > 40
        has_date = any(m in l for m in months) and re.search(r'\d{2,4}', l)
        
        if has_link or is_long or has_date:
            cleaned.append(l)
            
    return "\n".join(cleaned[:500])

from concurrent.futures import ThreadPoolExecutor

def run_collection_agent(state):
    """
    Scrapes targeted official pages in parallel. Enforces strict Python-based date filtering.
    """
    if not ENABLE_OFFICIAL_SCRAPE:
        return {"raw_items": []}

    from config import MAX_WORKERS
    all_collected = []
    seen_urls = set()
    
    # Process all official pages
    pages_to_process = OFFICIAL_PAGES
    
    print(f"🚀 Starting parallel Official Scrape for {len(pages_to_process)} pages using {MAX_WORKERS} workers...")

    def process_page(url):
        content = ""
        try:
            # 1. Primary: Local Scrape with BeautifulSoup (Free)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.content, "html.parser")
                # Convert links to markdown format to preserve URLs for LLM extraction
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True)
                    if text:
                        # Reconstruct full URL if relative
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
                # print(f"  ⚠️ Falling back to Jina for {url}")
                resp = requests.get(f"https://r.jina.ai/{url}", headers={"X-Return-Format": "markdown"}, timeout=JINA_TIMEOUT)
                if resp.status_code == 200:
                    content = filter_markdown(resp.text)
            except Exception as e:
                print(f"  ❌ Fallback error on {url}: {e}")
                
        if not content: return []

        try:
            current_date = datetime.now().strftime('%B %d, %Y')
            system_prompt = (
                "You are a Strategic Intelligence Analyst.\n"
                f"TODAY'S DATE: {current_date}\n"
                "Extract individual news items, press releases, or hearings.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. Focus EXCLUSIVELY on US-China bilateral strategic items: Trade, Sanctions, Tech, Military, and High-Level Diplomacy.\n"
                "2. EXCLUDE general news, local human interest stories, or infrastructure projects in third countries (e.g., Africa, SE Asia) unless they mention a direct US conflict/policy.\n"
                "3. You MUST extract the EXACT DATE written next to or below the article title.\n"
                "4. DO NOT use the generic 'Published Time' at the top of the page.\n"
                "5. If there is no specific date for the article in the text, you MUST SKIP THE ARTICLE entirely."
            )
            
            result = structured_llm.invoke([
                ("system", system_prompt),
                ("human", f"PAGE CONTENT:\n{content[:MAX_PAGE_CONTENT_CHARS]}")
            ])

            collected = []
            for art in result.articles:
                # --- HARD PYTHON DATE FILTER ---
                if not is_within_lookback(art.date):
                    # print(f"  ❌ Discarded (Old): {art.title[:50]}... [{art.date}]")
                    continue
                    
                collected.append(art)
            return collected
        except Exception as e:
            print(f"  ❌ Error on {url}: {e}")
            return []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(process_page, pages_to_process))
        
    for page_articles in results:
        for art in page_articles:
            c_url = canonicalize_url(art.url)
            if c_url not in seen_urls:
                parsed = parse_article({
                    "title": art.title,
                    "url": art.url,
                    "reasoning": art.reasoning,
                    "seendate": art.date
                }, "official_scrape")
                
                if parsed:
                    all_collected.append(parsed)
                    seen_urls.add(c_url)
                    print(f"  ✅ Collected: {art.title[:50]}...")

    print(f"✅ Parallel collection complete: {len(all_collected)} items captured.")
    return {"raw_items": all_collected}

