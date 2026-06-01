import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
import requests
import time
from email.utils import parsedate_to_datetime
from config import SOURCE_TIER, ALLOWED_DOMAINS, LOOKBACK_DAYS

def fetch_with_retry(url: str, params: dict = None, max_retries: int = 10) -> requests.Response:
    """Robust fetcher with exponential backoff and connection error handling"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    for i in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                return response
            if response.status_code == 429:
                time.sleep(10)
                continue
            break
        except requests.exceptions.RequestException:
            time.sleep(5)
            continue
    return None

def get_date_object(date_str: str, url: str = "") -> datetime:
    """Standardizes date parsing from various strings and URLs."""
    dt = None
    
    if not date_str or date_str == "Unknown" or "0000" in date_str:
        # If no date string, we'll try the URL immediately
        pass
    else:
        # 1. Try email.utils (Standard RSS/Web format: Wed, 27 May 2026...)
        try:
            dt = parsedate_to_datetime(date_str)
            dt = dt.replace(tzinfo=None)
        except:
            pass

        if not dt:
            # 2. Try ISO-like extraction (2026-05-11 or 20260511)
            date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
            match = re.search(r'(\d{4})[-\s/]?(\d{1,2})[-\s/]?(\d{1,2})', date_str_clean)
            if match:
                try:
                    dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                except ValueError: pass
                
        if not dt:
            # 3. Try common Month Day, Year formats
            date_str_clean = date_str.split(" - ")[0].split(" | ")[0].strip()
            for fmt in ("%B %d, %Y", "%d %B %Y", "%Y-%m-%d", "%Y/%m/%d", "%B %d %Y"):
                try:
                    dt = datetime.strptime(date_str_clean, fmt)
                    break
                except ValueError: continue

        if not dt:
            # 4. Handle cases with NO YEAR (e.g., "May 21")
            current_year = datetime.now().year
            for fmt in ("%B %d", "%d %B"):
                try:
                    dt = datetime.strptime(date_str_clean, fmt).replace(year=current_year)
                    if dt > datetime.now() + timedelta(days=2):
                        dt = dt.replace(year=current_year - 1)
                    break
                except ValueError: continue
                    
    # 5. URL EXTRACTION (The "Gold Standard")
    if not dt and url:
        url_lower = url.lower()
        # Pattern A: /2026/05/11/ or /2026-05-11/
        match = re.search(r'[/-](\d{4})[/-](\d{1,2})[/-](\d{1,2})[/-]', url_lower)
        if not match: 
             match = re.search(r'[/-](\d{4})[/-](\d{1,2})[/-](\d{1,2})', url_lower)
        
        if match:
            try:
                dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError: pass
        
        if not dt:
            # Pattern B: /2026/may/11/ (Alphabetical months - common in USTR)
            month_map = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
            match = re.search(r'[/-](\d{4})/([a-z]{3,9})/(\d{1,2})', url_lower)
            if not match:
                match = re.search(r'[/-](\d{4})/([a-z]{3,9})[/-]', url_lower)
            
            if match:
                try:
                    y = int(match.group(1))
                    m_str = match.group(2)[:3]
                    if m_str in month_map:
                        d = int(match.group(3)) if len(match.groups()) > 2 else 1
                        dt = datetime(y, month_map[m_str], d)
                except: pass
            
        if not dt:
            # Pattern C: YYYYMMDD in URL
            match = re.search(r'[/-](\d{4})(\d{2})(\d{2})[/-]', url_lower)
            if not match:
                match = re.search(r'[/-](\d{8})[/-]', url_lower)
            
            if match:
                ds = match.group(1) if len(match.group(1)) == 8 else match.group(1)+match.group(2)+match.group(3)
                try:
                    dt = datetime.strptime(ds, "%Y%m%d")
                except ValueError: pass

    return dt

def is_within_lookback(date_str: str, url: str = "") -> bool:
    """Strict Python check for the date window."""
    dt = get_date_object(date_str, url)
    if not dt:
        return False
        
    cutoff = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    return dt >= cutoff

def parse_article(a: dict, api_source: str) -> dict:
    """Standardizes metadata and enforces strict Official Domain + Date filtering."""
    url = a.get("url", "")
    title = a.get("title", "").strip()
    
    if not title or len(title.split()) < 2:
        return None
            
    p = urlparse(url)
    domain = p.netloc.replace("www.", "").lower()
    
    is_allowed = False
    for allowed in ALLOWED_DOMAINS:
        if domain == allowed or domain.endswith("." + allowed):
            is_allowed = True
            break
            
    is_special = (
        (api_source == "google_news" and "google.com" in domain) or
        (api_source == "chinese_state_media")
    )
    
    if not is_allowed and not is_special:
        return None
    
    raw_date = a.get("seendate", "")
    dt = get_date_object(raw_date, url)
    
    if api_source in ["gdelt", "tavily", "rss", "official_scrape", "chinese_state_media"]:
        if not dt or not is_within_lookback(raw_date, url):
            return None
    
    if api_source == "google_news" and raw_date:
        if dt and not is_within_lookback(raw_date, url):
            return None
    
    if dt:
        std_date = dt.strftime("%Y%m%d")
    else:
        std_date = "00000000"
        
    return {
        "title":         title,
        "url":           url,
        "domain":        domain,
        "seendate":      std_date,
        "api_source":    api_source,
        "tier":          SOURCE_TIER.get(domain, 1),
        "reasoning":     a.get("reasoning", "")
    }

def canonicalize_url(url: str) -> str:
    """Strips tracking parameters and fragments from URLs for deduplication"""
    p = urlparse(url)
    return urlunparse(p._replace(query="", fragment=""))
