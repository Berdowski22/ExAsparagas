document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyzeBtn');
    const newsInput = document.getElementById('newsInput');
    const resultSection = document.getElementById('resultSection');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultContent = document.getElementById('resultContent');
    const resultLabel = document.getElementById('resultLabel');
    const resultMessage = document.getElementById('resultMessage');

    // Web Verification Elements
    const webVerification = document.getElementById('webVerification');
    const webBadge = document.getElementById('webBadge');
    const searchKeywords = document.getElementById('searchKeywords');
    const sourceList = document.getElementById('sourceList');

    const API_URL = 'http://127.0.0.1:8000/predict';

    analyzeBtn.addEventListener('click', async () => {
        const text = newsInput.value.trim();
        if (!text) {
            alert('Please enter a paragraph of news to analyze.');
            return;
        }

        // Show loading state
        resultSection.classList.remove('hidden');
        resultContent.classList.add('hidden');
        if (webVerification) webVerification.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');
        if (sourceList) sourceList.innerHTML = ''; // Clear previous sources
        if (searchKeywords) searchKeywords.textContent = ''; // Clear previous keywords

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: text })
            });

            if (!response.ok) {
                throw new Error('API returned an error');
            }

            const data = await response.json();

            // Hide spinner and show result
            loadingSpinner.classList.add('hidden');
            resultContent.classList.remove('hidden');

            const isReal = data.prediction === 'Real';

            // Set Linguistic Prediction
            resultLabel.textContent = "AI Analysis: " + data.prediction;
            resultLabel.className = ''; // Reset classes
            resultLabel.classList.add(isReal ? 'real' : 'fake');

            resultMessage.textContent = isReal
                ? 'Based on writing style, this appears authentic.'
                : 'Caution: Based on writing style, this appears fabricated.';

            // Set Web Verification Data
            if (webVerification) {
                if (data.keywords && searchKeywords) {
                    searchKeywords.textContent = 'Searched Keywords: "' + data.keywords + '"';
                }

                if (data.web_verified && data.sources.length > 0) {
                    webVerification.classList.remove('hidden');
                    webBadge.textContent = '✅ Verified by Web Search Agent';
                    webBadge.style.color = '#10b981'; // Success green

                    data.sources.forEach(source => {
                        const li = document.createElement('li');
                        const a = document.createElement('a');
                        a.href = source.href;
                        a.target = '_blank';
                        a.style.color = '#6366f1';
                        a.style.textDecoration = 'none';
                        a.style.display = 'flex';
                        a.style.justifyContent = 'space-between';
                        a.style.alignItems = 'center';

                        let titleHTML = `<span>${source.title}</span>`;
                        let badgesHTML = `<div class="source-badges">`;

                        // Semantic Similarity Badge
                        badgesHTML += `<span class="badge similarity-badge">${source.similarity}% Match</span>`;

                        // Trusted Domain Badge
                        if (source.is_trusted) {
                            badgesHTML += `<span class="badge trusted-badge">⭐ Trusted Source</span>`;
                        }

                        badgesHTML += `</div>`;

                        a.innerHTML = titleHTML + badgesHTML;
                        li.appendChild(a);
                        sourceList.appendChild(li);
                    });
                } else if (!isReal) {
                    // Fake and not on web
                    webVerification.classList.remove('hidden');
                    webBadge.textContent = '❌ No semantic match found on trusted web sources';
                    webBadge.style.color = '#ef4444'; // Danger red
                } else {
                    // Real linguistically, but not on web
                    webVerification.classList.remove('hidden');
                    webBadge.textContent = '⚠️ Could not semantically verify this specific text on the web.';
                    webBadge.style.color = '#f59e0b'; // Warning yellow
                }
            }

        } catch (error) {
            console.error('Error:', error);
            loadingSpinner.classList.add('hidden');
            resultContent.classList.remove('hidden');

            resultLabel.textContent = 'Error';
            resultLabel.className = '';
            resultLabel.classList.add('fake');
            resultMessage.textContent = 'Failed to connect to the AI service. Make sure the backend is running.';
        }
    });
});
