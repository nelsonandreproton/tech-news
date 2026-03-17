# tech-news

Daily news digest script for **Claude Code**, **Anthropic**, and **OutSystems** — delivered every morning via Telegram.

## What it does

`news_report.py` aggregates the latest news and updates from multiple sources into a single, clean daily digest:

| Section | Source | Filter |
|---|---|---|
| 🔬 Anthropic | Google News (SerpAPI) | Last 24h |
| ⚙️ Claude Code | Google News (SerpAPI) | Last 24h |
| 🏗️ OutSystems News | Google News (SerpAPI) | Last 24h |
| 📦 OutSystems Product Updates | [outsystems.com/product-updates](https://www.outsystems.com/product-updates/) (Playwright) | Latest entries |
| 💻 GitHub Releases | GitHub API (claude-code, anthropic-sdk-python) | Last 48h |
| 🟠 Hacker News | Algolia HN API | Last 48h |
| 🐦 Twitter/X | Google Search site:x.com (SerpAPI) | Last 24h |

The digest is sent automatically every day at **07:30 Lisbon time** via Telegram, using an OpenClaw cron job.

## Requirements

- Python 3.10+
- Node.js (for Playwright — used to scrape the OutSystems product updates page)
- Playwright with Chromium: `npm install -g playwright && npx playwright install chromium`
- [SerpAPI](https://serpapi.com) key (free tier available)

## Configuration

Set the following environment variable before running:

```bash
export SERPAPI_KEY="your_serpapi_key_here"
```

For Playwright (OutSystems scraping), set `NODE_PATH` to your global npm modules:

```bash
export NODE_PATH=$(npm root -g)
```

## Usage

```bash
NODE_PATH=$(npm root -g) SERPAPI_KEY="your_key" python3 news_report.py
```

## Scheduled delivery

The script is scheduled via **OpenClaw cron** to run daily at 07:30 Europe/Lisbon and deliver the output directly to a Telegram chat:

```bash
openclaw cron add \
  --name "news-anthropic-daily" \
  --cron "30 7 * * *" \
  --tz "Europe/Lisbon" \
  --session isolated \
  --message "NODE_PATH=... SERPAPI_KEY=... python3 news_report.py" \
  --announce \
  --channel telegram \
  --to <telegram_chat_id>
```

## Output example

```
📰 Claude Code & Anthropic — Tuesday, 17 March 2026

🔬 Anthropic
  1. OpenAI to focus on coding to counter Anthropic growth (Tecnoblog) · 17 Mar
     🔗 https://...

⚙️ Claude Code
  1. Anthropic doubles Claude usage limits during off-peak hours (TugaTech) · 15 Mar
     🔗 https://...

🏗️ OutSystems
  📦 Product Updates
  1. Exposed Secrets in Site Properties in AI Mentor Studio (O11) · 16 March
     🔗 https://www.outsystems.com/product-updates/

💻 GitHub Releases
  1. [claude-code] v2.1.77 · 2026-03-17
     🔗 https://github.com/anthropics/claude-code/releases/tag/v2.1.77

🟠 Hacker News
  1. Anthropic requires your phone number · 16 Mar · ⬆️ 3 pts
     🔗 https://news.ycombinator.com/item?id=47403267

🐦 Twitter/X
  1. Anthropic just 2x'd Claude Code limits for "Spring Break"
     🔗 https://x.com/alexchristou_/status/...
```

## Notes

- Google News date filtering (`tbs=qdr:d`) is best-effort — some results may be 2–3 days old depending on news volume
- Twitter/X results are fetched via Google Search (`site:x.com`) since the native Twitter API requires a paid plan
- The OutSystems scraper uses Playwright headless Chromium since the page is JavaScript-rendered
