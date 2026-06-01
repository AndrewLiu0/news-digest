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
    OFFICIAL_PAGES, LOOKBACK_DAYS, ENABLE_OFFICIAL_SCRAPE
)
from utils import parse_article, canonicalize_url, is_within_lookback
from prompts import HARVESTER_PROMPT

load_dotenv()

class Article(BaseModel):
    title: str = Field(description="Headline of the news item")
    url: str = Field(description="Full URL to the specific news article.")
    reasoning: str = Field(description="Brief explanation of strategic relevance.")
    date: str = Field(description="Date found EXPLICITLY NEXT TO the article headline in the text. format YYYY-MM-DD.")

class ExtractionResults(BaseModel):
    articles: List[Article] = Field(default_factory=list)

structured_llm = base_model.with_structured_output(ExtractionResults)

def filter_markdown(text: str) -> str:
    if not text: return ""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[\s*\]\(.*?\)', '', text)
    lines = text.split('\n')
    
    cleaned = []
    # Broad date patterns
    date_regex = re.compile(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})|((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2})', re.I)
    
    # Identify "Today's Date" to specifically exclude it from headers
    today_variations = [
        datetime.now().strftime('%B %d, %Y'),
        datetime.now().strftime('%d %B %Y'),
        datetime.now().strftime('%Y-%m-%d'),
        "Published Time", "Updated at"
    ]
    
    for l in lines:
        l = l.strip()
        if not l: continue
        
        # If line is EXACTLY today's date or just a timestamp header, skip it to avoid confusing LLM
        if any(v.lower() in l.lower() for v in today_variations) and len(l) < 50:
            continue

        has_link = ('[' in l and '](' in l)
        is_long = len(l) > 40
        has_date = bool(date_regex.search(l))
        
        keywords = ["CHINA", "CHINESE", "US-", "U.S.", "USA", "TRADE", "SANCTION", "CHIP", "TAIWAN", "MILITARY", "BEIJING", "WASHINGTON"]
        has_keyword = any(k.upper() in l.upper() for k in keywords)
        
        if has_date or has_link:
            cleaned.append(l)
        elif is_long or has_keyword:
            cleaned.append(l)
            
    return "\n".join(cleaned[:1000])

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
    pages_to_process = OFFICIAL_PAGES
    
    print(f"Starting parallel Official Scrape for {len(pages_to_process)} pages using {MAX_WORKERS} workers...")

    def process_page(url):
        content = ""
        try:
            # 1. Primary: Local Scrape (Free)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            raw_resp = requests.get(url, headers=headers, timeout=10)
            if raw_resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw_resp.content, "html.parser")
                
                # Preserve <time> tags explicitly
                for time_tag in soup.find_all('time'):
                    time_text = time_tag.get_text(strip=True)
                    if time_text: time_tag.replace_with(f" (Date: {time_text}) ")
                        
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
                resp = requests.get(f"https://r.jina.ai/{url}", headers={"X-Return-Format": "markdown"}, timeout=30)
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
                    # --- HARD PYTHON DATE FILTER ---
                    if not is_within_lookback(art.date, art.url):
                        continue
                    collected.append(art)
            return collected
        except Exception as e:
            print(f"  [Error on {url}: {e}]")
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
                    print(f"  [Collected: {art.title[:50]}...]")

    print(f"Parallel collection complete: {len(all_collected)} items captured.")
    return {"raw_items": all_collected}
