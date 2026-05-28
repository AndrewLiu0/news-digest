import os
from dotenv import load_dotenv
from tavily import TavilyClient
from config import ALLOWED_DOMAINS
from datetime import datetime

load_dotenv()

def test_tavily_gov_search():
    print("\n--- 🔍 Testing Tavily Search for Gov Press Releases ---")
    api_key = os.getenv("TAVILY_API_KEY")
    client = TavilyClient(api_key=api_key)
    
    # Target official domains from config
    domains = list(ALLOWED_DOMAINS)
    print(f"Target Domains: {domains[:5]}... ({len(domains)} total)")
    
    # Search for US-China relations specifically in these domains
    query = "US-China relations press release"
    
    try:
        print(f"Running search for: '{query}'")
        response = client.search(
            query=query,
            topic="news",
            days=3,
            max_results=10,
            search_depth="advanced",
            include_domains=domains
        )
        
        results = response.get('results', [])
        if not results:
            print("⚠️  No results found within these domains in the last 3 days.")
        else:
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r.get('title')}")
                print(f"     URL: {r.get('url')}")
                print(f"     Score: {r.get('score')}")
    except Exception as e:
        print(f"❌ Tavily Search Error: {e}")

if __name__ == "__main__":
    test_tavily_gov_search()
