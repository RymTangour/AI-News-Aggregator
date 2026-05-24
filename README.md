# 📰 AI News Aggregator

Automated pipeline that scrapes YouTube channels and Anthropic's blog, generates RAG-powered digests using a local LLM, and delivers a personalised email — on a configurable schedule.

## How it works

```
Scrape (YouTube + Anthropic RSS)
  → Process (transcripts + markdown)
    → RAG (chunk → embed → 10 Q&A → summary)
      → Rank → Format → Email
```

## Stack

| | |
|---|---|
| LLM + Embeddings | llama3.1:8B + nomic-embed-text via Ollama |
| Vector store | ChromaDB |
| Database |  SQLAlchemy |
| Scraping | feedparser + Docling + YouTube Transcript API |
| Scheduling | APScheduler |
| GUI | Streamlit |
| Email | Resend API |

## Setup

```bash
git clone https://github.com/yourname/ai-news-aggregator
cd ai-news-aggregator
pip install -r requirements.txt

# Pull local models
ollama pull llama3.1
ollama pull nomic-embed-text
```

## Usage

**GUI (recommended)**
```bash
streamlit run app.py
```
Enter your Resend API key + email, pick an interval, hit Start.

**CLI**
```bash
python main.py                    # last 24h, top 10
python main.py --hours 48 --top-n 15
```

## Project structure

```
app/
  scrapers/      youtube.py · anthropic.py
  agent/         digest_agent.py · curator_agent.py · email_agent.py
  database/      models.py · repository.py · create_tables.py  · connection.py
  services/      process_*.py · email.py
  profiles/      user_profile.py
main.py          full pipeline CLI
app_ui.py        Streamlit GUI
runner_daily.py  scheduled runner
```

## Why local-first?

Everything runs on your machine — no API costs, no data sent externally, full privacy. ChromaDB and Ollama require zero cloud setup.

---

*Rym Tangour*