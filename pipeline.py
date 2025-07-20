import asyncio
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from AiLib import generate_response
import difflib
import logging
import json
import re
from html_processing_library import diff_html  

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "competitorIQ"
COLLECTION_NAME = "competitors"

def get_tracked_urls(competitor):
    urls = [competitor.get('homepage')]
    fields = competitor.get('fields', {})
    for key in ['pricing', 'blog', 'releaseNotes', 'playstore', 'appstore', 'linkedin', 'twitter']:
        url = fields.get(key)
        if url:
            urls.append(url)
    custom = fields.get('custom', [])
    urls.extend([u for u in custom if u])
    return list(set(urls))

def diff_snapshots(snap1, snap2):
    diff_by_url = {}
    pages1 = {p['url']: p['content'] for p in snap1.get('pages', [])}
    pages2 = {p['url']: p['content'] for p in snap2.get('pages', [])}
    all_urls = set(pages1) | set(pages2)
    for url in all_urls:
        content1 = pages1.get(url, '')
        content2 = pages2.get(url, '')
        diff = diff_html(content1, content2)  
        diff_by_url[url] = '\n'.join(diff)
    print(diff_by_url)
    return diff_by_url

# Fetch HTML using Playwright
async def fetch_html(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=20000)
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        logging.warning(f"Failed to crawl {url}: {e}")
        return ""

async def crawl_urls(urls):
    pages = []
    for url in urls:
        html = await fetch_html(url)
        pages.append({'url': url, 'content': html})
    return pages

def summarize_with_gemini(diff_by_url):
    prompt = """
You are an expert AI product analyst for CompetitorIQ, a tool that tracks changes in competitors' products.
Analyze the content from {url} to identify *meaningful* changes related to:
- New features or product updates
- Pricing changes
- New blog posts
- Social announcements
Ignore trivial or cosmetic changes (e.g., minor text tweaks, formatting, or style changes).
Return a JSON object where each key is the relevant field (e.g., 'pricing', 'blog', 'releaseNotes', 'playstore', 'appstore', 'linkedin', 'twitter', or the URL for custom fields),
and each value is a clear, confident, actionable summary of the meaningful change in 1-2 sentences.
If no meaningful changes are detected, return an empty JSON object: {{}}.
Do not include any explanations or headers in the JSON output.

Diffs:
"""
    for url, diff in diff_by_url.items():
        prompt += f"\nURL: {url}\nDiff:\n{diff}\n"
    prompt += "\nJSON:"
    response = generate_response(prompt)
    try:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            summary_json = json.loads(match.group(0))
        else:
            summary_json = {}
    except Exception:
        summary_json = {}
    return summary_json

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    competitors = list(collection.find({}))
    logging.info(f"Found {len(competitors)} competitors.")
    for competitor in competitors:
        user_id = competitor.get('userId')
        name = competitor.get('name')
        logging.info(f"Processing competitor '{name}' for user {user_id}")
        urls = get_tracked_urls(competitor)
        # Take new snapshot
        pages = asyncio.run(crawl_urls(urls))
        snapshot = {
            'date': datetime.utcnow().isoformat() + 'Z',
            'pages': pages
        }
        # Add snapshot, keep only 2 most recent
        collection.update_one(
            {'_id': competitor['_id']},
            {'$push': {'snapshots': {'$each': [snapshot], '$slice': -2}}}
        )
        # Get the two most recent snapshots
        updated = collection.find_one({'_id': competitor['_id']})
        snaps = updated.get('snapshots', [])
        if len(snaps) < 2:
            logging.info("Not enough snapshots to diff yet.")
            continue
        snap1, snap2 = snaps[-2], snaps[-1]
        diff_by_url = diff_snapshots(snap1, snap2)
        summary_json = summarize_with_gemini(diff_by_url)
        summary_doc = {
            'date': snapshot['date'],
            'summary': summary_json,
            'diff': diff_by_url
        }
        # Store summary, keep only 10 most recent
        collection.update_one(
            {'_id': competitor['_id']},
            {'$push': {'summaries': {'$each': [summary_doc], '$slice': -10}}}
        )
        logging.info(f"Summary for '{name}':\n{json.dumps(summary_json, indent=2)}\n")
        # TODO: Email the user the summary
    client.close()

if __name__ == "__main__":
    main()