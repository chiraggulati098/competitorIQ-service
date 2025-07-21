import google.generativeai as genai
import os
from dotenv import load_dotenv
import time

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-1.5-flash"

def generate_response(prompt):
    '''
    Send user query to Gemini API and return response
    '''
    print(prompt[-100:])    
    print(len(prompt))
    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            print(response.usage_metadata)
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                time.sleep(1)  
                continue
            else:
                return f"Error after {max_retries} attempts: {str(e)}"