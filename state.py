import operator
from typing import Annotated
from typing_extensions import TypedDict

"""
- raw_items: articles fetched from sources, appended across parallel fetch nodes.
  We use operator.add here because multiple nodes (fetch_gdelt, fetch_rss, etc.) 
  all contribute to this single list.
- processed_items: deduped, domain-filtered items. Replaced, not appended.
- filtered_items: items that passed relevance check. Replaced to save memory.
- summaries: final analysis. Replaced.
- run_timestamp: when this workflow run started.
"""
class WorkflowState(TypedDict):
    # Keep Annotated only where we TRULY want to merge lists from different nodes
    raw_items: Annotated[list[dict], operator.add]
    
    # Remove operator.add from these to prevent memory leaks/bloat
    processed_items: list[dict]
    filtered_items: list[dict]
    additional_sources: list[dict]
    scraped_content: list[dict]
    executive_summary: str
    
    run_timestamp: str
