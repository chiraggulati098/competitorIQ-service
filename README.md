# CompetitorIQ Service

CompetitorIQ Service is the CompetitorIQ backend service for tracking, analyzing, and summarizing changes in competitors' products and web presence. It leverages AI (Google Gemini) to extract and summarize meaningful changes from crawled competitor pages, and notifies users of important updates via email. The service is built with Flask, MongoDB, Playwright, and integrates with Clerk for authentication.

## Features

- **Competitor Tracking:** Add, update, list, and delete competitors you want to monitor.
- **Automated Crawling:** Uses Playwright to crawl competitor homepages and key subpages (pricing, blog, release notes, social, etc.).
- **AI-Powered Extraction:** Extracts important links and fields from competitor sites using Gemini LLM.
- **Change Detection:** Snapshots and diffs HTML content to detect meaningful changes.
- **Automated Summarization:** Summarizes changes using Gemini and stores summaries per competitor.
- **User Preferences:** Users can set notification frequency and email preferences.
- **Email Notifications:** Sends change summaries to users via email.
- **Authentication:** Uses Clerk for secure user authentication and management.

## Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/chiraggulati098/competitorIQ-service.git
cd competitorIQ/competitorIQ-service
```

### 2. Create and Activate Virtual Environment (optional but recommended)
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Variables
Create a `.env` file in the root of `competitorIQ-service` with the following variables:

```
MONGO_URI=<your-mongodb-uri>
GEMINI_API_KEYS=<comma-separated-gemini-api-keys>
CLERK_SECRET_KEY=<your-clerk-secret-key>
JWT_KEY=<your-jwt-key>
GMAIL_PASSWORD=<your-gmail-app-password>  # (if using Gmail for email, optional)
RESEND_API_KEY=<your-resend-api-key>
```

## Running the Service

```bash
python app.py
```
The service will start on `http://0.0.0.0:8000` by default.

## API Endpoints

### Authentication
- `POST /login` — Authenticate user via Clerk. Requires Authorization header.

### Health Check
- `GET /health` — Returns `{ status: 'ok' }` if the service is running.

### User Preferences
- `GET /api/user/preferences?userId=...` — Get user notification preferences.
- `POST /api/user/preferences` — Set user notification preferences.

### Competitor Management
- `POST /api/competitors/scan` — Crawl a homepage and extract key fields (pricing, blog, etc.) using AI.
- `POST /api/competitors` — Add a new competitor to track.
- `GET /api/competitors/list?userId=...` — List all competitors for a user.
- `PATCH /api/competitors/<competitor_id>` — Update competitor name/fields.
- `DELETE /api/competitors/<competitor_id>` — Delete a competitor.

### Snapshots & Summaries
- `POST /api/competitors/<competitor_id>/snapshot` — Trigger a crawl and snapshot for a competitor (runs in background).
- `GET /api/competitors/summaries?userId=...` — Get all change summaries for a user's competitors.

## How It Works

1. **Add Competitor:** User submits a competitor's homepage and name. The service uses Playwright to crawl the homepage and Gemini to extract important links (pricing, blog, etc.).
2. **Track Changes:** The service periodically crawls tracked URLs, snapshots HTML, and diffs against previous snapshots.
3. **Summarize Changes:** Diffs are summarized by Gemini into human-readable bullet points.
4. **Notify User:** Summaries are stored and, if user preferences allow, emailed to the user.

## Tech Stack
- **Python 3.11.9**
- **Flask** (API server)
- **MongoDB** (data storage)
- **Playwright** (headless browser crawling)
- **BeautifulSoup** (HTML parsing)
- **Google Gemini** (AI/LLM for extraction & summarization)
- **Clerk** (authentication)
- **Resend** (email delivery)

## Development & Testing
- Use the `/health` endpoint to verify the service is running.
- Use tools like Postman or curl to interact with the API.
- For crawling and AI features, ensure your environment variables are set and Playwright is installed (`pip install playwright` and `playwright install`).

## Folder Structure
- `app.py` — Main Flask app and API entrypoint
- `routes/competitor.py` — All competitor-related endpoints and crawling logic
- `AiLib.py` — Gemini LLM integration
- `pipeline.py` — Change detection, diffing, and summarization pipeline
- `mail_service.py` — Email notification logic
- `html_processing_library.py` — HTML cleaning and diff utilities
- `utils/clerk_auth.py` — Clerk authentication helpers

---

This project was made by Chirag with ❤️