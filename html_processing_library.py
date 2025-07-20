from bs4 import BeautifulSoup
import re
import difflib

def remove_unwanted_tags(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "meta", "link", "noscript", "iframe"]):
        tag.decompose()
    return str(soup)

def extract_paragraphs(html):
    soup = BeautifulSoup(html, "html.parser")
    block_tags = ['p', 'div', 'li', 'section', 'article']
    paragraphs = []
    for block in soup.find_all(block_tags):
        if not block.find(block_tags):
            text = block.get_text(separator=' ', strip=True)
            if text:
                paragraphs.append(text)
    return paragraphs

def normalize_text(text):
    text = re.sub(r'\b\d{1,2}:\d{2}(:\d{2})?\b', '', text)  
    text = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', text)      
    text = re.sub(r'\b\d{2}/\d{2}/\d{4}\b', '', text)     
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def preprocess_html(raw_html):
    cleaned_html = remove_unwanted_tags(raw_html)
    paragraphs = extract_paragraphs(cleaned_html)
    normalized_paragraphs = [normalize_text(p) for p in paragraphs if p.strip()]
    return normalized_paragraphs  # Return as a list

def diff_html(html1, html2):
    text1 = preprocess_html(html1)
    text2 = preprocess_html(html2)

    diff = difflib.unified_diff(text1, text2)
    return diff