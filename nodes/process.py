import re
from typing import List
from pydantic import BaseModel, Field
from llm import fast_model as base_model
from state import WorkflowState
from config import ALLOWED_DOMAINS, MAX_RELEVANCE_CHECK, MAX_DEEP_DIVE_COUNT
from utils import canonicalize_url

class RelevanceCheck(BaseModel):
    reasoning: str = Field(description="Brief explanation of why this item is or IS NOT strategic US-China intelligence.")
    is_relevant: str = Field(description="Answer 'YES' if it provides strategic value for US-China bilateral relations, 'NO' otherwise.")

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
        
        if canon in seen_urls:
            # print(f"  [DUP URL: {title[:30]}]")
            continue
        if simple_title and simple_title in seen_titles:
            # print(f"  [DUP TITLE: {title[:30]}]")
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
    
    class DateExtraction(BaseModel):
        date_str: str = Field(description="YYYY-MM-DD format date.")

    date_extractor = fast_model.with_structured_output(DateExtraction)
    cutoff_date = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    today_str = datetime.now().strftime("%B %d, %Y")

    def validate_date(item):
        incoming_date = str(item.get("seendate") or "00000000")
        url = item.get("url", "")
        title = item.get("title", "")
        
        # 0. TRUST Check: If date is already solid and recent, keep it.
        from utils import get_date_object
        dt_pre = get_date_object(incoming_date, url)
        
        # Skepticism: Google News RSS dates are often indexing dates, not publication dates.
        # We only TRUST it if it was successfully extracted from the URL (Gold Standard).
        is_google_news = item.get("api_source") == "google_news"
        dt_from_url = get_date_object("", url)
        
        # If we have a solid date and it's either NOT GNews, or it IS GNews but confirmed by URL
        if dt_pre and (not is_google_news or dt_from_url):
            dt_just_day = datetime(dt_pre.year, dt_pre.month, dt_pre.day)
            cutoff_just_day = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
            
            if dt_just_day < cutoff_just_day:
                return None # Old item
            
            item["seendate"] = dt_just_day.strftime("%Y%m%d")
            return item

        # 1. Forensic LLM Verification (Only if no solid date found yet)
        try:
            snippet = item.get("reasoning", "")[:1500]
            formatted_discovery = incoming_date
            if len(incoming_date) == 8:
                formatted_discovery = f"{incoming_date[:4]}-{incoming_date[4:6]}-{incoming_date[6:]}"

            res = date_extractor.invoke([
                ("system", f"You are a Forensic Historian. Identify publication date.\nTODAY IS {today_str}.\nCUTOFF IS {cutoff_date.strftime('%B %d, %Y')}.\nReturn YYYY-MM-DD."),
                ("human", f"Title: {title}\nSnippet: {snippet}\nDiscovery Date: {formatted_discovery}")
            ])
            
            dt = get_date_object(res.date_str)
            if not dt:
                dt = get_date_object("", url)
                
            if not dt:
                print(f"  [PURGING (Unverifiable): {title[:50]}]")
                return None

            dt_just_day = datetime(dt.year, dt.month, dt.day)
            cutoff_just_day = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
            
            if dt_just_day < cutoff_just_day:
                print(f"  [PURGING (Old): {dt_just_day.strftime('%Y-%m-%d')} - {title[:50]}]")
                return None
            
            item["seendate"] = dt_just_day.strftime("%Y%m%d")
            return item
        except Exception as e:
            print(f"  [Validation error for {title[:30]}: {e}]")
            return None

    validated = []
    from concurrent.futures import ThreadPoolExecutor
    from config import MAX_WORKERS
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(validate_date, unique_items))
        validated = [r for r in results if r is not None]

    validated.sort(key=lambda x: (x.get("tier", 1), -int(x.get("seendate", "0")[:8] or "0")))
    return {"processed_items": validated}

def save_pre_filtered_sources(state: WorkflowState):
    """
    Node 1e: Saves all deduplicated items BEFORE relevance filtering.
    """
    if not ENABLE_RAW_SOURCE_LIST:
        return {}

    items = state.get("processed_items", [])
    if not items:
        return {}

    print(f"💾 Saving {len(items)} pre-filtered sources...")
    
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
    
    source_list = []
    for idx, item in enumerate(items, 1):
        date_display = item.get("seendate", "00000000")
        if len(date_display) == 8:
            date_display = f"{date_display[:4]}-{date_display[4:6]}-{date_display[6:]}"
        source_list.append(f"{idx}. {item['title']}")
        source_list.append(f"Date: {date_display}")
        source_list.append(f"Source: {item['url']}\n")
        
    filename = os.path.join(folder, f"sources_pre_filtered_{file_timestamp}.txt")
    latest_filename = os.path.join(folder, "latest_pre_filtered.txt")
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(source_list))
        
    with open(latest_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(source_list))
        
    print(f"✅ Pre-filtered source list saved to: {filename}")
    return {}

import os
from datetime import datetime
from config import MAX_TOTAL_ARTICLES, MAX_DEEP_DIVE_COUNT, MAX_RELEVANCE_CHECK, MAX_WORKERS, ENABLE_RAW_SOURCE_LIST

def save_raw_sources(state: WorkflowState):
    """
    Node 2a-2: Saves the list of relevant sources AFTER relevance check but BEFORE strategic deduplication.
    """
    if not ENABLE_RAW_SOURCE_LIST:
        return {}

    items = state.get("filtered_items", [])
    if not items:
        return {}

    print(f"💾 Saving {len(items)} relevant sources before triage...")
    
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
    
    source_list = []
    for idx, item in enumerate(items, 1):
        date_display = item.get("seendate", "00000000")
        if len(date_display) == 8:
            date_display = f"{date_display[:4]}-{date_display[4:6]}-{date_display[6:]}"
        source_list.append(f"{idx}. {item['title']}")
        source_list.append(f"Date: {date_display}")
        source_list.append(f"Source: {item['url']}\n")
        
    filename = os.path.join(folder, f"sources_raw_{file_timestamp}.txt")
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(source_list))
        
    print(f"✅ Raw source list saved to: {filename}")
    return {}

from prompts import RELEVANCE_FILTER_PROMPT, TRIAGE_PROMPT

def filter_relevance(state: WorkflowState):
    """Node 2: Strategic relevance check."""
    items_to_check = state.get("processed_items", [])
    
    if not items_to_check:
        return {"filtered_items": []}

    print(f"Filter Node: Running parallel LLM relevance check for {len(items_to_check)} items...")
    
    structured_llm = base_model.with_structured_output(RelevanceCheck)
    
    def check_item(item):
        try:
            human_text = f"TITLE: {item.get('title')}\nSOURCE: {item.get('domain')}\nSNIPPET: {item.get('reasoning', '')}"
            
            result = structured_llm.invoke([
                ("system", RELEVANCE_FILTER_PROMPT),
                ("human", human_text)
            ])
            if result.is_relevant.strip().upper() == 'YES':
                item["reasoning"] = result.reasoning
                return item
        except Exception as e:
            print(f"[Filter Error for {item.get('title')[:30]}: {e}]")
        return None

    from concurrent.futures import ThreadPoolExecutor
    passed_items = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(check_item, items_to_check[:MAX_RELEVANCE_CHECK]))
        passed_items = [r for r in results if r is not None]
        
    print(f"Filter Result: Found {len(passed_items)} relevant strategic items.")
    return {"filtered_items": passed_items}

def strategic_deduplication(state: WorkflowState):
    """
    Node 2b: Strategic Triage.
    Removes near-identical redundant coverage while retaining all unique stories.
    """
    items = state.get("filtered_items", [])
    if not items:
        print("Strategic Triage: No items to triage.")
        return {"filtered_items": [], "additional_sources": []}

    print(f"Strategic Triage: Deduplicating {len(items)} relevant items...")

    from llm import fast_model as dedupe_model
    from pydantic import BaseModel, Field

    class TriageResult(BaseModel):
        retained_indices: List[int] = Field(description="Indices of items to keep. Only exclude items that are near-identical mirrors of another item in the list.")

    items_text = "\n".join([f"[{i}] ({item.get('domain', 'source')}): {item.get('title')}" for i, item in enumerate(items[:150])])

    final_retained = []
    try:
        triage_llm = dedupe_model.with_structured_output(TriageResult)
        result = triage_llm.invoke([
            ("system", TRIAGE_PROMPT),
            ("human", f"ITEMS TO TRIAGE:\n{items_text}")
        ])
        final_retained = [items[i] for i in result.retained_indices if i < len(items)]
        print(f"Strategic Triage: Retained {len(final_retained)} unique stories.")
    except Exception as e:
        print(f"[Strategic Triage error: {e}]")
        final_retained = items
        
    final_retained.sort(key=lambda x: (x.get("tier", 1), -int(x.get("seendate", "0")[:8] or "0")))
    
    return {
        "filtered_items": final_retained,
        "additional_sources": []
    }
