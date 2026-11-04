(function () {
    const originalFetch = window.fetch.bind(window);
    let refreshPromise = null;

    function shouldHandle(url) {
        return !String(url).includes('/auth/refresh') &&
            !String(url).includes('/auth/token') &&
            !String(url).includes('/auth/login-page') &&
            !String(url).includes('/auth/register-page');
    }

    async function refresh() {
        if (!refreshPromise) {
            refreshPromise = originalFetch('/auth/refresh', {
                method: 'POST',
                credentials: 'same-origin'
            }).finally(() => { refreshPromise = null; });
        }
        return refreshPromise;
    }

    window.fetch = async function (input, init) {
        const response = await originalFetch(input, init);
        if (response.status !== 401 || !shouldHandle(input)) return response;

        try {
            const refreshed = await refresh();
            if (refreshed.ok) return originalFetch(input, init);
        } catch (error) {
            console.error('Authentication refresh failed:', error);
        }

        const next = window.location.pathname + window.location.search;
        window.location.assign('/auth/login-page?next=' + encodeURIComponent(next));
        return response;
    };
})();
