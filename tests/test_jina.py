import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(override=True)

def test_jina_extraction(url: str):
    """
    Tests Jina Reader (r.jina.ai) for clean Markdown extraction.
    Uses JINA_API_KEY from .env to bypass IP-based blocks.
    """
    print(f"\n{'='*80}")
    print(f"TESTING URL: {url}")
    print(f"{'='*80}")
    
    # Jina Reader works by prepending https://r.jina.ai/ to the target URL
    jina_url = f"https://r.jina.ai/{url}"
    api_key = os.getenv("JINA_API_KEY")
    
    try:
        headers = {
            "X-Return-Format": "markdown" # Forces Markdown output
        }
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            print("Using JINA_API_KEY for authentication.")
        else:
            print("Warning: JINA_API_KEY not found. Using anonymous access (might be blocked by VPN).")
        
        response = requests.get(jina_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            content = response.text
            print(f"Extraction Successful!")
            print(f"Content Length: {len(content)} characters")
            print("-" * 40)
            print("PREVIEW (First 1000 chars):")
            print(content[:1000])
            print("-" * 40)
            
            # Save the full output to a file for manual inspection
            filename = "jina_test_output.md"
            with open(filename, "w") as f:
                f.write(content)
            print(f"Full content saved to: {filename}")
            
        else:
            print(f"Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_urls = [
        "https://www.reuters.com/world/china/white-house-quiet-china-ramps-up-trade-leverage-before-trump-xi-summit-2026-04-30/",
        "https://www.scmp.com/news/china/diplomacy/article/3261051/chinas-xi-jinping-urges-france-avoid-new-cold-war-stresses-strategic-autonomy",
        "https://www.aljazeera.com/news/2026/4/30/hormuz-effect-how-us-china-are-ramping-up-tensions-over-the-panama-canal"
    ]
    
    for url in test_urls:
        test_jina_extraction(url)
