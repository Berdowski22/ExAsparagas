import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
import re

def clean_text(text):
    if not isinstance(text, str):
        return ""
    
    # 1. Remove Publisher/Location shortcuts like "WASHINGTON (Reuters) - "
    # The regex looks for start of string, some characters, "(Reuters) -"
    text = re.sub(r'^.*?\(Reuters\)\s*-\s*', '', text, flags=re.IGNORECASE)
    
    # 2. Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # 3. Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    
    # 4. Remove special characters and numbers (keeping only letters)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # 5. Lowercase and remove extra whitespace
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def train():
    print("Loading dataset...")
    # Read the dataset
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'news.csv')
    df = pd.read_csv(data_path)
    
    # Check if 'text' and 'label' columns exist
    if 'text' not in df.columns or 'label' not in df.columns:
        raise ValueError("Dataset must contain 'text' and 'label' columns.")
        
    print(f"Dataset loaded with {len(df)} records.")
    
    # Handle missing values
    df = df.dropna(subset=['text', 'label'])
    
    print("Cleaning text data (Removing shortcuts and artifacts)...")
    df['clean_text'] = df['text'].apply(clean_text)
    
    X = df['clean_text']
    y = df['label']
    
    # Split the dataset
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Vectorizing text data with N-Grams...")
    # Using ngram_range=(1, 2) to capture word pairs for better context
    vectorizer = TfidfVectorizer(stop_words='english', max_df=0.7, ngram_range=(1, 2))
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    
    print("Training LinearSVC model...")
    model = LinearSVC(max_iter=2000)
    model.fit(X_train_tfidf, y_train)
    
    print("Evaluating model...")
    y_pred = model.predict(X_test_tfidf)
    acc = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {acc:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))
    
    print("Saving model and vectorizer...")
    joblib.dump(model, 'model.pkl')
    joblib.dump(vectorizer, 'vectorizer.pkl')
    print("Training complete! Saved as model.pkl and vectorizer.pkl.")

if __name__ == "__main__":
    train()
