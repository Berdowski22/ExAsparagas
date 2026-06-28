document.addEventListener('DOMContentLoaded', () => {
    const chatWindow = document.getElementById('chatWindow');
    const newsInput = document.getElementById('newsInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const wordCounter = document.getElementById('wordCounter');

    const outputModal = document.getElementById('outputModal');
    const modalContent = document.getElementById('modalContent');
    const modalClose = document.getElementById('modalClose');

    const API_URL = 'http://127.0.0.1:8000/predict';
    const MIN_WORDS = 20;

    // --- Auth guard + shared nav (see common.js) ---
    if (!Auth.requireLogin()) return;
    Auth.initNav('analyzer');
    const token = Auth.token;
    const logout = () => Auth.logout();

    // --- Popup (zoom) for AI output ---
    function openModal(bubble) {
        // Clone the rendered result so the popup shows the exact same content
        const clone = bubble.cloneNode(true);
        const actionsInClone = clone.querySelector('.bubble-actions');
        if (actionsInClone) actionsInClone.remove();

        modalContent.innerHTML = '';
        while (clone.firstChild) modalContent.appendChild(clone.firstChild);

        outputModal.hidden = false;
        modalContent.scrollTop = 0;
    }

    function closeModal() {
        outputModal.hidden = true;
        modalContent.innerHTML = '';
    }

    modalClose.addEventListener('click', closeModal);
    outputModal.addEventListener('click', (e) => {
        if (e.target === outputModal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !outputModal.hidden) closeModal();
    });

    // Share a finished analysis to the blog
    async function sharePost(btn, data) {
        if (btn.disabled) return;
        btn.disabled = true;
        const prev = btn.textContent;
        btn.textContent = '…';
        try {
            const res = await fetch(API_BASE + '/posts', {
                method: 'POST',
                headers: Auth.authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ news_text: data.__newsText || '', result: data })
            });
            if (res.status === 401) { logout(); return; }
            if (!res.ok) throw new Error('share failed');
            btn.textContent = '✓';
            btn.title = 'Shared to blog';
            btn.classList.add('shared');
        } catch (err) {
            console.error(err);
            btn.textContent = prev;
            btn.disabled = false;
            btn.title = 'Could not share — try again';
        }
    }

    // Adds the action buttons (share + zoom) to a finished result bubble.
    // shareable=false for "Not News" results, which aren't worth posting.
    function addBubbleActions(bubble, data, shareable) {
        bubble.classList.add('has-zoom');
        const actions = document.createElement('div');
        actions.className = 'bubble-actions';

        if (shareable) {
            const shareBtn = document.createElement('button');
            shareBtn.className = 'bubble-action-btn';
            shareBtn.type = 'button';
            shareBtn.title = 'Share to blog';
            shareBtn.setAttribute('aria-label', 'Share to blog');
            shareBtn.textContent = '📤';
            shareBtn.addEventListener('click', () => sharePost(shareBtn, data));
            actions.appendChild(shareBtn);
        }

        const zoomBtn = document.createElement('button');
        zoomBtn.className = 'bubble-action-btn';
        zoomBtn.type = 'button';
        zoomBtn.title = 'Expand output';
        zoomBtn.setAttribute('aria-label', 'Expand output');
        zoomBtn.textContent = '⤢';
        zoomBtn.addEventListener('click', () => openModal(bubble));
        actions.appendChild(zoomBtn);

        bubble.appendChild(actions);
    }

    // --- Word counting / validation ---
    function countWords(text) {
        const trimmed = text.trim();
        if (!trimmed) return 0;
        return trimmed.split(/\s+/).length;
    }

    function updateCounter() {
        const n = countWords(newsInput.value);
        if (n >= MIN_WORDS) {
            wordCounter.textContent = n + ' words';
            wordCounter.classList.add('ok');
            analyzeBtn.disabled = false;
        } else {
            wordCounter.textContent = n + ' / ' + MIN_WORDS + ' words minimum';
            wordCounter.classList.remove('ok');
            analyzeBtn.disabled = true;
        }
    }

    newsInput.addEventListener('input', updateCounter);
    updateCounter();

    // --- Chat helpers ---
    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function addUserMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'message user-message';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.textContent = text;
        msg.appendChild(bubble);
        chatWindow.appendChild(msg);
        scrollToBottom();
    }

    function addBotLoading() {
        const msg = document.createElement('div');
        msg.className = 'message bot-message';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
        msg.appendChild(bubble);
        chatWindow.appendChild(msg);
        scrollToBottom();
        return bubble; // we replace its content when the result arrives
    }

    // Build the analysis result inside a bot bubble (DOM nodes — safe from injection)
    function renderResult(bubble, data) {
        bubble.innerHTML = '';

        // Input was not news — this tool only fact-checks news, so show a clean notice
        if (data.prediction === 'Not News') {
            const badge = document.createElement('span');
            badge.className = 'verdict-badge uncertain';
            badge.textContent = 'Not News';
            bubble.appendChild(badge);

            const note = document.createElement('p');
            note.className = 'ml-line';
            note.textContent = '📰 ' + (data.verdict_detail ||
                'This tool only fact-checks news. Please paste a news report or claim.');
            bubble.appendChild(note);

            if (data.gemini_analysis) {
                const why = document.createElement('p');
                why.className = 'verdict-detail';
                why.textContent = data.gemini_analysis;
                bubble.appendChild(why);
            }
            addBubbleActions(bubble, data, false); // "Not News" isn't worth sharing
            return;
        }

        // Verdict badge
        const verdict = data.verdict || 'Uncertain';
        const badge = document.createElement('span');
        badge.className = 'verdict-badge';
        if (verdict === 'Likely Real') badge.classList.add('real');
        else if (verdict === 'Likely Fake') badge.classList.add('fake');
        else badge.classList.add('uncertain');
        badge.textContent = verdict;
        bubble.appendChild(badge);

        // Gemini verdict line
        const mlLine = document.createElement('p');
        mlLine.className = 'ml-line';
        if (data.prediction === 'Real') mlLine.textContent = '🟢 Gemini judged this authentic.';
        else if (data.prediction === 'Fake') mlLine.textContent = '🔴 Gemini judged this fabricated.';
        else mlLine.textContent = '🟡 Gemini was uncertain about this.';
        bubble.appendChild(mlLine);

        // Confidence bar
        const conf = data.confidence != null ? data.confidence : 50;
        const wrap = document.createElement('div');
        wrap.className = 'confidence-bar-wrap';
        wrap.innerHTML =
            '<span class="confidence-label">Gemini Confidence</span>' +
            '<div class="confidence-bar"><div class="confidence-fill"></div></div>' +
            '<span class="confidence-val"></span>';
        bubble.appendChild(wrap);
        wrap.querySelector('.confidence-fill').style.width = conf + '%';
        wrap.querySelector('.confidence-val').textContent = conf + '%';

        if (data.verdict_detail) {
            const detail = document.createElement('p');
            detail.className = 'verdict-detail';
            detail.textContent = data.verdict_detail;
            bubble.appendChild(detail);
        }

        // Web verification
        const web = document.createElement('div');
        web.className = 'web-verification';
        const webBadge = document.createElement('h3');

        if (data.web_verified && data.sources && data.sources.length > 0) {
            webBadge.textContent = '✅ Verified by Web Search Agent';
            webBadge.style.color = '#10b981';
        } else if (data.sources && data.sources.length > 0) {
            webBadge.textContent = '⚠️ Related results found, but no trusted source strongly matched.';
            webBadge.style.color = '#f59e0b';
        } else {
            webBadge.textContent = '❌ No web sources found for this text.';
            webBadge.style.color = '#ef4444';
        }
        web.appendChild(webBadge);

        if (data.keywords) {
            const kw = document.createElement('p');
            kw.className = 'search-keywords';
            kw.textContent = 'Searched Keywords: "' + data.keywords + '"';
            web.appendChild(kw);
        }

        if (data.sources && data.sources.length > 0) {
            const ul = document.createElement('ul');
            ul.className = 'source-list';
            data.sources.forEach(source => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = source.href;
                a.target = '_blank';
                a.rel = 'noopener noreferrer';

                const titleSpan = document.createElement('span');
                titleSpan.textContent = source.title;
                a.appendChild(titleSpan);

                const badges = document.createElement('div');
                badges.className = 'source-badges';
                const sim = document.createElement('span');
                sim.className = 'badge similarity-badge';
                sim.textContent = source.similarity + '% Match';
                badges.appendChild(sim);
                if (source.is_trusted) {
                    const trusted = document.createElement('span');
                    trusted.className = 'badge trusted-badge';
                    trusted.textContent = '⭐ Trusted Source';
                    badges.appendChild(trusted);
                }
                a.appendChild(badges);
                li.appendChild(a);
                ul.appendChild(li);
            });
            web.appendChild(ul);
        }
        bubble.appendChild(web);

        // Gemini AI analysis
        if (data.gemini_analysis || data.summary || (data.key_points && data.key_points.length)) {
            const card = document.createElement('div');
            card.className = 'gemini-card';
            const h3 = document.createElement('h3');
            h3.textContent = '✨ Gemini AI Analysis';
            card.appendChild(h3);

            // Bottom-line summary (bold lead)
            if (data.summary) {
                const sum = document.createElement('p');
                sum.className = 'gemini-summary';
                sum.textContent = data.summary;
                card.appendChild(sum);
            }

            // Key signals as a bullet list
            if (data.key_points && data.key_points.length > 0) {
                const ul = document.createElement('ul');
                ul.className = 'gemini-points';
                data.key_points.forEach(point => {
                    const li = document.createElement('li');
                    li.textContent = point;
                    ul.appendChild(li);
                });
                card.appendChild(ul);
            }

            // Full reasoning paragraph
            if (data.gemini_analysis) {
                const p = document.createElement('p');
                p.className = 'gemini-text';
                p.textContent = data.gemini_analysis;
                card.appendChild(p);
            }

            // Actionable recommendation
            if (data.recommendation) {
                const rec = document.createElement('p');
                rec.className = 'gemini-recommendation';
                rec.textContent = '👉 ' + data.recommendation;
                card.appendChild(rec);
            }

            bubble.appendChild(card);
        }

        addBubbleActions(bubble, data, true);
        scrollToBottom();
    }

    function renderError(bubble, message) {
        bubble.innerHTML = '';
        const err = document.createElement('p');
        err.className = 'error-text';
        err.textContent = '⚠️ ' + message;
        bubble.appendChild(err);
        scrollToBottom();
    }

    // --- Submit ---
    async function analyze() {
        const text = newsInput.value.trim();
        if (countWords(text) < MIN_WORDS) {
            return; // button is disabled below the minimum anyway
        }

        addUserMessage(text);
        newsInput.value = '';
        updateCounter();

        const loadingBubble = addBotLoading();

        try {
            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({ text: text })
            });

            // Session expired / invalid → back to login
            if (response.status === 401) {
                logout();
                return;
            }

            if (!response.ok) {
                throw new Error('API returned an error');
            }

            const data = await response.json();
            data.__newsText = text; // keep the source text so it can be shared to the blog
            renderResult(loadingBubble, data);
        } catch (error) {
            console.error('Error:', error);
            renderError(loadingBubble, 'Failed to connect to the AI service. Make sure the backend is running.');
        }
    }

    analyzeBtn.addEventListener('click', analyze);

    // Ctrl+Enter submits
    newsInput.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !analyzeBtn.disabled) {
            analyze();
        }
    });
});
