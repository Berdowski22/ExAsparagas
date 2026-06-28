document.addEventListener('DOMContentLoaded', () => {
    const API_BASE = 'http://127.0.0.1:8000';

    const tabLogin = document.getElementById('tabLogin');
    const tabSignup = document.getElementById('tabSignup');
    const form = document.getElementById('authForm');
    const usernameField = document.getElementById('usernameField');
    const identifierLabel = document.getElementById('identifierLabel');
    const identifierInput = document.getElementById('identifier');
    const passwordInput = document.getElementById('password');
    const usernameInput = document.getElementById('username');
    const roleField = document.getElementById('roleField');
    const submitBtn = document.getElementById('submitBtn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnIcon = submitBtn.querySelector('.btn-icon');
    const message = document.getElementById('authMessage');
    const subtitle = document.getElementById('authSubtitle');
    const switchPrompt = document.getElementById('switchPrompt');
    const switchLink = document.getElementById('switchLink');

    let mode = 'login'; // 'login' | 'signup'

    // Already signed in? Skip the page.
    if (localStorage.getItem('token')) {
        window.location.href = 'index.html';
        return;
    }

    function showMessage(text, type) {
        message.textContent = text;
        message.className = 'auth-message ' + (type || '');
        message.hidden = false;
    }
    function clearMessage() {
        message.hidden = true;
        message.textContent = '';
    }

    function setMode(next) {
        mode = next;
        clearMessage();
        const isSignup = mode === 'signup';

        tabLogin.classList.toggle('active', !isSignup);
        tabSignup.classList.toggle('active', isSignup);

        usernameField.hidden = !isSignup;
        roleField.hidden = !isSignup;

        identifierLabel.textContent = isSignup ? 'Email' : 'Username or email';
        identifierInput.placeholder = isSignup ? 'you@example.com' : 'username or you@example.com';
        identifierInput.type = isSignup ? 'email' : 'text';
        identifierInput.autocomplete = isSignup ? 'email' : 'username';
        passwordInput.autocomplete = isSignup ? 'new-password' : 'current-password';

        subtitle.textContent = isSignup
            ? 'Create an account to get started'
            : 'Welcome back — sign in to continue';
        btnText.textContent = isSignup ? 'Create account' : 'Sign in';
        btnIcon.textContent = isSignup ? '✨' : '🔓';
        switchPrompt.textContent = isSignup ? 'Already have an account?' : "Don't have an account?";
        switchLink.textContent = isSignup ? 'Sign in' : 'Create one';
    }

    tabLogin.addEventListener('click', () => setMode('login'));
    tabSignup.addEventListener('click', () => setMode('signup'));
    switchLink.addEventListener('click', (e) => {
        e.preventDefault();
        setMode(mode === 'login' ? 'signup' : 'login');
    });

    function setLoading(loading) {
        submitBtn.disabled = loading;
        btnText.textContent = loading
            ? 'Please wait…'
            : (mode === 'signup' ? 'Create account' : 'Sign in');
    }

    async function submit(e) {
        e.preventDefault();
        clearMessage();

        const password = passwordInput.value;
        if (!password) {
            showMessage('Please enter your password.', 'error');
            return;
        }

        let url, payload;
        if (mode === 'signup') {
            const username = usernameInput.value.trim();
            const email = identifierInput.value.trim();
            const role = (form.querySelector('input[name="role"]:checked') || {}).value || 'casual';
            if (username.length < 3) { showMessage('Username must be at least 3 characters.', 'error'); return; }
            if (!email) { showMessage('Please enter your email.', 'error'); return; }
            if (password.length < 6) { showMessage('Password must be at least 6 characters.', 'error'); return; }
            url = API_BASE + '/auth/signup';
            payload = { username, email, password, role };
        } else {
            const identifier = identifierInput.value.trim();
            if (!identifier) { showMessage('Please enter your username or email.', 'error'); return; }
            url = API_BASE + '/auth/login';
            payload = { identifier, password };
        }

        setLoading(true);
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                showMessage(data.detail || 'Something went wrong. Please try again.', 'error');
                setLoading(false);
                return;
            }

            // Save session and go to the app
            localStorage.setItem('token', data.access_token);
            localStorage.setItem('user', JSON.stringify(data.user));

            if (mode === 'signup' && data.user.role === 'journalist') {
                showMessage('Account created! Journalist access is pending admin approval.', 'success');
            } else {
                showMessage('Success! Redirecting…', 'success');
            }
            setTimeout(() => { window.location.href = 'index.html'; }, 700);
        } catch (err) {
            console.error(err);
            showMessage('Could not reach the server. Is the backend running?', 'error');
            setLoading(false);
        }
    }

    form.addEventListener('submit', submit);
    setMode('login');
});
