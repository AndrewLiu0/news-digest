import re
from typing import List
from pydantic import BaseModel, Field
from llm import fast_model as base_model
from state import WorkflowState
from config import ALLOWED_DOMAINS, MAX_RELEVANCE_CHECK, MAX_DEEP_DIVE_COUNT
from utils import canonicalize_url

class RelevanceCheck(BaseModel):
    # Minimal schema for maximum reliability
    is_relevant: str = Field(description="Answer 'YES' if strictly related to US-China relations, 'NO' otherwise.")

def deduplicate_and_filter(state: WorkflowState):
    """Node 1d: Merges results, deduplicates, and performs aggressive LLM-based date validation."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique_items = []
    
    raw_items = state.get("raw_items", [])
    print(f"Preprocessor received {len(raw_items)} total raw items")
    
    for item in raw_items:
        url = item.get("url", "")
        title = item.get("title", "")
        if not url or not title: continue
        
        canon = canonicalize_url(url)
        simple_title = re.sub(r'[^a-z0-9]', '', title.lower().split('-')[0].split('|')[0])
        
        if canon in seen_urls or simple_title in seen_titles:
            continue
            
        seen_urls.add(canon)
        if simple_title:
            seen_titles.add(simple_title)
        unique_items.append(item)

    # --- Aggressive Date Validation ---
    print(f"Starting parallel date validation for {len(unique_items)} unique items...")
    
    from datetime import datetime, timedelta
    from config import LOOKBACK_DAYS
    from llm import fast_model
    from pydantic import BaseModel, Field
    
    class DateExtraction(BaseModel):
        date_str: str = Field(description="YYYY-MM-DD format date.")

    date_extractor = fast_model.with_structured_output(DateExtraction)
    cutoff_date = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    today_str = datetime.now().strftime("%B %d, %Y")

    def validate_date(item):
        incoming_date = str(item.get("seendate") or "00000000")
        url = item.get("url", "")
        title = item.get("title", "")
        
        # 1. Forensic LLM Verification
        try:
            snippet = item.get("reasoning", "")[:1500]
            # Format incoming_date for the LLM
            formatted_discovery = incoming_date
            if len(incoming_date) == 8:
                formatted_discovery = f"{incoming_date[:4]}-{incoming_date[4:6]}-{incoming_date[6:]}"

            res = date_extractor.invoke([
                ("system", f"You are a Forensic Historian. Your goal is to identify the publication date.\n"
                            f"TODAY IS {today_str}.\n"
                            f"CUTOFF DATE IS {cutoff_date.strftime('%B %d, %Y')}.\n"
                            "RULES:\n"
                            "1. Look for explicit dates in the Title or Snippet.\n"
                            "2. If no explicit date is found in the text, check the 'Discovery Date' provided.\n"
                            "3. If the 'Discovery Date' looks plausible (e.g., not 0000-00-00), you may use it.\n"
                            "4. Return ONLY YYYY-MM-DD. If absolutely no date can be found or inferred, return '0000-00-00'."),
                ("human", f"Title: {title}\nSnippet: {snippet}\nDiscovery Date: {formatted_discovery}")
            ])
            
            from utils import get_date_object
            dt = get_date_object(res.date_str)
            
            # Fallback to incoming_date if LLM failed but incoming_date is valid
            if not dt and len(incoming_date) == 8 and incoming_date != "00000000":
                dt = get_date_object(incoming_date)
            
            if not dt:
                # One last try with Python on URL
                dt = get_date_object("", url)
                
            if not dt:
                print(f"  [PURGING (Unverifiable): {title[:50]}]")
                return None

            dt_just_day = datetime(dt.year, dt.month, dt.day)
            cutoff_just_day = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
            
            if dt_just_day < cutoff_just_day:
                print(f"  [PURGING (Old): {dt_just_day.strftime('%Y-%m-%d')} - {title[:50]}]")
                return None
            
            # If we reach here, it's verified and fresh
            item["seendate"] = dt_just_day.strftime("%Y%m%d")
            return item

        except Exception as e:
            print(f"  [Validation error for {title[:30]}: {e}]")
            return None

    validated = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(validate_date, unique_items))
        validated = [r for r in results if r is not None]

    # Sort by Tier, then by Date
    validated.sort(key=lambda x: (x.get("tier", 1), -int(x.get("seendate", "0")[:8] or "0")))
    
    print(f"Deduplication & Date Filter complete: {len(validated)} fresh items passed to relevance check")
    return {"processed_items": validated}

from concurrent.futures import ThreadPoolExecutor
import os
from datetime import datetime
from config import MAX_TOTAL_ARTICLES, MAX_DEEP_DIVE_COUNT, MAX_RELEVANCE_CHECK, MAX_WORKERS, ENABLE_RAW_SOURCE_LIST

def save_raw_sources(state: WorkflowState):
    """
    Node 2a-2: Saves the list of ALL discovered and deduped sources BEFORE any filtering.
    Only runs if ENABLE_RAW_SOURCE_LIST is True.
    """
    if not ENABLE_RAW_SOURCE_LIST:
        return {}

    items = state.get("processed_items", [])
    if not items:
        print("Save Raw Sources: No items to save.")
        return {}

    print(f"Saving {len(items)} raw discovered sources (backup)...")
    
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
    
    source_list = []
    for idx, item in enumerate(items, 1):
        source_list.append(f"{idx}. {item['title']}")
        source_list.append(f"Source: {item['url']}\n")
        
    filename = os.path.join(folder, f"sources_raw_{file_timestamp}.txt")
    with open(filename, "w") as f:
        f.write("\n".join(source_list))
        
    print(f"Raw source backup saved to: {filename}")
    return {}

def filter_relevance(state: WorkflowState):
    """Node 2: High-reliability LLM relevance check using GPT-4o-mini."""
    items_to_check = state.get("processed_items", [])
    
    if not items_to_check:
        return {"filtered_items": [], "additional_sources": []}

    print(f"Filter Node: Running parallel LLM relevance check for {len(items_to_check)} items using {MAX_WORKERS} workers...")
    
    structured_llm = base_model.with_structured_output(RelevanceCheck)
    
    def check_item(item):
        try:
            system_prompt = """You are a Senior Strategic Intelligence Analyst. 
Evaluate if this article provides STRATEGIC INTELLIGENCE for US-China bilateral relations.

CRITICAL INSTRUCTIONS (AUTO-REJECT IF TRUE):
1. REJECT Domestic Law Enforcement: Do NOT include drug busts, cartel sanctions, fentanyl trafficking, or individual criminal indictments (even if Chinese nationals are involved) UNLESS it is explicitly framed as a major state-level diplomatic action or sanction between Washington and Beijing.
2. REJECT Routine Regional News: Do NOT include routine military port visits (e.g., Indonesian Navy), local Asian coast guard meetings, or third-country infrastructure projects UNLESS the United States policy or a US-China conflict is the central focus.
3. REJECT Unrelated Foreign Policy: Do NOT include US actions against Iran, Russia, or other nations unless China's state involvement is the primary focus.

STRATEGIC (KEEP):
- Official readouts of high-level meetings (Trump, Xi, Ministers).
- Sanctions, tariffs, trade enforcement, and economic security.
- Military posture, Taiwan security, and South China Sea conflicts.
- Strategic technology competition (AI, Chips, NASA).
- Significant responses or "slams" between Foreign Ministries.

FLUFF (REJECT):
- Cultural events, language competitions, or "Chinese Bridge" news.
- Generic diplomatic travel (e.g., 'Ambassador visits a museum' or 'travels to unrelated region').
- Localized aid or bridge-building in third countries.
- Domestic youth innovation or purely local administrative news.

Only answer 'YES' if it has a direct impact on the bilateral strategic relationship."""

            human_text = f"Title: {item.get('title')}\nURL: {item.get('url')}\nSnippets: {item.get('reasoning', '')}"
            
            result = structured_llm.invoke([
                ("system", system_prompt),
                ("human", human_text)
            ])
            if result.is_relevant.strip().upper() == 'YES':
                return item
        except Exception as e:
            print(f"[LLM Error for {item.get('title')[:30]}: {e}]")
        return None

    all_relevant = []
    errors = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_item, items_to_check[:MAX_RELEVANCE_CHECK]))
        for r in results:
            if r is not None:
                all_relevant.append(r)
            else:
                # check_item returns None on both rejection AND error
                # but it prints a warning on error. 
                pass
        
    # Count errors by checking if we have fewer results than items_to_check
    # (Actually check_item always returns something unless it's a map failure)
    
    # --- NO FALLBACK ---
    if not all_relevant and items_to_check:
        print(f"[LLM Filter returned 0 relevant items out of {len(items_to_check[:MAX_RELEVANCE_CHECK])} checked]")
        # We do NOT fallback to top items anymore, as they might be old or junk.
        return {"filtered_items": []} 

    # Sort relevant items by Tier then Date
    all_relevant.sort(key=lambda x: (x.get("tier", 1), -int(x.get("seendate", "0")[:8] or "0")))

    print(f"Filter Result: Found {len(all_relevant)} relevant strategic items.")
    return {
        "filtered_items": all_relevant
    }

def strategic_deduplication(state: WorkflowState):
    """
    Node 2b: Strategic Triage.
    1. Retains ALL Government sources (.gov, .gov.cn, .mil).
    2. Groups items by topic and removes redundant news coverage.
    3. Retains news ONLY if it adds unique info (e.g. exclusive, source-based reporting).
    """
    items = state.get("filtered_items", [])
    if not items:
        print("Strategic Triage: No items to triage.")
        return {"filtered_items": [], "additional_sources": []}

    print(f"Strategic Triage: Evaluating {len(items)} relevant items for redundancy...")

    gov_items = []
    news_items = []

    for item in items:
        domain = item.get("domain", "").lower()
        url = item.get("url", "").lower()
        title = item.get("title", "").lower()
        # Government sources: .gov, .gov.cn, .mil, or specific gov domains
        is_gov = any(d in domain or d in url or d in title for d in [".gov", ".gov.cn", ".mil", "usembassy", "whitehouse"])
        if is_gov:
            gov_items.append(item)
        else:
            news_items.append(item)

    if not news_items:
        print(f"Strategic Triage: No news items to triage. Retaining all {len(gov_items)} Gov items.")
        return {"filtered_items": gov_items[:MAX_DEEP_DIVE_COUNT], "additional_sources": gov_items[MAX_DEEP_DIVE_COUNT:]}

    # Use LLM to triage news items against gov items
    from llm import fast_model as dedupe_model
    from pydantic import BaseModel, Field

    class TriageResult(BaseModel):
        retained_indices: List[int] = Field(description="Indices of news items that provide UNIQUE info not in gov items.")

    system_prompt = """You are a Strategic Editor. 
I will provide a list of OFFICIAL GOVERNMENT items and a list of NEWS items.
Your goal is to eliminate redundant news coverage to maximize signal-to-noise ratio.

RULES:
1. Always KEEP all Government items (they are for context here, do not exclude them).
2. For each NEWS item, determine if it adds SIGNIFICANT UNIQUE information (e.g., 'sources say', exclusive interview details, specific numbers, critical context) that is NOT in the government readouts.
3. If multiple news items cover the exact same thing (e.g., 'Trump says Xi agreed...'), pick only the BEST 1 or 2 (most comprehensive).
4. Be aggressive in removing standard news "echoes" of government press releases.
5. Return the indices of the NEWS items to keep."""

    # Batch news items if too many, but usually they are manageable
    # Construct the comparison text
    gov_text = "\n".join([f"GOV: {item.get('title')}" for item in gov_items[:50]]) # Context limit
    news_text = "\n".join([f"NEWS [{i}]: {item.get('title')}" for i, item in enumerate(news_items[:50])])

    final_news = []
    try:
        triage_llm = dedupe_model.with_structured_output(TriageResult)
        result = triage_llm.invoke([
            ("system", system_prompt),
            ("human", f"OFFICIAL ITEMS (CONTEXT):\n{gov_text}\n\nNEWS ITEMS TO TRIAGE:\n{news_text}")
        ])
        
        final_news = [news_items[i] for i in result.retained_indices if i < len(news_items)]
        print(f"Strategic Triage: Retained {len(final_news)} unique News items.")
    except Exception as e:
        print(f"[Strategic Triage error: {e}. Falling back to top news]")
        final_news = news_items[:10]
        
    all_curated = gov_items + final_news
    # Final Sort
    all_curated.sort(key=lambda x: (x.get("tier", 1), -int(x.get("seendate", "0")[:8] or "0")))

    top_items = all_curated[:MAX_DEEP_DIVE_COUNT]
    the_rest = all_curated[MAX_DEEP_DIVE_COUNT:]
    
    print(f"Strategic Triage complete: {len(top_items)} deep-dives, {len(the_rest)} additional sources.")
    return {
        "filtered_items": top_items,
        "additional_sources": the_rest
    }
