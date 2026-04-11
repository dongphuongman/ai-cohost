/**
 * Content script injected into localhost:3000 (Dashboard).
 * Syncs auth tokens from Dashboard localStorage → extension chrome.storage.local.
 */
import { STORAGE_KEYS } from "@/lib/constants";

function syncTokens() {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");

  // Only push tokens TO the extension when the dashboard has them.
  // Never remove — the extension may have valid tokens from a prior login
  // and the dashboard page may simply not have loaded its auth state yet.
  if (accessToken && refreshToken) {
    chrome.storage.local.set({
      [STORAGE_KEYS.AUTH_TOKEN]: accessToken,
      [STORAGE_KEYS.REFRESH_TOKEN]: refreshToken,
    });
  }
}

// Sync on page load
syncTokens();

// Re-sync whenever localStorage changes (login/logout in another tab)
window.addEventListener("storage", (e) => {
  if (e.key === "access_token" || e.key === "refresh_token") {
    syncTokens();
  }
});

// Handle explicit logout: only clear extension tokens when the dashboard
// transitions FROM having a token TO not having one (user logged out).
let lastToken = localStorage.getItem("access_token");
setInterval(() => {
  const current = localStorage.getItem("access_token");
  if (current !== lastToken) {
    if (!current && lastToken) {
      // Dashboard had a token and now doesn't → explicit logout
      chrome.storage.local.remove([STORAGE_KEYS.AUTH_TOKEN, STORAGE_KEYS.REFRESH_TOKEN]);
    } else if (current) {
      syncTokens();
    }
    lastToken = current;
  }
}, 2000);
