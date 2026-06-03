document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyzeBtn');
    const newsInput = document.getElementById('newsInput');
    const resultSection = document.getElementById('resultSection');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const resultContent = document.getElementById('resultContent');
    const resultLabel = document.getElementById('resultLabel');
    const resultMessage = document.getElementById('resultMessage');

    const API_URL = 'http://127.0.0.1:8001/predict';

    analyzeBtn.addEventListener('click', async () => {
        const text = newsInput.value.trim();
        if (!text) {
            alert('Please enter a paragraph of news to analyze.');
            return;
        }

        // Show loading state
        resultSection.classList.remove('hidden');
        resultContent.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');
        
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
            
            resultLabel.textContent = data.prediction;
            resultLabel.className = ''; // Reset classes
            resultLabel.classList.add(isReal ? 'real' : 'fake');
            
            resultMessage.textContent = isReal 
                ? 'This news paragraph appears to be authentic and fact-based.' 
                : 'Caution: This news paragraph appears to be fabricated or misleading.';

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
