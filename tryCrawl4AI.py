import asyncio
from click import prompt
from crawl4ai import AsyncWebCrawler
from AiLib import generate_response
import re

LINK = "https://trello.com"

def extract_links(markdown):
    links = re.findall(r'(http[s]?://[^\s)\]\["\'>]+)', markdown)
    links = set(links)
    print(f"Found {len(links)} total links.")
    return links

async def evaluate_links(links, base_url):
    prompt = f"""
You are an AI assistant for CompetitorIQ, a tool that tracks changes in competitors' products.
Analyze the following links from {base_url} and return *only* a Python list of links (e.g., ["link1", "link2"]) that are likely to contain information about:
- Landing page updates
- Blog posts
- Pricing changes
- Social announcements or product updates
Prioritize links containing keywords like 'pricing', 'blog', 'announcements', 'updates', 'features', or 'changelog' in their URLs.
Do not include any explanations or additional text, just the Python list.
Links: {', '.join(links)}
    """
    response = generate_response(prompt)
    response = response.strip()
    response = response[9:-3].strip() if response.startswith('```python') and response.endswith('```') else response
    relevant_links = eval(response) if response else []
    if not isinstance(relevant_links, list):
        relevant_links = []
    return relevant_links

async def main():
    # homepage to markdown
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(LINK)
    
    # extract links
    links = extract_links(result.markdown)

    # ask gemini about which links to crawl
    relevant_links = await evaluate_links(links, LINK)
    print(f"Total number of Relevant links: {len(relevant_links)}\nRelevant links to crawl: {relevant_links}")
    
    # crawl links
    if relevant_links:
        async with AsyncWebCrawler() as crawler:
            for link in relevant_links:
                print(f"Crawling {link}...")
                result = await crawler.arun(link)
                print(f"Crawled {link} with status: {result.status_code}")

    # ask gemini about these links now (and if any are as per our requirements)

    # final crawl

    # print pages crawled and important links if received


if __name__ == "__main__":
    asyncio.run(main())