from fastapi import FastAPI
from pydantic import BaseModel
import os
import re
import time
import json
from google import genai
from urllib.parse import urlparse
from fastapi.middleware.cors import CORSMiddleware
from ddgs import DDGS
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
    # International / English
    'bbc.com', 'bbc.co.uk', 'reuters.com', 'apnews.com',
    'nytimes.com', 'washingtonpost.com', 'nasa.gov',
    'cnn.com', 'npr.org', 'theguardian.com', 'wsj.com',
    'bloomberg.com', 'cnbc.com', 'aljazeera.com',
    'dw.com', 'france24.com', 'euronews.com', 'ft.com',
    'economist.com', 'time.com', 'abcnews.go.com',
    'cbsnews.com', 'nbcnews.com', 'politico.com', 'forbes.com',
    # Turkish
    'aa.com.tr', 'trthaber.com', 'trt.net.tr', 'ntv.com.tr',
    'cnnturk.com', 'haberturk.com', 'hurriyet.com.tr',
    'milliyet.com.tr', 'sozcu.com.tr', 'sabah.com.tr',
    'dha.com.tr'
}

# verify_with_web bunları doğrudan `site:` aramasıyla hedefler — en geniş
# kapsamlı/otoriter kaynaklar; haberin tam kaynağını şansa bırakmadan bulmak için.
PRIORITY_TRUSTED_DOMAINS = [
    'reuters.com', 'apnews.com', 'bbc.com', 'theguardian.com',
    'aljazeera.com', 'aa.com.tr', 'trthaber.com', 'ntv.com.tr',
]

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
    # Küçük kümeye (genelde kısa snippet) göre normalize et: snippet tamamen
    # makalede geçiyorsa skor yüksek olur. len(wa)'ya bölmek uzun makalelerde
    # skoru daima düşürüp güvenilir eşleşmeleri kaçırıyordu.
    denom = min(len(wa), len(wb))
    return round(len(wa & wb) / denom * 100, 1)


def _ddg_search(query, max_results=4):
    """Tek bir DuckDuckGo metin araması; hata/limit durumunda boş liste döner."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"DDG search error (query={query!r}):", e)
        return []


def _normalize_domain(href):
    """URL'den 'www.' önekini atılmış küçük harf alan adını çıkarır."""
    domain = urlparse(href).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def verify_with_web(original_text):
    """Web search agent tool: find related articles and flag trusted-domain matches.

    İki arama yapar:
      1. Genel arama — web genelinde ilgili sonuçlar (bağlam için).
      2. Hedefli `site:` araması — tek bir birleşik OR sorgusuyla öncelikli güvenilir
         kaynaklarda haberin tam makalesini doğrudan arar, doğru kaynağı şansa bırakmaz.
    """
    keywords = extract_keywords(original_text, top_n=5)
    query = keywords or original_text[:100]

    # 1) Genel arama — web genelinde ilgili sonuçlar (bağlam için)
    generic = _ddg_search(query, max_results=5)

    # 2) Hedefli güvenilir arama — tek bir birleşik `site:` OR sorgusuyla öncelikli
    #    güvenilir kaynaklarda haberin tam makalesini doğrudan arar (şansa bırakmaz)
    site_filter = " OR ".join(f"site:{d}" for d in PRIORITY_TRUSTED_DOMAINS)
    trusted = _ddg_search(f"{query} ({site_filter})", max_results=8)

    all_results = generic + trusted
    if not all_results:
        return False, [], keywords

    sources = []
    trusted_match = False
    seen = set()

    for r in all_results:
        href = r.get("href")
        if not href or href in seen:
            continue
        seen.add(href)

        snippet = r.get("body", "")
        similarity = text_overlap(original_text, snippet)
        domain = _normalize_domain(href)
        is_trusted = domain in TRUSTED_DOMAINS

        if similarity > 15 and is_trusted:
            trusted_match = True

        sources.append({
            "title": r.get("title", domain),
            "href": href,
            "similarity": similarity,
            "is_trusted": is_trusted,
        })

    # Önce benzerliğe, eşitlikte güvenilir olana göre sırala; ilk 8'i tut
    sources = sorted(sources, key=lambda x: (x["similarity"], x["is_trusted"]), reverse=True)
    sources = sources[:8]
    return trusted_match, sources, keywords


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
        "You are a fact-checking AI agent that ONLY analyzes news. "
        "Your single job is to judge whether a news report/claim about real-world events is real or fake.\n\n"
        "FIRST, decide if the input is actually a news statement (a claim or report about real-world "
        "events, people, places, or facts). It is NOT news if it is a question, a request/command, "
        "a poem or story, source code, a personal opinion, small talk, or meaningless gibberish.\n\n"
        f"INPUT TEXT:\n{text[:1500]}\n\n"
        f"WEB SEARCH RESULTS:{sources_context if sources_context else ' none found'}\n\n"
        f"A trusted news source corroborates this: {'Yes' if web_verified else 'No'}\n\n"
        "If the input is NOT news, set \"is_news\" to false and do not judge real/fake. "
        "If it IS news, weigh plausibility and whether reputable web sources corroborate the "
        "claims. Polished or sloppy writing style is WEAK evidence either way — well-written "
        "fakes and badly-written truths both exist, so do not lean on style.\n\n"
        "IMPORTANT JUDGEMENT RULES:\n"
        "  - If NO web sources were found, that is almost always a search limitation "
        "(rate-limiting, paywalls, or a very recent event) — NOT evidence that the news is fake. "
        "In that case prefer \"Uncertain\"; do NOT return \"Fake\" unless the claim itself is "
        "internally implausible or self-contradictory.\n"
        "  - Do NOT judge a claim as fake merely because it post-dates your training data. "
        "Recent real events are expected and you cannot have memorized them.\n"
        "  - Reserve \"Fake\" for claims that are implausible, contradicted by sources, or show "
        "clear fabrication signals — not merely for claims you cannot verify.\n\n"
        "Be genuinely helpful and conversational with the user — explain your thinking clearly, "
        "point out exactly what makes the claim credible or suspicious, and tell them what they "
        "should do next. Write to the reader directly, not as a dry report.\n\n"
        "Respond ONLY with a JSON object using these keys:\n"
        '  "is_news": true if the input is a news claim/report, otherwise false\n'
        '  "verdict": one of "Real", "Fake", "Uncertain" (use "Uncertain" when is_news is false)\n'
        '  "confidence": an integer from 0 to 100 (how sure you are)\n'
        '  "summary": ONE sentence that directly answers the user as if replying to '
        '"is this real or fake?". It MUST open with a clear verdict word and address the '
        'reader: start with "Yes — this appears to be REAL:" if real, "No — this looks FAKE:" '
        'if fake, or "It is unclear:" if uncertain, then a short reason. Be direct, not a dry report.\n'
        '  "key_points": an array of 2-4 short strings, each a concrete signal that supports or '
        "undermines the claim (mention sources, dates, numbers, or wording where relevant)\n"
        '  "recommendation": one actionable sentence telling the user what to do next '
        "(e.g. which source to cross-check, what detail to be skeptical of)\n"
        '  "reasoning": 2-4 sentences explaining your decision and the strongest signal. '
        "If is_news is false, briefly explain that the input is not news."
    )

    config = {"response_mime_type": "application/json"}

    # 503 (yoğunluk) gibi geçici hatalarda birkaç kez tekrar dener;
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
                is_news = bool(data.get("is_news", True))
                verdict = data.get("verdict", "Uncertain")
                if verdict not in ("Real", "Fake", "Uncertain"):
                    verdict = "Uncertain"
                confidence = max(0, min(100, int(data.get("confidence", 0))))
                reasoning = (data.get("reasoning") or "").strip() or "No reasoning returned."
                summary = (data.get("summary") or "").strip()
                recommendation = (data.get("recommendation") or "").strip()
                # key_points'i temizle: yalnızca boş olmayan string'leri al (en fazla 4)
                raw_points = data.get("key_points") or []
                if not isinstance(raw_points, list):
                    raw_points = []
                key_points = [str(p).strip() for p in raw_points if str(p).strip()][:4]
                if not is_news:
                    verdict = "Uncertain"
                return {"is_news": is_news, "verdict": verdict, "confidence": confidence,
                        "summary": summary, "key_points": key_points,
                        "recommendation": recommendation, "reasoning": reasoning}
            except Exception:
                # JSON ayrıştırılamadıysa ham metni gerekçe olarak göster
                return {"is_news": True, "verdict": "Uncertain", "confidence": 0,
                        "summary": "", "key_points": [], "recommendation": "",
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

    # Girdi haber değilse: bu araç yalnızca haber analiz eder, kibarca reddet
    if not result.get("is_news", True):
        return {
            "prediction": "Not News",
            "confidence": 0,
            "verdict": "Not News",
            "verdict_detail": "This tool only fact-checks news. Please paste a news report or claim.",
            "web_verified": False,
            "sources": [],
            "keywords": keywords,
            "gemini_analysis": result["reasoning"]
        }

    verdict = result["verdict"]
    confidence = result["confidence"]

    # Çelişki uzlaştırma: Güvenilir bir kaynak haberi doğruluyorsa (web_verified)
    # ama Gemini "Fake" dediyse, bu gerçek bir çelişkidir. Sahte kararını körü
    # körüne göstermek yerine "Uncertain"a indir ve çelişkiyi kullanıcıya bildir;
    # böylece "Likely Fake" + "güvenilir kaynak doğruluyor" gibi tutarsız bir
    # ekran oluşmaz.
    conflict = web_verified and verdict == "Fake"
    if conflict:
        verdict = "Uncertain"
        confidence = min(confidence, 50)

    if verdict == "Real":
        prediction, verdict_label = "Real", "Likely Real"
    elif verdict == "Fake":
        prediction, verdict_label = "Fake", "Likely Fake"
    else:
        prediction, verdict_label = "Uncertain", "Uncertain"

    if conflict:
        verdict_detail = ("Conflicting signals: a trusted web source corroborates this, but "
                          "Gemini found the claim suspicious — treat with caution and verify.")
    elif web_verified:
        verdict_detail = "A trusted web source corroborates this."
    elif sources:
        verdict_detail = "Related web results were found, but no trusted source strongly matched."
    else:
        verdict_detail = "No corroborating web sources were found."

    return {
        "prediction": prediction,
        "confidence": confidence,
        "verdict": verdict_label,
        "verdict_detail": verdict_detail,
        "web_verified": web_verified,
        "sources": sources,
        "keywords": keywords,
        "summary": result.get("summary", ""),
        "key_points": result.get("key_points", []),
        "recommendation": result.get("recommendation", ""),
        "gemini_analysis": result["reasoning"]
    }


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
