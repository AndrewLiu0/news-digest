import requests
import json
from config import DOC_QUERY, LOOKBACK_DAYS

def test_gdelt():
    query = DOC_QUERY
    print(f"Testing GDELT with query: {query}")
    
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query":      query,
        "timespan":   f"{LOOKBACK_DAYS}d",
        "maxrecords": 250,
        "sort":       "relevance",
        "format":     "json",
    }
    
    resp = requests.get(url, params=params)
    print(f"Status Code: {resp.status_code}")
    
    try:
        data = resp.json()
        articles = data.get("articles", [])
        print(f"Found {len(articles)} articles")
        for a in articles[:5]:
            print(f"- {a.get('title')} ({a.get('url')})")
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        print(f"Raw response: {resp.text[:500]}")

if __name__ == "__main__":
    test_gdelt()
