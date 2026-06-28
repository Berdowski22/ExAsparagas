// Shared auth + navigation helpers used by index.html (analyzer) and blog.html.
const API_BASE = 'http://127.0.0.1:8000';

const Auth = {
    get token() { return localStorage.getItem('token'); },

    get user() {
        try { return JSON.parse(localStorage.getItem('user') || '{}'); }
        catch (e) { return {}; }
    },

    // Redirect to the login page if there's no session. Returns false if redirected.
    requireLogin() {
        if (!this.token) {
            window.location.href = 'login.html';
            return false;
        }
        return true;
    },

    logout() {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = 'login.html';
    },

    authHeaders(extra) {
        return Object.assign({ 'Authorization': 'Bearer ' + this.token }, extra || {});
    },

    // Only verified journalists (and admins) may verify blog posts.
    canVerify() {
        const u = this.user;
        return u.role === 'admin' || (u.role === 'journalist' && u.is_verified);
    },

    // Fill the shared nav bar: user chip, role badge, active link, logout.
    initNav(activePage) {
        const u = this.user;

        const nameEl = document.getElementById('userName');
        if (nameEl) nameEl.textContent = u.username || '';

        const badge = document.getElementById('userRoleBadge');
        if (badge) {
            if (u.role === 'journalist' && !u.is_verified) {
                badge.textContent = 'Journalist · Pending';
                badge.classList.add('pending');
            } else {
                badge.textContent = u.role || '';
                if (u.role) badge.classList.add(u.role);
            }
        }

        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) logoutBtn.addEventListener('click', () => this.logout());

        document.querySelectorAll('.nav-link').forEach(a => {
            if (a.dataset.page === activePage) a.classList.add('active');
        });

        const nav = document.getElementById('navBar');
        if (nav) nav.hidden = false;
    }
};
