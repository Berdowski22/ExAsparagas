# Real or Fake News Detector — AI Agent Edition

An AI-powered web application that fact-checks news. A user pastes a news report or claim, and the app decides whether it is **Real**, **Fake**, or **Uncertain** — backed by a live web search and an LLM reasoning step.

> **Note:** This version no longer uses a locally trained ML model (TF-IDF / Logistic Regression). It has been replaced by a **Gemini LLM "brain" + a web search agent** that finds and weighs trusted news sources in real time.

## How It Works

```
User text
   │
   ▼
1. Web Search Agent (verify_with_web)
   ├─ Generic DuckDuckGo search for context
   └─ Targeted "site:" search across priority trusted outlets
        (Reuters, AP, BBC, Anadolu Ajansı, TRT, …)
   │
   ▼
2. Gemini LLM Brain (analyze_with_gemini)
   ├─ Confirms the input is actually news (guardrail)
   └─ Judges Real / Fake / Uncertain using the web evidence
   │
   ▼
3. /predict endpoint packages the result
   │
   ▼
Frontend renders verdict, confidence, sources, and Gemini's analysis
```

## Features

- **LLM fact-checking**: Google Gemini decides Real / Fake / Uncertain with a confidence score.
- **Live web verification**: A search agent finds related articles and flags matches from a curated list of **trusted outlets** (international + Turkish).
- **Direct trusted-source lookup**: Uses combined `site:` queries to fetch the exact article from reputable sources instead of relying on luck.
- **News-only guardrail**: Politely declines anything that isn't a news claim (questions, poems, code, gibberish).
- **Rich, conversational response**: Returns a direct yes/no summary, supporting key points, an actionable recommendation, and full reasoning.
- **Resilient API calls**: Retries on transient errors and falls back to a secondary Gemini model.

## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **AI**: Google Gemini (`google-genai`) — `gemini-2.5-flash` with `gemini-2.0-flash` fallback
- **Web Search**: `ddgs` (DuckDuckGo Search)
- **Config**: `python-dotenv` for managing the API key
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## Project Structure

```
ExAsparagas/
├── backend/
│   ├── main.py                      # FastAPI app: web search agent + Gemini analysis + /predict
│   ├── requirements.txt             # Python dependencies
│   ├── .env                         # GEMINI_API_KEY (you create this — not committed)
│   └── train_model(Not Using FNow).py  # Legacy ML training script (no longer used)
├── frontend/
│   ├── index.html                   # Main user interface
│   ├── style.css                    # UI styling
│   └── app.js                       # Frontend logic and API calls
├── LICENSE
└── README.md                        # Project documentation
```

## Setup and Installation

### Prerequisites

- Python 3.8+
- A **Google Gemini API key** — get one free at https://aistudio.google.com/app/apikey

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd ExAsparagas
```

### 2. Backend Setup
Install the required Python packages.
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure your API key
Create a file named `.env` inside the `backend/` folder with your Gemini key (no quotes, no spaces):
```
GEMINI_API_KEY=your_actual_key_here
```
The app loads this automatically on startup via `python-dotenv`. The `.env` file is git-ignored so your key is never committed.

> **Free-tier quota:** Gemini's free tier allows a limited number of requests **per day, per Google Cloud project** (e.g. 20/day for `gemini-2.5-flash`). This limit is shared across all API keys in the same project — creating a new key does **not** reset it. If you hit `RESOURCE_EXHAUSTED` (429), wait for the daily reset, use a new project, or enable billing.

### 4. Running the Backend Server
```bash
# In the backend directory
python main.py
```
The API runs at `http://127.0.0.1:8000`. Interactive docs are at `http://127.0.0.1:8000/docs`.

> **Tip:** Restart the server after editing `.env` — the key is read only once at startup.

### 5. Running the Frontend
Open `frontend/index.html` directly in your browser, or serve it with a simple HTTP server:
```bash
cd frontend
python -m http.server 3000
```
Then navigate to `http://localhost:3000`. The frontend calls the backend at `http://127.0.0.1:8000/predict`.

## API Endpoints

### `POST /predict`
- **Description**: Fact-checks a news text using the web search agent + Gemini.
- **Request Body**:
  ```json
  {
    "text": "Your news report or claim goes here..."
  }
  ```
- **Response** (news input):
  ```json
  {
    "prediction": "Real",
    "confidence": 95,
    "verdict": "Likely Real",
    "verdict_detail": "A trusted web source corroborates this.",
    "web_verified": true,
    "sources": [
      {
        "title": "Article title",
        "href": "https://www.reuters.com/...",
        "similarity": 75.0,
        "is_trusted": true
      }
    ],
    "keywords": "turkey central bank interest",
    "summary": "Yes — this appears to be REAL: a trusted source confirms it.",
    "key_points": ["Reuters and BBC both report this", "..."],
    "recommendation": "Cross-check the figures against the official statement.",
    "gemini_analysis": "Full reasoning paragraph..."
  }
  ```
- **Response** (non-news input):
  ```json
  {
    "prediction": "Not News",
    "verdict": "Not News",
    "verdict_detail": "This tool only fact-checks news. Please paste a news report or claim.",
    "web_verified": false,
    "sources": [],
    "keywords": "...",
    "gemini_analysis": "Explanation of why the input isn't news."
  }
  ```

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE).
