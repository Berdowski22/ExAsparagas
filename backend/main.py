from fastapi import FastAPI
from pydantic import BaseModel
import os
import re
import time
import json
from google import genai
from urllib.parse import urlparse
from fastapi.middleware.cors import CORSMiddleware
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri os.environ'a yükler (GEMINI_API_KEY vb.)
load_dotenv()

app = FastAPI()

# CORS Ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class NewsInput(BaseModel):
    text: str

TRUSTED_DOMAINS = {
    'bbc.com', 'bbc.co.uk', 'reuters.com', 'apnews.com',
    'nytimes.com', 'washingtonpost.com', 'nasa.gov',
    'cnn.com', 'npr.org', 'theguardian.com', 'wsj.com',
    'bloomberg.com', 'cnbc.com', 'aljazeera.com'
}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'of', 'to', 'in', 'on', 'for', 'with',
    'as', 'by', 'at', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those', 'it', 'its', 'they', 'them', 'their', 'you',
    'your', 'we', 'our', 'will', 'would', 'can', 'could', 'should', 'has', 'have',
    'had', 'not', 'no', 'do', 'does', 'did', 'if', 'then', 'than', 'so', 'such',
    'about', 'into', 'over', 'after', 'before', 'more', 'most', 'some', 'any',
    'all', 'who', 'what', 'when', 'where', 'which', 'while', 'also', 'said', 'says'
}


def extract_keywords(text, top_n=5):
    """Pick the most frequent meaningful words to use as a web search query (no ML)."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    freq = {}
    for w in words:
        if w in STOPWORDS:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: freq[w], reverse=True)
    return " ".join(ranked[:top_n])


def text_overlap(a, b):
    """Lightweight keyword-overlap score (0-100) between two texts — replaces TF-IDF similarity."""
    wa = {w for w in re.findall(r"[a-zA-Z]{4,}", a.lower()) if w not in STOPWORDS}
    wb = {w for w in re.findall(r"[a-zA-Z]{4,}", b.lower()) if w not in STOPWORDS}
    if not wa or not wb:
        return 0.0
    return round(len(wa & wb) / len(wa) * 100, 1)


def verify_with_web(original_text):
    """Web search agent tool: find related articles and flag trusted-domain matches."""
    keywords = extract_keywords(original_text, top_n=5)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(keywords, max_results=5)) if keywords else []
            if not results:
                results = list(ddgs.text(original_text[:100], max_results=5))

        if not results:
            return False, [], keywords

        sources = []
        trusted_match = False

        for r in results:
            snippet = r.get("body", "")
            similarity = text_overlap(original_text, snippet)

            domain = urlparse(r["href"]).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            is_trusted = domain in TRUSTED_DOMAINS

            if similarity > 15 and is_trusted:
                trusted_match = True

            sources.append({
                "title": r["title"],
                "href": r["href"],
                "similarity": similarity,
                "is_trusted": is_trusted
            })

        sources = sorted(sources, key=lambda x: x["similarity"], reverse=True)
        return trusted_match, sources, keywords
    except Exception as e:
        print("Web search error:", e)
        return False, [], ""


def analyze_with_gemini(text, sources, web_verified):
    """The LLM brain: Gemini decides Real/Fake/Uncertain with a confidence and reasoning."""
    if not os.environ.get("GEMINI_API_KEY"):
        print("Hata: GEMINI_API_KEY ortam değişkeni set edilmemiş.")
        return {"verdict": "Uncertain", "confidence": 0,
                "reasoning": "Gemini API Key bulunamadı."}

    # Boş bırakıldığında otomatik olarak os.environ["GEMINI_API_KEY"] değerini okur
    try:
        client = genai.Client()
    except Exception as e:
        print("Gemini client error:", e)
        return {"verdict": "Uncertain", "confidence": 0,
                "reasoning": f"Gemini API hatası gerçekleşti: {e}"}

    sources_context = ""
    for s in sources[:5]:
        trust = "trusted" if s["is_trusted"] else "unverified"
        sources_context += f"\n  - {s['title']} ({trust}, {s['similarity']}% keyword overlap)"

    prompt = (
        "You are a fact-checking AI agent. Decide whether the following news text is real or fake.\n\n"
        f"NEWS TEXT:\n{text[:1500]}\n\n"
        f"WEB SEARCH RESULTS:{sources_context if sources_context else ' none found'}\n\n"
        f"A trusted news source corroborates this: {'Yes' if web_verified else 'No'}\n\n"
        "Weigh the writing style, plausibility, and whether reputable web sources corroborate the claims. "
        "Respond ONLY with a JSON object using these keys:\n"
        '  "verdict": one of "Real", "Fake", "Uncertain"\n'
        '  "confidence": an integer from 0 to 100 (how sure you are)\n'
        '  "reasoning": 2-4 sentences explaining your decision and the strongest signal'
    )

    config = {"response_mime_type": "application/json"}

    # 503 (yoğunluk) gibi geçici hatalarda birkaç kez tekrar dener;
    # birincil model sürekli meşgulse yedek modele geçer.
    models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    last_error = None
    for model_name in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            except Exception as e:
                last_error = e
                msg = str(e)
                is_transient = "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower()
                print(f"Gemini API error (model={model_name}, attempt={attempt + 1}): {e}")
                if not is_transient:
                    return {"verdict": "Uncertain", "confidence": 0,
                            "reasoning": f"Gemini API hatası gerçekleşti: {msg}"}
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))  # 1.5s, sonra 3s bekle
                continue

            # İstek başarılı — JSON yanıtını ayrıştır
            raw = (response.text or "").strip()
            try:
                data = json.loads(raw)
                verdict = data.get("verdict", "Uncertain")
                if verdict not in ("Real", "Fake", "Uncertain"):
                    verdict = "Uncertain"
                confidence = max(0, min(100, int(data.get("confidence", 0))))
                reasoning = (data.get("reasoning") or "").strip() or "No reasoning returned."
                return {"verdict": verdict, "confidence": confidence, "reasoning": reasoning}
            except Exception:
                # JSON ayrıştırılamadıysa ham metni gerekçe olarak göster
                return {"verdict": "Uncertain", "confidence": 0,
                        "reasoning": raw or "Gemini geçersiz bir yanıt döndü."}

    print("Gemini still unavailable after retries:", last_error)
    return {"verdict": "Uncertain", "confidence": 0,
            "reasoning": "Gemini şu anda çok yoğun, lütfen birkaç saniye sonra tekrar deneyin."}


@app.post("/predict")
def predict_news(news: NewsInput):
    # 1. Web arama ajanı: ilgili kaynakları bul
    web_verified, sources, keywords = verify_with_web(news.text)

    # 2. LLM beyni: Gemini gerçek/sahte kararını verir
    result = analyze_with_gemini(news.text, sources, web_verified)

    verdict = result["verdict"]
    if verdict == "Real":
        prediction, verdict_label = "Real", "Likely Real"
    elif verdict == "Fake":
        prediction, verdict_label = "Fake", "Likely Fake"
    else:
        prediction, verdict_label = "Uncertain", "Uncertain"

    if web_verified:
        verdict_detail = "A trusted web source corroborates this."
    elif sources:
        verdict_detail = "Related web results were found, but no trusted source strongly matched."
    else:
        verdict_detail = "No corroborating web sources were found."

    return {
        "prediction": prediction,
        "confidence": result["confidence"],
        "verdict": verdict_label,
        "verdict_detail": verdict_detail,
        "web_verified": web_verified,
        "sources": sources,
        "keywords": keywords,
        "gemini_analysis": result["reasoning"]
    }


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
