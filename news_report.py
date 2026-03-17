#!/usr/bin/env python3
"""Daily news digest — delivered per topic."""

import argparse
import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
OUTSYSTEMS_UPDATES_URL = "https://www.outsystems.com/product-updates/"
GITHUB_REPOS = [
    ("anthropics", "claude-code"),
    ("anthropics", "anthropic-sdk-python"),
    ("anthropics", "anthropic-sdk-node"),
]

TOPICS = {
    "anthropic": {
        "title": "🤖 Claude Code & Anthropic",
        "emoji": "🤖",
    },
    "outsystems": {
        "title": "🏗️ OutSystems",
        "emoji": "🏗️",
    },
    "chiefs": {
        "title": "🏈 Kansas City Chiefs",
        "emoji": "🏈",
    },
}


def serpapi(params: dict) -> dict:
    params["api_key"] = SERPAPI_KEY
    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ── Google News ────────────────────────────────────────────────────────────────

def get_google_news(query: str, max_results: int = 5) -> list[dict]:
    try:
        data = serpapi({"engine": "google_news", "q": query, "gl": "pt", "hl": "pt", "tbs": "qdr:d"})
        results = []
        for item in data.get("news_results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "source": item.get("source", {}).get("name", ""),
                "date": item.get("date", ""),
                "link": item.get("link", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ── Twitter/X ─────────────────────────────────────────────────────────────────

def get_twitter_results(query: str, max_results: int = 4) -> list[dict]:
    try:
        data = serpapi({"engine": "google", "q": f"site:x.com {query}", "num": max_results, "hl": "en", "tbs": "qdr:d"})
        results = []
        for item in data.get("organic_results", [])[:max_results]:
            link = item.get("link", "")
            link = re.sub(r'/(photo|video)/\d+$', '', link)
            results.append({
                "title": item.get("title", ""),
                "link": link,
                "date": item.get("date", ""),
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ── GitHub Releases ────────────────────────────────────────────────────────────

def get_github_releases(owner: str, repo: str, max_results: int = 3) -> list[dict]:
    try:
        from datetime import timezone, timedelta
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"
        data = fetch_json(url)
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        results = []
        for release in data:
            pub = release.get("published_at", "")
            if pub:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    continue
            results.append({
                "name": release.get("name") or release.get("tag_name", ""),
                "date": pub[:10],
                "url": release.get("html_url", ""),
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ── OutSystems Product Updates ────────────────────────────────────────────────

def get_outsystems_updates(max_results: int = 4) -> list[dict]:
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch({{ args: ['--no-sandbox'] }});
  const page = await browser.newPage();
  await page.goto('{OUTSYSTEMS_UPDATES_URL}', {{ waitUntil: 'domcontentloaded', timeout: 20000 }});
  await page.waitForTimeout(3000);
  const items = await page.evaluate(() => {{
    const results = [];
    const blocks = document.querySelectorAll('.product-updates-list-item, [class*="update-item"], article');
    if (blocks.length > 0) {{
      blocks.forEach(block => {{
        const title = block.querySelector('h2,h3,h4,[class*="title"]')?.innerText?.trim();
        const date = block.querySelector('[class*="date"],time')?.innerText?.trim();
        const link = block.querySelector('a')?.href || '';
        if (title) results.push({{ title, date, link }});
      }});
    }}
    if (results.length === 0) {{
      const text = document.body.innerText;
      const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
      let currentDate = '';
      for (const line of lines) {{
        if (/^\\d{{1,2}} [A-Z][a-z]+$/.test(line)) {{ currentDate = line; }}
        else if (currentDate && line.length > 20 && line.length < 200 && !line.startsWith('Related')) {{
          results.push({{ title: line, date: currentDate, link: '{OUTSYSTEMS_UPDATES_URL}' }});
          currentDate = '';
        }}
      }}
    }}
    return results.slice(0, {max_results});
  }});
  console.log(JSON.stringify(items));
  await browser.close();
}})().catch(e => {{ console.log(JSON.stringify([])); }});
"""
    try:
        import subprocess
        env = os.environ.copy()
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=35, env=env)
        for line in reversed(result.stdout.strip().splitlines()):
            if line.startswith("["):
                items = json.loads(line)
                return items if items else [{"empty": True}]
        return [{"empty": True}]
    except Exception as e:
        return [{"error": str(e)}]


# ── Hacker News ────────────────────────────────────────────────────────────────

def get_hn_stories(query: str, max_results: int = 4) -> list[dict]:
    try:
        import time
        since = int(time.time()) - 48 * 3600
        url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&tags=story&hitsPerPage={max_results}&numericFilters=created_at_i>{since}"
        data = fetch_json(url)
        results = []
        for hit in data.get("hits", [])[:max_results]:
            results.append({
                "title": hit.get("title", ""),
                "points": hit.get("points", 0),
                "comments": hit.get("num_comments", 0),
                "date": (hit.get("created_at") or "")[:10],
                "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            })
        return results
    except Exception as e:
        return [{"error": str(e)}]


# ── Formatters ─────────────────────────────────────────────────────────────────

def no_news():
    return "  — Sem novidades nas últimas 24h"


def fmt_news(item: dict, i: int) -> str:
    if "error" in item:
        return f"  {i}. ⚠️ Erro: {item['error']}"
    source = f" ({item['source']})" if item.get("source") else ""
    date = f" · {item['date']}" if item.get("date") else ""
    return f"  {i}. {item['title']}{source}{date}\n     🔗 {item['link']}"


def fmt_tweet(item: dict, i: int) -> str:
    if "error" in item:
        return f"  {i}. ⚠️ Erro: {item['error']}"
    return f"  {i}. {item['title']}\n     🔗 {item['link']}"


def fmt_release(repo: str, item: dict, i: int) -> str:
    if "error" in item:
        return f"  {i}. ⚠️ Erro: {item['error']}"
    return f"  {i}. [{repo}] {item['name']} · {item['date']}\n     🔗 {item['url']}"


def fmt_hn(item: dict, i: int) -> str:
    if "error" in item:
        return f"  {i}. ⚠️ Erro: {item['error']}"
    return f"  {i}. {item['title']} · {item['date']}\n     ⬆️ {item['points']} pts · 💬 {item['comments']} · 🔗 {item['hn_url']}"


# ── Topic renderers ────────────────────────────────────────────────────────────

def render_anthropic(date_str: str, day_name: str) -> str:
    lines = [f"🤖 Claude Code & Anthropic — {day_name}, {date_str}\n"]

    lines.append("🔬 Anthropic")
    news = get_google_news("Anthropic AI", max_results=4)
    if news and "error" not in news[0]:
        for i, item in enumerate(news, 1):
            lines.append(fmt_news(item, i))
    else:
        lines.append(no_news())

    lines.append("\n⚙️ Claude Code")
    news = get_google_news("Claude Code Anthropic", max_results=4)
    if news and "error" not in news[0]:
        for i, item in enumerate(news, 1):
            lines.append(fmt_news(item, i))
    else:
        lines.append(no_news())

    lines.append("\n💻 GitHub Releases")
    idx = 1
    any_release = False
    for owner, repo in GITHUB_REPOS:
        releases = get_github_releases(owner, repo, max_results=2)
        for item in releases:
            if "error" not in item:
                lines.append(fmt_release(repo, item, idx))
                idx += 1
                any_release = True
    if not any_release:
        lines.append(no_news())

    lines.append("\n🟠 Hacker News")
    hn = get_hn_stories("Anthropic Claude", max_results=4)
    if hn and "error" not in hn[0]:
        for i, item in enumerate(hn, 1):
            lines.append(fmt_hn(item, i))
    else:
        lines.append(no_news())

    lines.append("\n🐦 Twitter/X")
    tweets = get_twitter_results("Anthropic Claude Code", max_results=4)
    if tweets and "error" not in tweets[0]:
        for i, item in enumerate(tweets, 1):
            lines.append(fmt_tweet(item, i))
    else:
        lines.append(no_news())

    return "\n".join(lines)


def render_outsystems(date_str: str, day_name: str) -> str:
    lines = [f"🏗️ OutSystems — {day_name}, {date_str}\n"]

    lines.append("📰 Notícias")
    news = get_google_news("OutSystems", max_results=4)
    if news and "error" not in news[0]:
        for i, item in enumerate(news, 1):
            lines.append(fmt_news(item, i))
    else:
        lines.append(no_news())

    lines.append("\n📦 Product Updates")
    updates = get_outsystems_updates(max_results=4)
    if updates and "error" not in updates[0] and "empty" not in updates[0]:
        for i, item in enumerate(updates, 1):
            date = f" · {item['date']}" if item.get("date") else ""
            link = item.get("link") or OUTSYSTEMS_UPDATES_URL
            lines.append(f"  {i}. {item['title']}{date}\n     🔗 {link}")
    else:
        lines.append(no_news())

    lines.append("\n🐦 Twitter/X")
    tweets = get_twitter_results("OutSystems", max_results=3)
    if tweets and "error" not in tweets[0]:
        for i, item in enumerate(tweets, 1):
            lines.append(fmt_tweet(item, i))
    else:
        lines.append(no_news())

    return "\n".join(lines)


def render_chiefs(date_str: str, day_name: str) -> str:
    lines = [f"🏈 Kansas City Chiefs — {day_name}, {date_str}\n"]

    lines.append("📰 Notícias")
    news = get_google_news("Kansas City Chiefs", max_results=5)
    if news and "error" not in news[0]:
        for i, item in enumerate(news, 1):
            lines.append(fmt_news(item, i))
    else:
        lines.append(no_news())

    lines.append("\n🐦 Twitter/X")
    tweets = get_twitter_results("Kansas City Chiefs", max_results=4)
    if tweets and "error" not in tweets[0]:
        for i, item in enumerate(tweets, 1):
            lines.append(fmt_tweet(item, i))
    else:
        lines.append(no_news())

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Daily news digest per topic")
    parser.add_argument("--topic", choices=list(TOPICS.keys()), required=True,
                        help="Topic to render: anthropic, outsystems, chiefs")
    args = parser.parse_args()

    now = datetime.now()
    date_str = now.strftime("%-d %B %Y")
    day_name = now.strftime("%A")

    if args.topic == "anthropic":
        print(render_anthropic(date_str, day_name))
    elif args.topic == "outsystems":
        print(render_outsystems(date_str, day_name))
    elif args.topic == "chiefs":
        print(render_chiefs(date_str, day_name))


if __name__ == "__main__":
    main()
