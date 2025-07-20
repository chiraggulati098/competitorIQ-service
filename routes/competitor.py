from flask import Blueprint, request, jsonify
import asyncio
import re
from crawl4ai import AsyncWebCrawler
from AiLib import generate_response

competitor_bp = Blueprint('competitor', __name__)

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