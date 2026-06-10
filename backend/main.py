from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
import re
import time
from google import genai
import numpy as np
from urllib.parse import urlparse
from fastapi.middleware.cors import CORSMiddleware
from duckduckgo_search import DDGS
from sklearn.metrics.pairwise import cosine_similarity

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

model = None
vectorizer = None

TRUSTED_DOMAINS = {
    'bbc.com', 'bbc.co.uk', 'reuters.com', 'apnews.com', 
    'nytimes.com', 'washingtonpost.com', 'nasa.gov', 
    'cnn.com', 'npr.org', 'theguardian.com', 'wsj.com',
    'bloomberg.com', 'cnbc.com', 'aljazeera.com'
}

def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r'^.*?\(Reuters\)\s*-\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_keywords(text_tfidf, top_n=5):
    if not vectorizer:
        return ""
    feature_names = vectorizer.get_feature_names_out()
    row = text_tfidf.toarray()[0]
    indices = np.argsort(row)[::-1]
    top_indices = indices[:top_n]
    keywords = [feature_names[i] for i in top_indices if row[i] > 0]
    return " ".join(keywords)

def verify_with_web(original_text, text_tfidf):
    keywords = extract_keywords(text_tfidf, top_n=5)
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(keywords, max_results=5)) if keywords else []
            if not results:
                query = original_text[:100]
                results = list(ddgs.text(query, max_results=5))
        
        if not results:
            return False, False, [], keywords
            
        sources = []
        trusted_match_found = False
        any_match_found = False

        for r in results:
            snippet = r.get("body", "")
            snippet_clean = clean_text(snippet)
            snippet_tfidf = vectorizer.transform([snippet_clean])

            similarity = cosine_similarity(text_tfidf, snippet_tfidf)[0][0]

            domain = urlparse(r["href"]).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            is_trusted = domain in TRUSTED_DOMAINS

            if similarity > 0.20:
                any_match_found = True
                if is_trusted:
                    trusted_match_found = True

            sources.append({
                "title": r["title"],
                "href": r["href"],
                "similarity": round(similarity * 100, 1),
                "is_trusted": is_trusted
            })
            
        sources = sorted(sources, key=lambda x: x["similarity"], reverse=True)
        return trusted_match_found, any_match_found, sources, keywords
    except Exception as e:
        print("Web search error:", e)
        return False, False, [], ""


def analyze_with_gemini(text, sources, ml_label, confidence_pct, trusted_verified):
    # Sistemdeki GEMINI_API_KEY ortam değişkenini kontrol eder
    if not os.environ.get("GEMINI_API_KEY"):
        print("Hata: GEMINI_API_KEY ortam değişkeni set edilmemiş.")
        return "Gemini API Key bulunamadı."
        
    # Boş bırakıldığında otomatik olarak os.environ["GEMINI_API_KEY"] değerini okur
    try:
        client = genai.Client()
    except Exception as e:
        print("Gemini client error:", e)
        return f"Gemini API hatası gerçekleşti: {str(e)}"

    sources_context = ""
    for s in sources[:3]:
        trust = "trusted" if s["is_trusted"] else "unverified"
        sources_context += f"\n  - {s['title']} — {s['similarity']}% match ({trust})"

    prompt = (
        "You are a fact-checking AI agent. Analyze this news snippet and determine if it is real or fake.\n\n"
        f"ARTICLE:\n{text[:1200]}\n\n"
        "ML MODEL SIGNALS:\n"
        f"- Prediction: {ml_label}\n"
        f"- Confidence: {confidence_pct}%\n"
        f"- Trusted web verification: {'Yes' if trusted_verified else 'No'}\n\n"
        f"WEB SEARCH RESULTS:{sources_context if sources_context else ' none found'}\n\n"
        "Provide:\n"
        "1. Final verdict: Real / Fake / Uncertain\n"
        "2. 2-3 sentences of reasoning\n"
        "3. The strongest signal in the text supporting your verdict"
    )

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
                )
                return response.text.strip() if response.text else None
            except Exception as e:
                last_error = e
                msg = str(e)
                is_transient = "503" in msg or "UNAVAILABLE" in msg or "overloaded" in msg.lower()
                print(f"Gemini API error (model={model_name}, attempt={attempt + 1}): {e}")
                if not is_transient:
                    # Kalıcı hata (hatalı key, kota, geçersiz istek) — tekrar denemeye gerek yok
                    return f"Gemini API hatası gerçekleşti: {msg}"
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))  # 1.5s, sonra 3s bekle

    print("Gemini still unavailable after retries:", last_error)
    return "Gemini şu anda çok yoğun, lütfen birkaç saniye sonra tekrar deneyin."


@app.on_event("startup")
def load_model():
    global model, vectorizer
    model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'model.pkl')
    vec_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vectorizer.pkl')
    
    if os.path.exists(model_path) and os.path.exists(vec_path):
        model = joblib.load(model_path)
        vectorizer = joblib.load(vec_path)
        print("Model and vectorizer loaded successfully.")
    else:
        print("Warning: Model or vectorizer not found. Please train the model first.")

@app.post("/predict")
def predict_news(news: NewsInput):
    if not model or not vectorizer:
        raise HTTPException(status_code=500, detail="Model is not loaded.")
    
    cleaned_input = clean_text(news.text)
    text_tfidf = vectorizer.transform([cleaned_input])
    prediction = model.predict(text_tfidf)[0]
    label = "Real" if prediction == 1 else "Fake"

    raw_confidence = float(model.decision_function(text_tfidf)[0])
    clamped = max(-3.0, min(3.0, raw_confidence))
    confidence_pct = round((clamped + 3.0) / 6.0 * 100, 1)
    
    trusted_verified, any_verified, sources, keywords = verify_with_web(news.text, text_tfidf)

    if label == "Real" and trusted_verified:
        verdict = "Likely Real"
        verdict_detail = "ML model and a trusted web source both support this."
    elif label == "Fake" and not any_verified:
        verdict = "Likely Fake"
        verdict_detail = "ML model flagged this and no matching sources were found."
    elif label == "Real" and not any_verified:
        verdict = "Uncertain"
        verdict_detail = "ML model says real but no corroborating sources found online."
    else:
        verdict = "Uncertain"
        verdict_detail = "ML model and web results give conflicting signals. Review sources."

    gemini_analysis = analyze_with_gemini(news.text, sources, label, confidence_pct, trusted_verified)

    return {
        "prediction": label,
        "raw_score": int(prediction),
        "confidence": confidence_pct,
        "web_verified": trusted_verified,
        "any_match_found": any_verified,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "sources": sources,
        "keywords": keywords,
        "gemini_analysis": gemini_analysis
    }

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)