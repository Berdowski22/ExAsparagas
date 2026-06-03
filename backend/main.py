from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
import re
from fastapi.middleware.cors import CORSMiddleware

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
    
    # Preprocess the incoming text exactly like training
    cleaned_input = clean_text(news.text)
    
    # Transform and predict
    text_tfidf = vectorizer.transform([cleaned_input])
    prediction = model.predict(text_tfidf)[0]
    
    label = "Real" if prediction == 1 else "Fake"
    
    return {"prediction": label, "raw_score": int(prediction)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
