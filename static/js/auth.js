(function () {
    const originalFetch = window.fetch.bind(window);
    let refreshPromise = null;

    function getRequestUrl(input) {
        if (typeof input === 'string') return input;
        if (input instanceof URL) return input.toString();
        if (input instanceof Request) return input.url;
        return String(input);
    }

    function cloneFetchInput(input, init) {
        if (input instanceof Request) {
            return {
                input: input.clone(),
                init: init ? { ...init } : undefined
            };
        }
        return {
            input: input,
            init: init ? { ...init } : undefined
        };
    }

    function shouldHandle(url) {
        const target = String(url);
        return !target.includes('/auth/refresh') &&
            !target.includes('/auth/token') &&
            !target.includes('/auth/login-page') &&
            !target.includes('/auth/register-page');
    }

    async function refresh() {
        if (!refreshPromise) {
            refreshPromise = originalFetch('/auth/refresh', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { Accept: 'application/json' }
            }).finally(() => { refreshPromise = null; });
        }
        return refreshPromise;
    }

    function redirectToLogin() {
        const next = window.location.pathname + window.location.search;
        window.location.assign('/auth/login-page?next=' + encodeURIComponent(next));
    }

    async function restoreSessionOnPageLoadIfNeeded() {
        if (!document.cookie.split('; ').some(cookie => cookie.startsWith('refresh_token='))) {
            return;
        }
        if (window.location.pathname === '/auth/login-page' || window.location.pathname === '/auth/register-page') {
            return;
        }
        try {
            const response = await originalFetch('/auth/refresh', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { Accept: 'application/json' }
            });
            if (response.ok && window.location.pathname === '/') {
                window.location.replace('/dashboard');
            }
        } catch (error) {
            console.warn('Session restoration skipped:', error);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', restoreSessionOnPageLoadIfNeeded);
    } else {
        restoreSessionOnPageLoadIfNeeded();
    }

    window.fetch = async function (input, init) {
        const requestReplay = cloneFetchInput(input, init);
        const response = await originalFetch(input, init);
        if (response.status !== 401 || !shouldHandle(getRequestUrl(input))) return response;

        try {
            const refreshed = await refresh();
            if (!refreshed.ok) {
                redirectToLogin();
                return response;
            }
            return originalFetch(requestReplay.input, requestReplay.init);
        } catch (error) {
            console.error('Authentication refresh failed:', error);
            redirectToLogin();
            return response;
        }
    };
})();
