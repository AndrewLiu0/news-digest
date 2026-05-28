import requests
import trafilatura

url = "https://chinaselectcommittee.house.gov/media/press-releases/moolenaar-calls-to-restrict-american-investment-in-china-s-biotechnology-companies"

print("--- TRAFILATURA ---")
downloaded = trafilatura.fetch_url(url)
if downloaded:
    content = trafilatura.extract(downloaded, include_tables=True, include_comments=False)
    print(content[:500])
else:
    print("Download failed.")

print("\n--- JINA ---")
try:
    resp = requests.get(f"https://r.jina.ai/{url}", headers={"X-Return-Format": "markdown"})
    print(resp.text[:500])
except Exception as e:
    print(f"Jina failed: {e}")

