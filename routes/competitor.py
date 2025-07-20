from flask import Blueprint, request, jsonify
import asyncio
import re
from crawl4ai import AsyncWebCrawler
from AiLib import generate_response
from datetime import datetime
from pymongo import MongoClient
from threading import Thread
from bson import ObjectId

competitor_bp = Blueprint('competitor', __name__)

# MongoDB connection helper
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "competitorIQ"
COLLECTION_NAME = "competitors"
def get_mongo_client():
    return MongoClient(MONGO_URI)

# Async helper for crawling and field extraction (homepage only)
async def crawl_and_extract_fields(homepage):
    # 1. Crawl homepage
    async with AsyncWebCrawler() as crawler:
        homepage_result = await crawler.arun(homepage)
    homepage_markdown = getattr(homepage_result, 'markdown', '')

    # 2. Use Gemini to extract required fields from homepage content only
    extraction_prompt = f"""
Given the following website content, extract the following fields as a JSON object:\n- pricing: URL of the pricing page (if any)\n- blog: URL of the blog (if any)\n- releaseNotes: URL of release notes/changelog (if any)\n- playstore: URL of Play Store app (if any)\n- appstore: URL of App Store app (if any)\n- linkedin: URL of LinkedIn page (if any)\n- twitter: URL of Twitter/X page (if any)\n- custom: []\nReturn only a JSON object with these fields.\n\nContent:\n{homepage_markdown}\n"""
    fields_json = generate_response(extraction_prompt)
    # Try to parse the JSON from Gemini's response
    import json
    try:
        # Find the first { ... } block in the response
        match = re.search(r'\{[\s\S]*\}', fields_json)
        if match:
            fields = json.loads(match.group(0))
        else:
            fields = {}
    except Exception:
        fields = {}
    # Ensure custom is always an empty array
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
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            try:
                result = await crawler.arun(url)
                content = getattr(result, 'markdown', '')
                pages.append({'url': url, 'content': content})
            except Exception:
                pages.append({'url': url, 'content': ''})
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
    # snapshot = data.get('snapshot')  # No longer used for initial save
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