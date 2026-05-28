import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)

def test_tavily_full_text():
    api_key = os.getenv("TAVILY_API_KEY")
    client = TavilyClient(api_key=api_key)
    
    query = "US-China relations news"
    
    try:
        response = client.search(
            query=query,
            topic="news",
            days=7,
            max_results=5,
            search_depth="advanced",
            include_raw_content=True
        )
        
        for i, r in enumerate(response['results'], 1):
            print(f"\n\n{'='*80}")
            print(f"ARTICLE {i}: {r['title']}")
            print(f"URL: {r['url']}")
            print(f"{'='*80}\n")
            print(r.get('raw_content', 'No content found.'))
            print(f"\n{'*'*80}\n")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_tavily_full_text()
