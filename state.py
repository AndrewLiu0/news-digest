import operator
from typing import Annotated
from typing_extensions import TypedDict

class WorkflowState(TypedDict):
    # Discovery Phase
    raw_items: Annotated[list[dict], operator.add]
    
    # Processing Phase
    processed_items: list[dict]
    
    # Intelligence Phase (Lenient)
    filtered_items: list[dict]
    
    # Deep Scrape Phase
    scraped_content: list[dict]
    
    # Final Reporting
    additional_sources: list[dict]
    
    run_timestamp: str
