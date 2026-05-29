# US-China News Digest Tool

This tool automatically scans the internet for news related to US-China relations, filters out the noise, and prepares a structured timeline of the most important stories.

## What does it do?
- **Scans multiple sources:** It looks at global news databases (GDELT), smart search engines (Tavily), and high-quality news sites (RSS feeds).
- **Filters for quality:** It prioritizes official government sources and major news agencies.
- **Removes duplicates:** If the same story is reported in multiple places, it only keeps one.
- **Curates with AI:** It uses advanced AI to evaluate relevance and prioritize official government communications.

---

## The Tech Stack

We use several industry-standard tools to make this work:

### 1. The Foundation
- **Python:** The programming language used to build the tool.
- **LangGraph:** The engine. It makes sure the data flows correctly from "fetching news" to "organizing" in the right order.

### 2. The Information Sources
- **GDELT Project:** A real-time database of global news.
- **Tavily:** A search engine designed specifically for AI agents
- **RSS Feeds:** Direct pipes into major newsrooms like

### 3. AI Model
- **OpenAI GPT-4o-mini:** High-speed, cost-efficient AI that filters through the news items and decides what's relevant.

### 4. Monitoring & Management
- **LangSmith:** A dashboard that lets us watch the AI "think" in real-time, helping us debug and improve its accuracy.

---

## How to get started

### 1. Install Python
You will need Python installed on your computer. You can download it from [python.org](https://www.python.org/).

### 2. Set up your API Keys
This tool connects to several external services. Create a `.env` file in this folder:

```bash
OPENAI_API_KEY=your_openai_key_here
TAVILY_API_KEY=your_tavily_key_here

# --- REQUIRED ONLY FOR LANGGRAPH STUDIO (Visual Mode) ---
LANGCHAIN_API_KEY=your_langsmith_key_here
```

### 3. Install Dependencies
Open your computer's "Terminal" or "Command Prompt," navigate to this folder, and run:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the Tool
You can run this tool in two ways:

#### **Option A: Visual Mode (LangGraph Studio)**
*Best for debugging and seeing the AI's "thought process" visually.*
- **Requirements:** Docker Desktop must be running; `LANGCHAIN_API_KEY` must be set.
- **Command:**
  ```bash
  langgraph dev
  ```
- This will provide a local link to a visual dashboard.

#### **Option B: Standard Mode (Terminal Only)**
*Best for quick runs. Does NOT require a LangChain API key or Docker.*
- **Command:**
  ```bash
  python run_workflow.py
  ```
- This will run the full intelligence gathering process directly in your terminal and save the reports to the `intel_reports/` folder.

## Files in this project
- `main.py`: The main "brain" of the tool.
- `langgraph.json`: Configuration for the engine.
- `.env`: Where you store your private keys.
- `requirements.txt`: A list of extra parts Python needs to run this tool.
