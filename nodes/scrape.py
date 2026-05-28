import os
import time
import requests
from state import WorkflowState
from config import JINA_TIMEOUT, DIRECT_TIMEOUT, MAX_DEEP_DIVE_COUNT, MAX_SCRAPE_SIZE_CHARS, SCRAPE_DELAY

def scrape_url(url_item, api_key):
    """Helper function to scrape a single URL. Uses Trafilatura (Local) first, then falls back to Jina/Tavily."""
    url = url_item.get("url", "")
    title = url_item.get("title", "")
    reasoning = url_item.get("reasoning", "")
    seendate = url_item.get("seendate", "00000000")
    if not url: return None
    
    # 1. PRIMARY: Local Scrape with Trafilatura (Free)
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            content = trafilatura.extract(downloaded, include_tables=True, include_comments=False)
            if content and len(content) > 500:
                return {"url": url, "content": content, "title": title, "seendate": seendate, "scrape_status": "trafilatura_local"}
    except Exception as e:
        pass # Silent fail to fallback
        
    # 2. FALLBACK 1: JINA FOR GOV DOMAINS ONLY (Paid)
    is_gov = any(domain in url for domain in [".gov", ".gov.cn", ".mil"])
    
    if is_gov:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {"X-Return-Format": "markdown", "X-No-Cache": "true"}
        if api_key: headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            time.sleep(SCRAPE_DELAY) 
            response = requests.get(jina_url, headers=headers, timeout=JINA_TIMEOUT)
            if response.status_code == 200 and len(response.text) > 500:
                return {"url": url, "content": response.text, "title": title, "seendate": seendate, "scrape_status": "jina_fallback"}
        except Exception as e:
            print(f"⚠️ Jina fallback error for {url}: {e}")

    # 3. FALLBACK 2: TAVILY FALLBACK (Paid)
    print(f"⚠️ Using Tavily fallback for {url}...")
    try:
        from tavily import TavilyClient
        t_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        t_res = t_client.search(query=url, include_raw_content=True, max_results=1)
        if t_res and t_res.get('results') and len(t_res['results'][0].get('raw_content', '')) > 500:
            return {"url": url, "content": t_res['results'][0]['raw_content'], "title": title, "seendate": seendate, "scrape_status": "tavily_fallback"}
    except Exception as e:
        print(f"⚠️ Tavily fallback failed for {url}: {e}")
            
    # 4. FINAL SNIPPET FALLBACK
    return {"url": url, "content": f"Full content scrape failed. Discovery Snippet:\n\n{reasoning}", "title": title, "seendate": seendate, "scrape_status": "snippet_only"}



from concurrent.futures import ThreadPoolExecutor

def scrape_with_jina(state: WorkflowState):
    """Node 4: Scrapes full content for the top items in parallel"""
    api_key = os.getenv("JINA_API_KEY")
    # Process top MAX_DEEP_DIVE_COUNT items
    items = state.get("filtered_items", [])[:MAX_DEEP_DIVE_COUNT]
    
    if not items:
        print("No items to scrape.")
        return {"scraped_content": []}

    from config import MAX_WORKERS
    print(f"🚀 Starting parallel scrape of {len(items)} items using {MAX_WORKERS} workers...")
    
    def scrape_task(item):
        return scrape_url(item, api_key)

    scraped_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(scrape_task, items))
        scraped_results = [r for r in results if r is not None]
        
    print(f"✅ Scraping complete: {len(scraped_results)} items successfully captured.")
    return {"scraped_content": scraped_results}

