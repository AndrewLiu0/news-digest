import os
import re
import time
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from tavily import TavilyClient
from config import (
    DOC_QUERY, CONTEXT_QUERY, GNEWS_QUERY, RSS_FEEDS, RSS_KEYWORDS, 
    ALLOWED_DOMAINS, ENABLE_GDELT, ENABLE_RSS, ENABLE_TAVILY,
    ENABLE_GOOGLE_NEWS, LOOKBACK_DAYS,
    TAVILY_MAX_RESULTS, GDELT_MAX_RECORDS, GNEWS_MAX_RESOLVE
)
from state import WorkflowState
from utils import fetch_with_retry, parse_article

def fetch_tavily_search(state: WorkflowState):
    """Fetches search results via DuckDuckGo (Free) with Tavily (Paid) as fallback"""
    if not ENABLE_TAVILY:
        return {"raw_items": []}
    
    queries = [
        "US China bilateral relations diplomacy",
        "US China trade economic policy tariffs",
        "US China technology export controls semiconductor",
        "US China military defense security",
        "US State Department China policy",
        "Chinese Foreign Ministry United States statements",
        "US China artificial intelligence AI competition",
        "US China Indo-Pacific Taiwan Strait South China Sea",
        "US Congress legislation China Select Committee",
        "US Treasury OFAC sanctions Chinese entities",
        "US China cybersecurity espionage hacking",
        "US China agricultural trade phase one",
        "US China climate change cooperation energy"
    ]
    
    parsed = []
    
    # 1. Primary: DuckDuckGo Search (Free)
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        print("🔍 Running DuckDuckGo Search (Free) as primary search...")
        
        for q in queries:
            try:
                # Query without the site: operator since DDG blocks/fails it
                results = list(ddgs.text(q, max_results=30, safesearch='off', timelimit='w'))
                for r in results:
                    # parse_article natively drops anything not in ALLOWED_DOMAINS
                    item = parse_article({
                        "title": r.get('title', ''),
                        "url": r.get('href', ''),
                        "seendate": "" # Let parser handle date inference from URL or assume fresh
                    }, "duckduckgo")
                    if item:
                        parsed.append(item)
                time.sleep(1) # Be nice to DDG rate limits
            except Exception as e:
                print(f"  ⚠️ DDG Error on '{q}': {e}")
                
    except Exception as e:
        print(f"⚠️ DuckDuckGo initialization failed: {e}")

    # 2. Fallback: Tavily Search (Paid API)
    if not parsed:
        print("⚠️ DuckDuckGo returned 0 items. Falling back to Tavily Search (Paid)...")
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            print("⚠️ Tavily API Key missing, skipping fallback.")
            return {"raw_items": []}
            
        client = TavilyClient(api_key=api_key)
        
        from concurrent.futures import ThreadPoolExecutor
        
        def run_search(query):
            try:
                return client.search(
                    query=query,
                    topic="news",
                    days=LOOKBACK_DAYS,
                    max_results=TAVILY_MAX_RESULTS,
                    search_depth="advanced",
                    include_domains=list(ALLOWED_DOMAINS)
                )
            except Exception as e:
                print(f"Tavily search error on '{query}': {e}")
                return {'results': []}

        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            search_responses = list(executor.map(run_search, queries))
        
        for response in search_responses:
            for r in response.get('results', []):
                item = parse_article({
                    "title": r.get('title', ''),
                    "url": r.get('url', ''),
                    "seendate": r.get('published_date', '') # Use actual date if Tavily provides it
                }, "tavily")
                if item:
                    parsed.append(item)
                
    print(f"Search found {len(parsed)} official items")
    return {"raw_items": parsed}

def fetch_gdelt_doc(state: WorkflowState):
    """Fetches from GDELT DOC API (Strict Official Domains)"""
    if not ENABLE_GDELT:
        return {"raw_items": []}
    
    # Build a precise query for GDELT
    query = DOC_QUERY
    print(f"DEBUG: GDELT query: {query}")
    
    resp = fetch_with_retry(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={
            "query":      query,
            "timespan":   f"{LOOKBACK_DAYS}d",
            "maxrecords": GDELT_MAX_RECORDS,
            "sort":       "relevance",
            "format":     "json",
        }
    )
    if not resp: return {"raw_items": []}
    
    try:
        raw = resp.json().get("articles", [])
        parsed = []
        for a in raw:
            p = parse_article(a, "gdelt")
            if p:
                parsed.append(p)
        print(f"GDELT found {len(parsed)} official items")
        return {"raw_items": parsed}
    except Exception as e:
        print(f"GDELT DOC error: {e}")
        return {"raw_items": []}

def fetch_google_news(state: WorkflowState):
    """Fetches from Google News RSS (Targeting Official Domains)"""
    if not ENABLE_GOOGLE_NEWS:
        return {"raw_items": []}

    # Construct dynamic query using LOOKBACK_DAYS
    base_query = 'United States China (site:gov OR site:gov.cn OR site:reuters.com OR site:bloomberg.com OR site:foxnews.com OR site:cnbc.com)'
    query = f"{base_query} when:{LOOKBACK_DAYS}d"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200: return {"raw_items": []}
        
        root = ET.fromstring(resp.text)
        items = root.findall(".//item")
        
        raw_to_process = items[:GNEWS_MAX_RESOLVE]
        print(f"Google News: Resolving {len(raw_to_process)} URLs in parallel...")

        def resolve_url(item):
            gnews_url = item.find("link").text
            title = item.find("title").text
            
            pub_date_str = ""
            pubdate_elem = item.find("pubDate")
            if pubdate_elem is not None:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pubdate_elem.text)
                    pub_date_str = dt.strftime("%Y%m%d")
                except:
                    pub_date_str = pubdate_elem.text
                    
            try:
                # Use a shorter timeout for resolution to keep it snappy
                res = requests.get(gnews_url, headers=headers, allow_redirects=True, timeout=10)
                final_url = res.url
            except:
                final_url = gnews_url
                
            return parse_article({
                "title": title,
                "url": final_url,
                "seendate": pub_date_str 
            }, "google_news")

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(resolve_url, raw_to_process))
            parsed = [r for r in results if r is not None]
                
        print(f"Google News found {len(parsed)} official items")
        return {"raw_items": parsed}
    except Exception as e:
        print(f"Google News error: {e}")
        return {"raw_items": []}

def fetch_rss_feeds(state: WorkflowState):
    """Polls RSS feeds (Toggleable)"""
    if not ENABLE_RSS or not RSS_FEEDS:
        return {"raw_items": []}
    
    items = []
    for url in RSS_FEEDS:
        resp = fetch_with_retry(url, max_retries=3)
        if not resp: continue
        
        try:
            content = resp.text
            # Use regex to find all <item>...</item> blocks to avoid being killed by one malformed item
            raw_items = re.findall(r'<item>(.*?)</item>', content, re.DOTALL)
            
            for raw_item in raw_items:
                try:
                    # Clean the raw item XML
                    clean_item = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', raw_item)
                    # Wrap in a root tag for ET
                    root = ET.fromstring(f"<root>{clean_item}</root>")
                    
                    title = root.find("title").text if root.find("title") is not None else ""
                    link = root.find("link").text if root.find("link") is not None else ""
                    
                    if link and (any(k.upper() in title.upper() for k in RSS_KEYWORDS) or 
                                 any(k.upper() in link.upper() for k in RSS_KEYWORDS)):
                        # print(f"DEBUG: Match found: {title}")
                        extracted_date = None
                        
                        # 1. Try URL pattern: /art/2026/5/11/
                        date_match = re.search(r'/art/(\d{4})/(\d{1,2})/(\d{1,2})/', link)
                        if date_match:
                            y, m, d = date_match.groups()
                            extracted_date = f"{y}{m.zfill(2)}{d.zfill(2)}T000000Z"
                        
                        # 2. Try pubDate timestamp
                        pub_date_elem = root.find("pubDate")
                        if not extracted_date and pub_date_elem is not None and pub_date_elem.text:
                            if pub_date_elem.text.isdigit():
                                try:
                                    dt = datetime.fromtimestamp(int(pub_date_elem.text)/1000)
                                    extracted_date = dt.strftime("%Y%m%dT%H%M%SZ")
                                except: pass
                        
                        item = parse_article({
                            "title": title,
                            "url": link,
                            "seendate": extracted_date or "" # Leave blank if not found
                        }, "rss")
                        if item:
                            items.append(item)
                except:
                    continue # Skip this specific item if it's still too broken
                    
        except Exception as e:
            print(f"RSS error on {url}: {e}")
    return {"raw_items": items}
