import asyncio
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import requests
from bs4 import BeautifulSoup
from AiLib import generate_response
import difflib
import logging
import json
import re

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
        diff = '\n'.join(difflib.unified_diff(
            content1.splitlines(), content2.splitlines(), lineterm='', fromfile='before', tofile='after'))
        diff_by_url[url] = diff
    print(diff_by_url)
    return diff_by_url

# Fetch HTML using requests + BeautifulSoup
async def fetch_html(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        html = soup.prettify()
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
You are an expert AI product analyst for CompetitorIQ. Summarize the following changes detected on a competitor's tracked pages. Only mention meaningful changes (such as new features, pricing changes, new blog posts, product updates, etc). Ignore trivial or cosmetic changes (such as minor text tweaks, formatting, or style changes).

Return your answer as a JSON object. Each key should be the field name (e.g., 'pricing', 'blog', 'releaseNotes', 'playstore', 'appstore', 'linkedin', 'twitter', or the URL for custom fields), and each value should be a clear, confident, and actionable summary of the meaningful change for that field. If a change is detected but the exact content is unclear, confidently state what was detected (e.g., "A new blog post was published". Do not apologize or hedge. If there are no meaningful changes, return an empty JSON object: {}.

Example:
{
  "pricing": "The pricing was updated to reflect new plans.",
  "blog": "A new blog post was published on the company blog.",
  "customfield1": "The UI was refreshed with a modern look."
}

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