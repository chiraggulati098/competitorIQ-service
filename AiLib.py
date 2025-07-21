import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

load_dotenv()

gemini_api_keys = os.getenv("GEMINI_API_KEYS", "").split(",")
gemini_api_keys = [key.strip() for key in gemini_api_keys if key.strip()]
GEMINI_MODEL = "gemini-1.5-flash"

if not gemini_api_keys:
    raise ValueError("No Gemini API keys found. Please set GEMINI_API_KEYS in your .env file.")

def is_quota_error(e):
    msg = str(e).lower()
    return (
        "quota" in msg or
        "limit" in msg or
        "exceeded" in msg or
        "rate" in msg
    )

def generate_response(prompt):
    '''
    Send user query to Gemini API and return response, rotating through API keys if quota/limit is reached
    '''
    max_retries = 3
    last_error = None
    for key in gemini_api_keys:
        genai.configure(api_key=key)
        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = model.generate_content(prompt)
                print(response.usage_metadata)
                return response.text
            except Exception as e:
                last_error = e
                if is_quota_error(e):
                    print(f"API key quota/limit reached for key ending with ...{key[-4:]}. Trying next key.")
                    break  # Try next key
                elif attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(1)
                    continue
                else:
                    print(f"Error after {max_retries} attempts with key ending ...{key[-4:]}: {e}")
                    break  # Try next key
    return f"All API keys failed. Last error: {str(last_error)}"