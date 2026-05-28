import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
import requests
import time
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
    
    if not date_str or date_str == "Unknown":
        return None

    # Clean date_str: remove time components and ordinal suffixes (1st, 2nd, 3rd, 4th...)
    # We look for common patterns to truncate
    date_str_clean = date_str.split(" - ")[0].split(" | ")[0].strip()
    
    # Remove ordinal suffixes: 1st, 2nd, 3rd, 4th...
    date_str_clean = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str_clean)

    # Further clean to take only first 3 parts if it's like "13 May 2026 07:22"
    parts = date_str_clean.split()
    if len(parts) > 3:
        # Check if the 4th part looks like a time (contains :)
        if ":" in parts[3]:
            date_str_clean = " ".join(parts[:3])

    # 1. Try ISO-like extraction from date_str (2026-05-11 or 20260511)
    match = re.search(r'(\d{4})[-\s/]?(\d{1,2})[-\s/]?(\d{1,2})', date_str_clean)
    if match:
        try:
            dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
        
    if not dt:
        # 2. Try "April 24, 2026" or "24 April 2026" or "2026/5/9"
        for fmt in ("%B %d, %Y", "%d %B %Y", "%Y-%m-%d", "%Y/%m/%d", "%Y/%n/%j", "%B %d %Y"):
            try:
                dt = datetime.strptime(date_str_clean, fmt)
                break
            except ValueError:
                continue
                    
    # 3. If still no date, try to extract from URL
    if not dt and url:
        url_lower = url.lower()
        # Pattern 1: /2026/05/11/ or /2026-05-11/
        match = re.search(r'/(\d{4})[/-](\d{1,2})[/-](\d{1,2})/', url_lower)
        if match:
            try:
                dt = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError: pass
        
        if not dt:
            # Pattern 2: /2026/may/11/ (Alphabetical months)
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            match = re.search(r'/(\d{4})/([a-z]{3,9})/(\d{1,2})/', url_lower)
            if match:
                try:
                    y = int(match.group(1))
                    m_str = match.group(2)[:3]
                    d = int(match.group(3))
                    if m_str in month_map:
                        dt = datetime(y, month_map[m_str], d)
                except ValueError: pass
            
        if not dt:
            # Pattern 3: /2026/may/ (No day, assume early month to be safe but check later)
            match = re.search(r'/(\d{4})/([a-z]{3,9})/', url_lower)
            if match:
                try:
                    y = int(match.group(1))
                    m_str = match.group(2)[:3]
                    if m_str in month_map:
                        dt = datetime(y, month_map[m_str], 1)
                except ValueError: pass

        if not dt:
            # Pattern 4: /2026/05/
            match = re.search(r'/(\d{4})/(\d{2})/', url_lower)
            if match:
                try:
                    dt = datetime(int(match.group(1)), int(match.group(2)), 1)
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
    
    # 1. Title Quality Gate
    if not title or len(title.split()) < 2:
        return None
            
    # 2. Domain Filter (Uses ALLOWED_DOMAINS from config)
    p = urlparse(url)
    domain = p.netloc.replace("www.", "").lower()
    
    # Check if domain or its parent domain is in ALLOWED_DOMAINS
    is_allowed = False
    for allowed in ALLOWED_DOMAINS:
        if domain == allowed or domain.endswith("." + allowed):
            is_allowed = True
            break
            
    # Trust special cases
    is_special = (
        (api_source == "google_news" and "google.com" in domain) or
        (api_source == "chinese_state_media")
    )
    
    if not is_allowed and not is_special:
        return None
    
    # 3. Strict Date Filter & Standardization
    raw_date = a.get("seendate", "")
    dt = get_date_object(raw_date, url)
    
    # Mandatory Date for most sources
    if api_source in ["gdelt", "tavily", "rss", "official_scrape", "chinese_state_media"]:
        if not dt or not is_within_lookback(raw_date, url):
            return None
    
    # For Google News, we trust the 'when:10d' query parameter if no date found, 
    # but still apply lookback if a date IS found.
    if api_source == "google_news" and raw_date:
        if dt and not is_within_lookback(raw_date, url):
            return None
    
    # Standardize seendate to YYYYMMDD for sorting
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
