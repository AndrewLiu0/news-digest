import os
from datetime import datetime
from state import WorkflowState
from config import MAX_TOTAL_ARTICLES, LOOKBACK_DAYS

def publish_source_list(state: WorkflowState):
    """Generates a simple source list TXT file."""
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Use filtered_items from strategic_deduplication
    items = state.get("filtered_items", [])
    
    total_limit = MAX_TOTAL_ARTICLES
    items = items[:total_limit]

    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
        
    source_list = []
    idx = 1
    for item in items:
        date_display = item.get("seendate", "00000000")
        if len(date_display) == 8:
            date_display = f"{date_display[:4]}-{date_display[4:6]}-{date_display[6:]}"
        source_list.append(f"{idx}. {item['title']}")
        source_list.append(f"Date: {date_display}")
        source_list.append(f"Source: {item['url']}\n")
        idx += 1
        
    source_filename = os.path.join(folder, f"sources_{file_timestamp}.txt")
    
    with open(source_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(source_list))

    print(f"Final source list saved to: {source_filename}")
    return {"source_list_path": source_filename}
