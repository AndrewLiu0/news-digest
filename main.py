from langgraph.graph import StateGraph, START, END

# Import modular components
from state import WorkflowState
from nodes.fetch import fetch_gdelt_doc, fetch_rss_feeds, fetch_tavily_search, fetch_google_news
from nodes.chinese_state_media import fetch_chinese_state_media
from nodes.collection_agent import run_collection_agent
from nodes.process import deduplicate_and_filter, filter_relevance, strategic_deduplication, save_raw_sources, clean_scraped_content
from nodes.scrape import scrape_with_jina
from nodes.publish import publish_markdown, publish_newsletter

# --- Graph Construction ---

builder = StateGraph(WorkflowState)

# Add Nodes
# DISCOVERY PHASE (Deterministic)
builder.add_node("fetch_gdelt", fetch_gdelt_doc)
builder.add_node("fetch_rss",   fetch_rss_feeds)
builder.add_node("fetch_tavily", fetch_tavily_search)
builder.add_node("fetch_google_news", fetch_google_news)
builder.add_node("fetch_chinese_state_media", fetch_chinese_state_media)
builder.add_node("fetch_official_pages", run_collection_agent)

# PROCESSING PHASE
builder.add_node("deduplicate_and_filter", deduplicate_and_filter)

# INTELLIGENCE PHASE (LLM Filter)
builder.add_node("filter_relevance",       filter_relevance)
builder.add_node("save_raw_sources",        save_raw_sources)
builder.add_node("strategic_deduplication", strategic_deduplication)

# DATA ACQUISITION PHASE (Verbatim Content)
builder.add_node("scrape_with_jina",       scrape_with_jina)
builder.add_node("clean_content",          clean_scraped_content)

# REPORTING PHASE
builder.add_node("publish_markdown",       publish_markdown)
builder.add_node("publish_newsletter",     publish_newsletter)

# --- Build Edges ---

# Start Discovery in Parallel
builder.add_edge(START, "fetch_gdelt")
builder.add_edge(START, "fetch_rss")
builder.add_edge(START, "fetch_tavily")
builder.add_edge(START, "fetch_google_news")
builder.add_edge(START, "fetch_chinese_state_media")
builder.add_edge(START, "fetch_official_pages")

# Feed all discovery results into the pre-processor
builder.add_edge("fetch_gdelt",  "deduplicate_and_filter")
builder.add_edge("fetch_rss",    "deduplicate_and_filter")
builder.add_edge("fetch_tavily", "deduplicate_and_filter")
builder.add_edge("fetch_google_news", "deduplicate_and_filter")
builder.add_edge("fetch_chinese_state_media", "deduplicate_and_filter")
builder.add_edge("fetch_official_pages", "deduplicate_and_filter")

# Linear path from Filter to Report
builder.add_edge("deduplicate_and_filter", "filter_relevance")
builder.add_edge("filter_relevance",       "save_raw_sources")
builder.add_edge("save_raw_sources",        "strategic_deduplication")

from config import ENABLE_SCRAPING, ENABLE_NEWSLETTER
if ENABLE_SCRAPING:
    builder.add_edge("strategic_deduplication", "scrape_with_jina")
    builder.add_edge("scrape_with_jina",       "clean_content")
    builder.add_edge("clean_content",          "publish_markdown")
    if ENABLE_NEWSLETTER:
        builder.add_edge("clean_content",      "publish_newsletter")
else:
    builder.add_edge("strategic_deduplication", "publish_markdown")
    if ENABLE_NEWSLETTER:
        builder.add_edge("strategic_deduplication", "publish_newsletter")

builder.add_edge("publish_markdown",       END)
if ENABLE_NEWSLETTER:
    builder.add_edge("publish_newsletter",     END)

# Final Agent Export
agent = builder.compile()
