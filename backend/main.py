from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
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
    
    # Preprocess and predict
    text_tfidf = vectorizer.transform([news.text])
    prediction = model.predict(text_tfidf)[0]
    
    # prediction 1 usually means Real (in our dataset), 0 means Fake.
    # Let's check the dataset distribution later, but we will return the raw int prediction for now.
    
    label = "Real" if prediction == 1 else "Fake"
    
    return {"prediction": label, "raw_score": int(prediction)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
