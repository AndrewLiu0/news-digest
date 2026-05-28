#!/bin/bash

source .venv/bin/activate

python - <<'EOF' | tee gdelt_output.txt
import requests
import time

DOMAIN_ALLOWLIST = " OR ".join([
    # Tier 1: Official government primary sources
    "domain:home.treasury.gov", "domain:state.gov", "domain:whitehouse.gov",
    "domain:fmprc.gov.cn", "domain:xinhuanet.com", "domain:en.people.cn",
    # Tier 2: Wire services
    "domain:reuters.com", "domain:apnews.com",
    # Tier 3: Western majors
    "domain:ft.com", "domain:bloomberg.com", "domain:wsj.com",
    "domain:bbc.com", "domain:theguardian.com", "domain:nytimes.com",
    # Tier 4: International/geopolitical
    "domain:aljazeera.com", "domain:foreignpolicy.com", "domain:economist.com",
    # Tier 5: Asia-Pacific + China-focused English
    "domain:straitstimes.com", "domain:scmp.com", "domain:japantimes.co.jp",
    "koreatimes.com", "thenewslens.com", "cna.com.tw",
    "voachinese.com", "rfa.org", "chinatechnews.com",
    "globaltimes.cn",
])

SOURCE_TIER = {
    # Tier 1 — official government primary sources
    "home.treasury.gov": 1, "state.gov": 1, "whitehouse.gov": 1,
    "fmprc.gov.cn": 1, "xinhuanet.com": 1, "en.people.cn": 1,
    # Tier 2 — wire services
    "reuters.com": 2, "apnews.com": 2,
    # Tier 3 — western majors
    "ft.com": 3, "bloomberg.com": 3, "wsj.com": 3, "economist.com": 3,
    "bbc.com": 3, "theguardian.com": 3, "nytimes.com": 3,
    "aljazeera.com": 3, "foreignpolicy.com": 3,
    # Tier 4 — regional/Asia-Pacific
    "straitstimes.com": 4, "scmp.com": 4, "japantimes.co.jp": 4,
    "koreatimes.com": 4, "thenewslens.com": 4, "cna.com.tw": 4,
    "voachinese.com": 4, "rfa.org": 4, "chinatechnews.com": 4,
    "globaltimes.cn": 4,
}

# Fixed near20 syntax: all terms MUST be inside the same set of double quotes
# Removed periods from "U.S." inside near20 to avoid "phrase too short" errors
# Added "U S China" to match GDELT's space-tokenized "U.S."
DOC_QUERY     = '(near20:"United States China" OR near20:"US China" OR near20:"US Chinese" OR near20:"U S China" OR "US-China" OR "U.S.-China" OR "Sino-American")'
CONTEXT_QUERY = '"United States" "China"'

def fetch_with_retry(url, params, max_retries=10):
    for i in range(max_retries):
        try:
            # Increased timeout to 30s for VPN stability
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                try:
                    return r.json().get("articles", [])
                except Exception:
                    print(f"GDELT Parser error: {r.text[:100]}")
                    return []
            if r.status_code == 429:
                wait_time = 6
                print(f"GDELT 429 Rate Limit (Attempt {i+1}/{max_retries}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"Error {r.status_code}: {r.text[:100]}")
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"Network error (Attempt {i+1}/{max_retries}): {e}. Retrying in 5s...")
            time.sleep(5)
            continue
        except Exception as e:
            print(f"Unexpected exception: {e}")
            break
    return []

def fetch_doc(query, timespan):
    return fetch_with_retry("https://api.gdeltproject.org/api/v2/doc/doc", {
        "query": query, "timespan": timespan, "maxrecords": 250,
        "sort": "relevance", "format": "json",
    })

def fetch_context(query):
    return fetch_with_retry("https://api.gdeltproject.org/api/v2/context/context", {
        "query": query, "timespan": "72h", "maxrecords": 200, "format": "json",
    })

doc_articles     = fetch_doc(DOC_QUERY, "7d")
time.sleep(6) # mandated gap between calls
context_articles = fetch_context(CONTEXT_QUERY)

ALLOWED_DOMAINS = set(SOURCE_TIER.keys())

from urllib.parse import urlparse, urlunparse

def canonical_url(url):
    p = urlparse(url)
    return urlunparse(p._replace(query="", fragment=""))

seen_urls = set()
items = []
for a, api_source in [(a, "doc") for a in doc_articles] + [(a, "context") for a in context_articles]:
    url = a.get("url", "")
    domain = a.get("domain", "")
    canon = canonical_url(url)
    if not url or canon in seen_urls or domain not in ALLOWED_DOMAINS:
        continue
    seen_urls.add(canon)
    items.append({**a, "api_source": api_source, "tier": SOURCE_TIER.get(domain, 5)})

items.sort(key=lambda x: x["tier"])

print(f"DOC: {len(doc_articles)} | Context: {len(context_articles)} | After dedup: {len(items)}\n")

for a in items:
    print(f"[T{a['tier']}] [{a.get('sourcecountry','')}] [{float(a.get('tone',0)):+.1f}] [{a.get('api_source','')}] {a.get('title','')}")
    print(f"  {a.get('domain','')} | {a.get('seendate','')}")
    print(f"  {a.get('url','')}")
    print()
EOF
