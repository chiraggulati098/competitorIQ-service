import asyncio
from datetime import datetime, date
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
from mail_service import send_email
from utils.clerk_auth import get_user_mails

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "competitorIQ"
COLLECTION_NAME = "competitors"
USER_PREFS_COLLECTION = "user_preferences"

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
You will be given the HTML diffs for all tracked pages of a single competitor.
Summarize the most important, meaningful changes as a prioritized list of bullet points (one change per bullet), focusing on:
- New features or product updates
- Pricing changes
- New blog posts
- Social announcements
Prioritize the most impactful changes at the top. Ignore trivial or cosmetic changes (e.g., minor text tweaks, formatting, or style changes).
Return a JSON array of strings, each string being a meaningful change. If no meaningful changes are detected, return ["No changes detected"].

Diffs:
"""
    for url, diff in diff_by_url.items():
        prompt += f"\nURL: {url}\nDiff:\n{diff}\n"
    prompt += "\nJSON:"
    response = generate_response(prompt)
    try:
        match = re.search(r'\[[\s\S]*\]', response)
        if match:
            summary_list = json.loads(match.group(0))
        else:
            summary_list = ["No changes detected"]
    except Exception:
        summary_list = ["No changes detected"]
    return summary_list


def generate_user_email_content(user_id, summary_blocks, total_pages, competitor_names):
    # Compose prompt for Gemini to generate subject and body
    prompt = f"""
You are an expert product analyst and email copywriter for CompetitorIQ. Write a concise, actionable email update for the user summarizing all tracked competitors' changes.

Details to include:
- Number of competitors tracked: {len(competitor_names)}
- Names of competitors: {', '.join(competitor_names)}
- Total number of pages tracked: {total_pages}
- For each competitor, summarize the meaningful changes (see below)

Summaries:
{json.dumps(summary_blocks, indent=2)}

Return a JSON object with two fields: 'subject' (string) and 'body' (string, can be HTML or plain text). Do not include any explanations or headers.
"""
    response = generate_response(prompt)
    try:
        match = re.search(r'\{[\s\S]*\}', response)
        if match:
            mail_json = json.loads(match.group(0))
        else:
            mail_json = {"subject": "CompetitorIQ Update", "body": "No changes detected."}
    except Exception:
        mail_json = {"subject": "CompetitorIQ Update", "body": "No changes detected."}
    return mail_json

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    user_prefs_collection = db[USER_PREFS_COLLECTION]
    competitors = list(collection.find({}))
    logging.info(f"Found {len(competitors)} competitors.")
    # Group competitors by user
    user_map = {}
    for competitor in competitors:
        user_id = competitor.get('userId')
        if not user_id:
            continue
        user_map.setdefault(user_id, []).append(competitor)
    # Get all user emails once
    user_mails = get_user_mails()
    today = date.today()
    weekday = today.weekday()  
    day_of_month = today.day
    for user_id, user_competitors in user_map.items():
        # Fetch user preferences
        prefs_doc = user_prefs_collection.find_one({'userId': user_id})
        prefs = prefs_doc.get('preferences', {}) if prefs_doc else {}
        update_freq = prefs.get('updateFreq', 'daily')
        receive_email = prefs.get('receiveEmail', True)
        # Determine if we should run for this user
        should_run = False
        if update_freq == 'daily':
            should_run = True
        elif update_freq == 'weekly' and weekday == 0:
            should_run = True
        elif update_freq == 'monthly' and day_of_month == 1:
            should_run = True
        if not should_run:
            logging.info(f"Skipping user {user_id} due to updateFreq ({update_freq})")
            continue
        summary_blocks = []
        total_pages = 0
        competitor_names = [c.get('name') for c in user_competitors]

        # For each competitor, update snapshots and summaries
        for competitor in user_competitors:
            urls = get_tracked_urls(competitor)
            # Take new snapshot
            pages = asyncio.run(crawl_urls(urls))
            snapshot = {
                'date': datetime.utcnow(),
                'pages': pages
            }
            total_pages += len(pages)
            # Add snapshot, keep only 2 most recent
            collection.update_one(
                {'_id': competitor['_id']},
                {'$push': {'snapshots': {'$each': [snapshot], '$slice': -2}}}
            )
            # Refresh competitor with latest snapshots
            updated_competitor = collection.find_one({'_id': competitor['_id']})
            
            # Generate and store summary
            snaps = updated_competitor.get('snapshots', [])
            summary_list = ["No changes detected"]
            summary_date = datetime.utcnow()

            if len(snaps) >= 2:
                snap1, snap2 = snaps[-2], snaps[-1]
                diff_by_url = diff_snapshots(snap1, snap2)
                summary_list = summarize_with_gemini(diff_by_url)
                summary_date = snap2['date']
            
            summary_doc = {'date': summary_date, 'summary': summary_list}
            collection.update_one(
                {'_id': competitor['_id']},
                {'$push': {'summaries': {'$each': [summary_doc], '$slice': -10}}}
            )

            summary_blocks.append({
                'competitor': competitor.get('name'),
                'summary': summary_list
            })

        # Generate email content for this user
        mail_json = generate_user_email_content(user_id, summary_blocks, total_pages, competitor_names)
        # Get user email from user_mails dict
        user_email = user_mails.get(user_id)
        if receive_email and user_email:
            result = send_email(user_email, mail_json['subject'], mail_json['body'])
            logging.info(f"Sent email to {user_email}: {result}")
        elif not receive_email:
            logging.info(f"User {user_id} has opted out of email updates.")
        else:
            logging.warning(f"Could not find email for user {user_id}")
    client.close()

if __name__ == "__main__":
    main()