import { STORAGE_KEYS, API_URL } from "./constants";
import { getStorageValue, setStorageValue, removeStorageValue } from "./storage";

export async function getAuthToken(): Promise<string | null> {
  return getStorageValue<string>(STORAGE_KEYS.AUTH_TOKEN);
}

export async function setAuthTokens(token: string, refreshToken: string): Promise<void> {
  await setStorageValue(STORAGE_KEYS.AUTH_TOKEN, token);
  await setStorageValue(STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
}

export async function clearAuth(): Promise<void> {
  await removeStorageValue(STORAGE_KEYS.AUTH_TOKEN);
  await removeStorageValue(STORAGE_KEYS.REFRESH_TOKEN);
}

export async function refreshAuthToken(): Promise<string | null> {
  const refreshToken = await getStorageValue<string>(STORAGE_KEYS.REFRESH_TOKEN);
  if (!refreshToken) return null;

  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      await clearAuth();
      return null;
    }

    const data = await res.json();
    await setAuthTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function isAuthenticated(): Promise<boolean> {
  const token = await getAuthToken();
  return token !== null;
}
