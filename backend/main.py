from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
import re
import numpy as np
from urllib.parse import urlparse
from fastapi.middleware.cors import CORSMiddleware
from duckduckgo_search import DDGS
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI()

# Add CORS middleware to allow requests from the frontend
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
    # text_tfidf is a sparse matrix of shape (1, n_features)
    row = text_tfidf.toarray()[0]
    indices = np.argsort(row)[::-1]
    top_indices = indices[:top_n]
    keywords = [feature_names[i] for i in top_indices if row[i] > 0]
    return " ".join(keywords)

def verify_with_web(original_text, text_tfidf):
    # 1. Smart Keyword Extraction
    keywords = extract_keywords(text_tfidf, top_n=5)
    
    try:
        with DDGS() as ddgs:
            # Try searching with keywords first
            results = list(ddgs.text(keywords, max_results=5)) if keywords else []
            
            # Fallback to standard text chunk if no results found for keywords
            if not results:
                query = original_text[:100]
                results = list(ddgs.text(query, max_results=5))
        
        if not results:
            return False, [], keywords
            
        sources = []
        verified = False
        
        for r in results:
            # 2. Text Similarity (Semantic Matching)
            snippet = r.get("body", "")
            snippet_clean = clean_text(snippet)
            snippet_tfidf = vectorizer.transform([snippet_clean])
            
            similarity = cosine_similarity(text_tfidf, snippet_tfidf)[0][0]
            
            # 3. Domain Whitelisting
            domain = urlparse(r["href"]).netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            
            is_trusted = domain in TRUSTED_DOMAINS
            
            # If similarity is above 5% (snippets are very short) it's considered a semantic match
            if similarity > 0.05:
                verified = True
                
            sources.append({
                "title": r["title"],
                "href": r["href"],
                "similarity": round(similarity * 100, 1),
                "is_trusted": is_trusted
            })
            
        # Sort sources by similarity descending
        sources = sorted(sources, key=lambda x: x["similarity"], reverse=True)
            
        return verified, sources, keywords
    except Exception as e:
        print("Web search error:", e)
        return False, [], ""

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
    
    # Live Fact Checking with Advanced Agent capabilities
    web_verified, sources, keywords = verify_with_web(news.text, text_tfidf)
    
    return {
        "prediction": label, 
        "raw_score": int(prediction),
        "web_verified": web_verified,
        "sources": sources,
        "keywords": keywords
    }

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run(app, host=host, port=port)
