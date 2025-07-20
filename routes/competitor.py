from flask import Blueprint, request, jsonify
import asyncio
import re
import requests
from bs4 import BeautifulSoup
from AiLib import generate_response
from datetime import datetime
from pymongo import MongoClient
from threading import Thread
from bson import ObjectId
from urllib.parse import urljoin

competitor_bp = Blueprint('competitor', __name__)

# MongoDB connection helper
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "competitorIQ"
COLLECTION_NAME = "competitors"
def get_mongo_client():
    return MongoClient(MONGO_URI)

# Helper to fetch HTML using requests + BeautifulSoup
async def fetch_html(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Optionally, prettify or minify
        html = soup.prettify()
        return html
    except Exception:
        return ""

# Async helper for crawling and field extraction (homepage only)
async def crawl_and_extract_fields(homepage):
    homepage_html = await fetch_html(homepage)
    # Extract all links using <a> tags and hrefs (absolute and relative)
    soup = BeautifulSoup(homepage_html, "html.parser")
    # save homepage_html to a file
    with open(f'{homepage.replace("/", "_")}_html.html', 'w') as f:
        f.write(homepage_html)
    hrefs = [a.get("href") for a in soup.find_all("a", href=True)]
    # Convert relative URLs to absolute
    links = [urljoin(homepage, href) if href and not href.startswith("http") else href for href in hrefs if href]
    links = [link for link in links if link]
    links = list(set(links))
    # 2. Use Gemini to extract required fields from links only
    extraction_prompt = f"""
Given the following list of links (which may be absolute or relative to the homepage), extract the following fields as a JSON object:\n- pricing: URL of the pricing page (if any)\n- blog: URL of the blog (if any)\n- releaseNotes: URL of release notes/changelog (if any)\n- playstore: URL of Play Store app (if any)\n- appstore: URL of App Store app (if any)\n- linkedin: URL of LinkedIn page (if any)\n- twitter: URL of Twitter/X page (if any)\n- custom: []\nReturn only a JSON object with these fields, and ensure all URLs are absolute (not relative).\n\nLinks:\n{links}\n"""
    fields_json = generate_response(extraction_prompt)
    import json
    try:
        match = re.search(r'\{[\s\S]*\}', fields_json)
        if match:
            fields = json.loads(match.group(0))
        else:
            fields = {}
    except Exception:
        fields = {}
    fields['custom'] = []
    return fields

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

async def crawl_urls_and_save_snapshot(competitor_id):
    client = get_mongo_client()
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    competitor = collection.find_one({'_id': ObjectId(competitor_id)})
    if not competitor:
        client.close()
        return
    urls = get_tracked_urls(competitor)
    pages = []
    for url in urls:
        html = await fetch_html(url)
        pages.append({'url': url, 'content': html})
    snapshot = {
        'date': datetime.utcnow().isoformat() + 'Z',
        'pages': pages
    }
    # Only keep the 2 most recent snapshots
    collection.update_one(
        {'_id': ObjectId(competitor_id)},
        {'$push': {'snapshots': {'$each': [snapshot], '$slice': -2}}}
    )
    client.close()

@competitor_bp.route('/api/competitors/scan', methods=['POST'])
def scan_competitor():
    data = request.get_json()
    homepage = data.get('homepage')
    if not homepage:
        return jsonify({'error': 'Homepage URL is required'}), 400
    try:
        fields = asyncio.run(crawl_and_extract_fields(homepage))
    except Exception as e:
        return jsonify({'error': f'Error during crawling/extraction: {str(e)}'}), 500
    return jsonify(fields), 200 

@competitor_bp.route('/api/competitors', methods=['POST'])
def save_competitor():
    data = request.get_json()
    user_id = data.get('userId')
    name = data.get('name')
    homepage = data.get('homepage')
    fields = data.get('fields')
    if not user_id or not name or not homepage or not fields:
        return jsonify({'error': 'Missing required fields'}), 400
    doc = {
        'userId': user_id,
        'name': name,
        'homepage': homepage,
        'fields': fields,
        'snapshots': []  # Start with no snapshots
    }
    try:
        client = get_mongo_client()
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        # Check for duplicate
        existing = collection.find_one({
            'userId': user_id,
            'name': name,
            'homepage': homepage
        })
        if existing:
            client.close()
            return jsonify({'error': 'Competitor already exists for this user.'}), 409
        result = collection.insert_one(doc)
        client.close()
        return jsonify({'success': True, 'id': str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({'error': f'Error saving competitor: {str(e)}'}), 500 

@competitor_bp.route('/api/competitors/<competitor_id>/snapshot', methods=['POST'])
def trigger_snapshot(competitor_id):
    # Start the snapshot crawl in a background thread
    def run_bg():
        asyncio.run(crawl_urls_and_save_snapshot(competitor_id))
    Thread(target=run_bg, daemon=True).start()
    return '', 202 