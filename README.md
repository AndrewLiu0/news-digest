# US-China News Digest Tool

This tool automatically scans the internet for news related to US-China relations, filters out the noise, and prepares a summary of the most important stories.

## What does it do?
- **Scans multiple sources:** It looks at global news databases (GDELT), smart search engines (Tavily), and high-quality news sites (RSS feeds).
- **Filters for quality:** It prioritizes official government sources and major news agencies.
- **Removes duplicates:** If the same story is reported in multiple places, it only keeps one.
- **Summarizes with AI:** It uses advanced AI to read the articles and extract the key takeaways.
- **Ready for analysis:** It prepares the news to be saved (e.g., to a Google Doc).

---

## The Tech Stack (What's under the hood?)

We use several industry-standard tools and "AI engines" to make this work:

### 1. The Foundation
- **Python:** The programming language used to build the tool.
- **LangGraph:** The "orchestrator" or engine. It makes sure the data flows correctly from "fetching news" to "summarizing" in the right order.

### 2. The Information Sources
- **GDELT Project:** A massive, real-time database of global news that monitors every corner of the world.
- **Tavily:** A search engine designed specifically for AI "agents" to find facts quickly and accurately.
- **RSS Feeds:** Direct pipes into major newsrooms like the New York Times, Reuters, and South China Morning Post.

### 3. The "Brains" (AI Models)
- **OpenAI GPT-4o-mini:** High-speed, cost-efficient AI that reads through the news items and decides what's important.

### 4. Monitoring & Management
- **LangSmith:** A dashboard that lets us watch the AI "think" in real-time, helping us debug and improve its accuracy.

---

## How to get started (for non-technical users)

### 1. Install Python
You will need Python installed on your computer. You can download it from [python.org](https://www.python.org/).

### 2. Set up your API Keys
This tool connects to several external services. You will need a `.env` file in this folder containing your secret "keys" (like passwords for services):

```bash
# AI Brain (OpenAI)
OPENAI_API_KEY=your_openai_key_here

# Smart Search
TAVILY_API_KEY=your_tavily_key_here

# Monitoring & Deep Scraping (Optional)
LANGSMITH_API_KEY=your_langsmith_key_here
JINA_API_KEY=your_jina_key_here
```

### 3. Install the Tool
Open your computer's "Terminal" or "Command Prompt," navigate to this folder, and type:
```bash
pip install -r requirements.txt
```

### 4. Run the Tool
To start the news gathering process, type:
```bash
langgraph dev
```
This will start the engine and provide a link to a visual dashboard.

## Files in this project
- `main.py`: The main "brain" of the tool.
- `langgraph.json`: Configuration for the engine.
- `.env`: Where you store your private keys.
- `requirements.txt`: A list of extra parts Python needs to run this tool.
