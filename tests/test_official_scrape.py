import os
import json
import re
from dotenv import load_dotenv
from llm import model
from config import OFFICIAL_PAGES
from utils import fetch_with_retry

load_dotenv()

def test_scrape_and_extract(url):
    print(f"\n--- 📡 Testing Scrape: {url} ---")
    
    # 1. Use Jina Reader to get markdown
    jina_url = f"https://r.jina.ai/{url}"
    print(f"🔗 Fetching via Jina: {jina_url}")
    resp = fetch_with_retry(jina_url, max_retries=2)
    
    if not resp or resp.status_code != 200:
        print(f"❌ Failed to fetch {url} via Jina.")
        return

    print("✅ Successfully fetched markdown content.")
    content = resp.text[:12000] 
    print(f"DEBUG: Content snippet (first 1000 chars):\n{content[:1000]}\n---")
    
    # 2. Use LLM to extract relevant items via JSON prompt
    print("🧠 Asking LLM to extract US-China press releases...")
    
    prompt = (
        "You are an expert intelligence analyst. Below is a markdown capture of a government press release index.\n"
        f"SOURCE PAGE: {url}\n\n"
        "TASK:\n"
        "1. Identify the 3 most recent press releases or news items on this page.\n"
        "2. They MUST be related to US-China relations, Taiwan, South China Sea, or trade/sanctions.\n"
        "3. Provide the exact title and the FULL absolute URL for each.\n\n"
        "OUTPUT FORMAT:\n"
        "Return ONLY a valid JSON array of objects with keys 'title' and 'url'.\n"
        "Example: [{\"title\": \"Example\", \"url\": \"https://example.com\"}]\n\n"
        f"CONTENT:\n{content}"
    )
    
    try:
        res = model.invoke(prompt)
        # Extract JSON from potential markdown code blocks
        json_str = res.content
        if "```json" in json_str:
            json_str = re.search(r"```json\s*(.*?)\s*```", json_str, re.DOTALL).group(1)
        elif "```" in json_str:
             json_str = re.search(r"```\s*(.*?)\s*```", json_str, re.DOTALL).group(1)
        
        items = json.loads(json_str)
        if not items:
            print("⚠️  LLM found 0 relevant items on this page.")
        else:
            for i, item in enumerate(items, 1):
                print(f"  {i}. {item.get('title')}")
                print(f"     URL: {item.get('url')}")
    except Exception as e:
        print(f"❌ LLM Extraction Error: {e}")
        if 'res' in locals():
            print(f"RAW LLM RESPONSE: {res.content[:500]}...")

if __name__ == "__main__":
    # Test one US source and two Chinese sources
    test_targets = [
        "https://www.state.gov/press-releases/",
        "http://english.mofcom.gov.cn/article/news/",
        "https://www.fmprc.gov.cn/mfa_eng/xwfw_665399/s2510_665401/"
    ]
    
    for target in test_targets:
        test_scrape_and_extract(target)
