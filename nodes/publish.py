import os
import json
from datetime import datetime, timedelta
from state import WorkflowState
from config import MAX_TOTAL_ARTICLES, LOOKBACK_DAYS
from llm import reasoning_model

from nodes.document_utils import markdown_to_pdf, markdown_to_docx

def publish_newsletter(state: WorkflowState):
    """
    Node 6: Synthesizes all intelligence into a CCCW-style 'A Tale of Two Capitols' newsletter.
    Uses a chunked (Map-Reduce) approach to guarantee 100% exhaustive coverage without hitting LLM attention limits.
    """
    scraped = state.get("scraped_content", [])
    filtered = state.get("filtered_items", [])
    
    items_for_synthesis = []
    seen_urls = set()
    
    # Prioritize scraped content (richer detail)
    for i, s in enumerate(scraped):
        content_limit = 6000 # Balanced for deep detail without hitting OpenAI TPM rate limits
        items_for_synthesis.append({
            "title": s.get("title"),
            "url": s.get("url"),
            "date": s.get("seendate"),
            "content": s.get("content", "")[:content_limit]
        })
        seen_urls.add(s.get("url"))
        
    for f in filtered:
        if f.get("url") not in seen_urls:
            items_for_synthesis.append({
                "title": f.get("title"),
                "url": f.get("url"),
                "date": f.get("seendate"),
                "content": f.get("reasoning", "")
            })

    if not items_for_synthesis:
        print("No items for synthesis.")
        return {}

    # Calculate report dates
    today = datetime.now()
    today_str = today.strftime('%B %d, %Y')
    cutoff_date = today - timedelta(days=LOOKBACK_DAYS)
    cutoff_str = cutoff_date.strftime('%B %d, %Y')

    # --- FINAL RIGOR CHECK (POST-SCRAPE DATE VERIFICATION) ---
    print(f"🚀 Performing Forensic Rigor Check on {len(items_for_synthesis)} items using gpt-4o-mini...")
    from llm import reasoning_model as expert_model
    from pydantic import BaseModel, Field
    from utils import get_date_object
    
    class FinalDateCheck(BaseModel):
        publication_date: str = Field(description="YYYY-MM-DD format.")

    date_checker = expert_model.with_structured_output(FinalDateCheck)
    rigorous_items = []
    
    for item in items_for_synthesis:
        try:
            # INCREASE CONTEXT: Give it more text to find the date
            res = date_checker.invoke([
                ("system", f"You are an expert Forensic Fact-Checker. Your sole mission is to find the exact publication date.\n"
                           f"TODAY IS {today_str}.\n"
                           "Look for datelines (e.g. BEIJING, May 21), timestamps, or 'Published on' text.\n"
                           "Return ONLY YYYY-MM-DD. If absolutely NO date is found, return 0000-00-00. DO NOT GUESS."),
                ("human", f"ARTICLE DATA:\nTitle: {item['title']}\nURL: {item['url']}\n\nCONTENT:\n{item['content'][:5000]}")
            ])
            dt = get_date_object(res.publication_date, item.get('url'))
            
            if dt:
                dt_just_day = datetime(dt.year, dt.month, dt.day)
                cutoff_just_day = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
                
                if dt_just_day < cutoff_just_day:
                    print(f"  ❌ PURGED (Old): {res.publication_date} - {item['title'][:50]}")
                    continue
                
                # Update date with verified one
                item["date"] = dt_just_day.strftime("%Y%m%d")
                rigorous_items.append(item)
            else:
                # One last attempt: Check the URL manually in Python if LLM failed
                dt_fallback = get_date_object("", item.get('url'))
                if dt_fallback:
                    dt_just_day = datetime(dt_fallback.year, dt_fallback.month, dt_fallback.day)
                    if dt_just_day >= cutoff_just_day:
                        item["date"] = dt_just_day.strftime("%Y%m%d")
                        rigorous_items.append(item)
                        print(f"  ✅ URL Fallback Date Success: {item['title'][:50]}")
                        continue

                print(f"  ❌ PURGED (Unverifiable): {item['title'][:50]}")
                continue
        except Exception as e:
            print(f"  ⚠️ Rigor check error for {item['title']}: {e}")
            continue

    if not rigorous_items:
        print("No items survived the Final Rigor Check.")
        return {}

    # Group by exact Date string
    grouped_data = {}
    for item in rigorous_items:
        raw_date = str(item.get("date") or "00000000")
        try:
            dt = datetime.strptime(raw_date[:8], "%Y%m%d")
            day_str = dt.strftime("%A, %B %d, %Y")
            sort_key = raw_date[:8]
        except:
            day_str = "Undated / Fresh"
            sort_key = "99999999"
                
        if sort_key not in grouped_data:
            grouped_data[sort_key] = {"day_str": day_str, "items": []}
        grouped_data[sort_key]["items"].append(item)

    print(f"🚀 Synthesizing Exhaustive CCCW Newsletter ({len(grouped_data)} timeline chunks)...")
    
    # --- 1. Synthesize Top News ---
    top_news_prompt = """You are a Senior Strategic Intelligence Analyst.
Task: Write the "Top news items of the week" section.

RULES:
- Select the 4 MOST consequential geopolitical or economic events.
- Write 1 bullet point for each (start with an asterisk *).
- Each bullet MUST be a highly detailed, empirical paragraph (5-8 sentences).
- CITATION RULE: You MUST embed the provided URLs directly onto action verbs: [text](URL).
- DO NOT put "[Read more](URL)" at the end. 
- EVERY bullet point MUST contain at least one hyperlink to a source.
- DO NOT use Markdown headers (#).
- BAN FILLER: Do NOT use AI filler or concluding sentences that summarize significance (e.g., "This highlights...", "reflecting the complex interplay...").
- NO WRAP-UPS: Every paragraph must end with a specific fact or a citation. No "overall" or "in summary" style endings."""

    top_data_feed = json.dumps(rigorous_items[:10], indent=2)
    
    try:
        top_news_resp = reasoning_model.invoke([
            ("system", top_news_prompt),
            ("human", f"DATA PROVIDED:\n{top_data_feed}")
        ])
        top_news_content = top_news_resp.content
    except Exception as e:
        print(f"Error generating Top News: {e}")
        top_news_content = "* Top news generation failed."

    # --- 2. Synthesize Timeline Day-by-Day ---
    timeline_sections = []
    sorted_keys = sorted([k for k in grouped_data.keys() if k != "99999999"])
    if "99999999" in grouped_data:
        sorted_keys.append("99999999")

    for key in sorted_keys:
        chunk = grouped_data[key]
        day_str = chunk["day_str"]
        items = chunk["items"]
        
        # EXPLICIT CHECKLIST: Force the LLM to see all titles it must include
        titles_checklist = "\n".join([f"- {i['title']}" for i in items])
        
        chunk_feed = ""
        for idx, item in enumerate(items):
            chunk_feed += f"\n[{idx+1}] Title: {item['title']}\nURL: {item['url']}\nContent: {item['content']}\n"
            
        day_prompt = f"""You are a Senior Strategic Intelligence Analyst.
Write the timeline entry for: {day_str}

CRITICAL: YOU MUST INCLUDE EVERY ITEM IN THIS CHECKLIST:
{titles_checklist}

RULES:
- Write comprehensive, empirical, multi-paragraph deep dives.
- CITATION RULE: You MUST embed the provided URLs directly onto action verbs: [text](URL).
- EVERY SINGLE PARAGRAPH must contain at least one embedded hyperlink.
- BOLD names of officials (e.g., **Xi Jinping**).
- Integrate specific quotes and statistics if present.
- NO EVALUATIVE FILLER: Do NOT include summary sentences, conclusions, or phrases like "pivotal day" or "complex interplay". 
- NO WRAP-UPS: End each paragraph with a fact. No "Overall" or "In conclusion" statements.
- DO NOT include headers, just return the raw paragraph text for this day."""

        try:
            day_resp = reasoning_model.invoke([
                ("system", day_prompt),
                ("human", f"DATA FOR {day_str}:\n{chunk_feed}")
            ])
            # Format the header in Python
            header = f"__**{day_str}**__\n\n"
            timeline_sections.append(header + day_resp.content.strip())
        except Exception as e:
            print(f"Error generating timeline for {day_str}: {e}")
            
    # --- 3. Assemble Final Newsletter ---
    newsletter_markdown = f"""Do not distribute. For internal use only.

A Tale of Two Capitols ({today_str})

A Tale of Two Capitols is the CCCW’s weekly timeline on activities of interest to U.S.-China relations from official government sources in Beijing and Washington, D.C. All information within is for the purpose of knowledge sharing only and does not imply any institutional stance by the CCCW.

**Top news items of the week**

{top_news_content}

**Timeline**

{chr(10).join([s + chr(10) for s in timeline_sections])}
"""

    # Save the reports
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
    
    md_filename = os.path.join(folder, f"cccw_newsletter_{file_timestamp}.md")
    pdf_filename = os.path.join(folder, f"cccw_newsletter_{file_timestamp}.pdf")
    docx_filename = os.path.join(folder, f"cccw_newsletter_{file_timestamp}.docx")
    
    with open(md_filename, "w") as f:
        f.write(newsletter_markdown)
        
    print(f"✅ Markdown saved to: {md_filename}")
    
    try:
        markdown_to_pdf(newsletter_markdown, pdf_filename)
        print(f"✅ PDF saved to: {pdf_filename}")
    except Exception as pdf_e:
        print(f"⚠️ PDF generation failed: {pdf_e}")

    try:
        markdown_to_docx(newsletter_markdown, docx_filename)
        print(f"✅ Word Document saved to: {docx_filename}")
    except Exception as docx_e:
        print(f"⚠️ Word generation failed: {docx_e}")

    return {
        "final_newsletter_path": md_filename,
        "pdf_path": pdf_filename,
        "docx_path": docx_path
    }

def publish_markdown(state: WorkflowState):
    """Generates a structured Markdown report and a simple source list TXT file."""
    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    file_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    scraped = state.get("scraped_content", [])
    if not scraped:
        scraped = state.get("filtered_items", [])
        is_scraped = False
    else:
        is_scraped = True

    others = state.get("additional_sources", [])
    
    total_limit = MAX_TOTAL_ARTICLES
    scraped = scraped[:total_limit]
    remaining_limit = max(0, total_limit - len(scraped))
    others = others[:remaining_limit]

    report = [
        f"# US-China Strategic Intelligence Briefing",
        f"**Date:** {timestamp_str}",
        f"\n> *This report provides a consolidated view of verified US and Chinese government communications and relevant intelligence from the past {LOOKBACK_DAYS} days.*",
        f"\n---",
        f"## 📋 Table of Contents",
        f"1. [Official Source Intelligence {'(Verbatim)' if is_scraped else '(Sources)'}](#official-source-intelligence-{'verbatim' if is_scraped else 'sources'})",
        f"2. [Other Relevant Intelligence](#other-relevant-intelligence)",
        f"\n---",
        f"\n## 🏛️ Official Source Intelligence {'(Verbatim)' if is_scraped else '(Sources)'}",
        f"{'Verbatim content from verified government/official domains.' if is_scraped else 'Curated list of relevant official and high-tier sources.'}"
    ]
    
    official_count = 0
    for item in scraped:
        official_count += 1
        report.append(f"\n### {official_count}. {item['title']}")
        report.append(f"**Source:** [Direct Link]({item['url']})")
        if is_scraped:
            report.append(f"\n{item.get('content', 'Content not available')}")
        report.append(f"\n---")
    
    if official_count == 0:
        report.append("\n*No official source articles were prioritized in this run.*")
    
    report.append(f"\n## 📡 Other Relevant Intelligence")
    report.append(f"Relevant news from GDELT, RSS, and other search tools.")
    
    if not others:
        report.append("\n*No additional sources found.*")
    else:
        for item in others:
            source_tag = item.get("api_source", "Unknown").upper()
            report.append(f"- **[{source_tag}]** [{item['title']}]({item['url']}) *({item['domain']})*")
            
    folder = "intel_reports"
    os.makedirs(folder, exist_ok=True)
    report_filename = os.path.join(folder, f"intel_report_{file_timestamp}.md")
    
    final_text = "\n".join(report)
    with open(report_filename, "w") as f:
        f.write(final_text)
        
    source_list = []
    idx = 1
    for item in scraped + others:
        date_display = item.get("seendate", "00000000")
        if len(date_display) == 8:
            date_display = f"{date_display[:4]}-{date_display[4:6]}-{date_display[6:]}"
        source_list.append(f"{idx}. {item['title']}")
        source_list.append(f"Date: {date_display}")
        source_list.append(f"Source: {item['url']}\n")
        idx += 1
        
    source_filename = os.path.join(folder, f"sources_{file_timestamp}.txt")
    with open(source_filename, "w") as f:
        f.write("\n".join(source_list))

    print(f"✅ Intel report saved to: {report_filename}")
    print(f"✅ Source list saved to: {source_filename}")
    return {"final_report_path": report_filename, "source_list_path": source_filename}
