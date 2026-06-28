document.addEventListener('DOMContentLoaded', () => {
    if (!Auth.requireLogin()) return;
    Auth.initNav('blog');

    const feed = document.getElementById('blogFeed');
    const outputModal = document.getElementById('outputModal');
    const modalContent = document.getElementById('modalContent');
    const modalClose = document.getElementById('modalClose');

    // --- small DOM helpers ---
    function el(tag, className, text) {
        const e = document.createElement(tag);
        if (className) e.className = className;
        if (text != null) e.textContent = text;
        return e;
    }

    function formatDate(iso) {
        try {
            return new Date(iso).toLocaleString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric',
                hour: '2-digit', minute: '2-digit'
            });
        } catch (e) { return ''; }
    }

    // --- modal (expand a post) ---
    function openModal(buildContent) {
        modalContent.innerHTML = '';
        buildContent(modalContent);
        outputModal.hidden = false;
        modalContent.scrollTop = 0;
    }
    function closeModal() {
        outputModal.hidden = true;
        modalContent.innerHTML = '';
    }
    modalClose.addEventListener('click', closeModal);
    outputModal.addEventListener('click', (e) => { if (e.target === outputModal) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !outputModal.hidden) closeModal(); });

    // --- render the AI analysis body (mirrors the analyzer's look) ---
    function renderAnalysis(container, result) {
        const verdict = result.verdict || 'Uncertain';
        const badge = el('span', 'verdict-badge');
        if (/real/i.test(verdict)) badge.classList.add('real');
        else if (/fake/i.test(verdict)) badge.classList.add('fake');
        else badge.classList.add('uncertain');
        badge.textContent = verdict;
        container.appendChild(badge);

        if (result.confidence != null) {
            const wrap = el('div', 'confidence-bar-wrap');
            wrap.innerHTML =
                '<span class="confidence-label">Confidence</span>' +
                '<div class="confidence-bar"><div class="confidence-fill"></div></div>' +
                '<span class="confidence-val"></span>';
            container.appendChild(wrap);
            wrap.querySelector('.confidence-fill').style.width = result.confidence + '%';
            wrap.querySelector('.confidence-val').textContent = result.confidence + '%';
        }

        if (result.summary || (result.key_points && result.key_points.length) || result.gemini_analysis) {
            const card = el('div', 'gemini-card');
            card.appendChild(el('h3', null, '✨ Gemini AI Analysis'));
            if (result.summary) card.appendChild(el('p', 'gemini-summary', result.summary));
            if (result.key_points && result.key_points.length) {
                const ul = el('ul', 'gemini-points');
                result.key_points.forEach(p => ul.appendChild(el('li', null, p)));
                card.appendChild(ul);
            }
            if (result.gemini_analysis) card.appendChild(el('p', 'gemini-text', result.gemini_analysis));
            if (result.recommendation) card.appendChild(el('p', 'gemini-recommendation', '👉 ' + result.recommendation));
            container.appendChild(card);
        }

        if (result.sources && result.sources.length) {
            const web = el('div', 'web-verification');
            web.appendChild(el('h3', null, '🔎 Web sources'));
            const ul = el('ul', 'source-list');
            result.sources.forEach(s => {
                const li = el('li');
                const a = el('a');
                a.href = s.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
                a.appendChild(el('span', null, s.title));
                const badges = el('div', 'source-badges');
                badges.appendChild(el('span', 'badge similarity-badge', s.similarity + '% Match'));
                if (s.is_trusted) badges.appendChild(el('span', 'badge trusted-badge', '⭐ Trusted'));
                a.appendChild(badges);
                li.appendChild(a);
                ul.appendChild(li);
            });
            web.appendChild(ul);
            container.appendChild(web);
        }
    }

    // --- verification bar (counts + journalist buttons) ---
    function renderVerifyBar(post) {
        const bar = el('div', 'verify-bar');

        // Status / counts
        const counts = el('div', 'verify-counts');
        const correct = el('span', 'verify-chip correct', '✓ ' + post.correct_count);
        const incorrect = el('span', 'verify-chip incorrect', '✗ ' + post.incorrect_count);
        counts.appendChild(correct);
        counts.appendChild(incorrect);

        // Overall status label
        let status = el('span', 'verify-status');
        if (post.correct_count === 0 && post.incorrect_count === 0) {
            status.textContent = 'Awaiting journalist review';
            status.classList.add('pending');
        } else if (post.correct_count > post.incorrect_count) {
            status.textContent = '✅ Verified accurate';
            status.classList.add('ok');
        } else if (post.incorrect_count > post.correct_count) {
            status.textContent = '⚠️ Disputed by journalists';
            status.classList.add('bad');
        } else {
            status.textContent = '🤝 Mixed reviews';
            status.classList.add('mixed');
        }
        counts.appendChild(status);
        bar.appendChild(counts);

        // Journalist-only action buttons
        if (post.can_verify) {
            const actions = el('div', 'verify-actions');

            const yes = el('button', 'verify-btn yes' + (post.my_vote === true ? ' active' : ''), '✓ Correct');
            yes.type = 'button';
            yes.addEventListener('click', () => vote(post, true));

            const no = el('button', 'verify-btn no' + (post.my_vote === false ? ' active' : ''), '✗ Incorrect');
            no.type = 'button';
            no.addEventListener('click', () => vote(post, false));

            actions.appendChild(yes);
            actions.appendChild(no);
            bar.appendChild(actions);
        }

        return bar;
    }

    // --- a single post card ---
    function renderCard(post) {
        const card = el('article', 'blog-card');
        card.dataset.id = post.id;

        // Header: author + date + actions
        const head = el('div', 'blog-card-head');
        head.appendChild(el('span', 'user-avatar', '👤'));

        const who = el('div', 'blog-who');
        const nameRow = el('div', 'blog-author');
        nameRow.appendChild(el('span', null, post.author));
        const roleBadge = el('span', 'user-role-badge ' + (post.author_role || ''), post.author_role);
        nameRow.appendChild(roleBadge);
        who.appendChild(nameRow);
        who.appendChild(el('div', 'blog-date', formatDate(post.created_at)));
        head.appendChild(who);

        const acts = el('div', 'blog-card-actions');
        const zoom = el('button', 'bubble-action-btn', '⤢');
        zoom.type = 'button';
        zoom.title = 'Expand';
        zoom.addEventListener('click', () => openModal((c) => {
            const q = el('blockquote', 'blog-news-full', post.news_text);
            c.appendChild(q);
            renderAnalysis(c, post.result);
        }));
        acts.appendChild(zoom);

        if (post.is_mine || Auth.user.role === 'admin') {
            const del = el('button', 'bubble-action-btn danger', '🗑');
            del.type = 'button';
            del.title = 'Delete';
            del.addEventListener('click', () => removePost(post, card));
            acts.appendChild(del);
        }
        head.appendChild(acts);
        card.appendChild(head);

        // Shared news text (clamped; full view in modal)
        card.appendChild(el('blockquote', 'blog-news', post.news_text));

        // Analysis body
        const body = el('div', 'blog-analysis');
        renderAnalysis(body, post.result);
        card.appendChild(body);

        // Verification
        card.appendChild(renderVerifyBar(post));

        return card;
    }

    // --- actions ---
    async function vote(post, isCorrect) {
        // Clicking your current vote again retracts it
        const retract = post.my_vote === isCorrect;
        const url = API_BASE + '/posts/' + post.id + '/verify';
        try {
            const res = await fetch(url, {
                method: retract ? 'DELETE' : 'POST',
                headers: Auth.authHeaders(retract ? {} : { 'Content-Type': 'application/json' }),
                body: retract ? undefined : JSON.stringify({ is_correct: isCorrect })
            });
            if (res.status === 401) { Auth.logout(); return; }
            if (!res.ok) throw new Error('vote failed');
            const updated = await res.json();
            const oldCard = feed.querySelector('.blog-card[data-id="' + post.id + '"]');
            if (oldCard) oldCard.replaceWith(renderCard(updated));
        } catch (err) {
            console.error(err);
            alert('Could not submit your verification. Please try again.');
        }
    }

    async function removePost(post, card) {
        if (!confirm('Delete this shared analysis?')) return;
        try {
            const res = await fetch(API_BASE + '/posts/' + post.id, {
                method: 'DELETE',
                headers: Auth.authHeaders()
            });
            if (res.status === 401) { Auth.logout(); return; }
            if (!res.ok && res.status !== 204) throw new Error('delete failed');
            card.remove();
            if (!feed.querySelector('.blog-card')) showEmpty();
        } catch (err) {
            console.error(err);
            alert('Could not delete the post.');
        }
    }

    function showEmpty() {
        feed.innerHTML = '';
        const empty = el('div', 'blog-empty');
        empty.appendChild(el('p', 'blog-empty-emoji', '📭'));
        empty.appendChild(el('p', null, 'No analyses shared yet.'));
        const link = el('a', 'blog-empty-link', 'Go analyze some news →');
        link.href = 'index.html';
        empty.appendChild(link);
        feed.appendChild(empty);
    }

    // --- load feed ---
    async function loadFeed() {
        try {
            const res = await fetch(API_BASE + '/posts', { headers: Auth.authHeaders() });
            if (res.status === 401) { Auth.logout(); return; }
            if (!res.ok) throw new Error('load failed');
            const posts = await res.json();
            feed.innerHTML = '';
            if (!posts.length) { showEmpty(); return; }
            posts.forEach(p => feed.appendChild(renderCard(p)));
        } catch (err) {
            console.error(err);
            feed.innerHTML = '';
            feed.appendChild(el('p', 'error-text', '⚠️ Could not load the blog. Is the backend running?'));
        }
    }

    loadFeed();
});
