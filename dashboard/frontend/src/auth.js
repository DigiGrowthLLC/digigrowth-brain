// App-level auth for the internal OS — replaces reliance on the browser's
// native HTTP Basic Auth popup, which desktop Chrome shows reliably on the
// first 401 but mobile browsers often don't surface at all for background
// fetch() calls (the app shell loads fine since it's served with no auth —
// see main.py's SPA fallback — but every /api/* call just silently 401s
// with no visible prompt). Storing the credential ourselves and attaching
// it explicitly to every request works the same on every browser/device.
//
// require_auth() in the backend (main.py) only checks credentials.password,
// so the username half of Basic Auth is unused — any fixed string works.

const STORAGE_KEY = "dg_auth";
const BASIC_USER = "dashboard";

export function getAuthHeader() {
  const token = localStorage.getItem(STORAGE_KEY);
  return token ? `Basic ${token}` : null;
}

export function setAuthPassword(password) {
  localStorage.setItem(STORAGE_KEY, btoa(`${BASIC_USER}:${password}`));
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
}

// Wraps window.fetch once at startup so every existing `fetch("/api/...")`
// call across the app (dozens of panels/modals) gets the Authorization
// header for free, with no per-call-site changes. On a 401 it clears the
// stored credential and fires an event AuthGate listens for, so an
// expired/changed password bounces the user back to the login screen
// instead of panels just silently showing no data.
export function installAuthFetch() {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url || "";
    if (url.startsWith("/api")) {
      const authHeader = getAuthHeader();
      if (authHeader) {
        const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : undefined));
        if (!headers.has("Authorization")) headers.set("Authorization", authHeader);
        init = { ...init, headers };
      }
    }
    return nativeFetch(input, init).then((res) => {
      if (res.status === 401 && url.startsWith("/api")) {
        clearAuth();
        window.dispatchEvent(new Event("dg-auth-invalid"));
      }
      return res;
    });
  };
}
