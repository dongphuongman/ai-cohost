import { STORAGE_KEYS } from "./constants";

export async function getStorageValue<T>(key: string): Promise<T | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get([key], (result) => {
      resolve((result[key] as T) ?? null);
    });
  });
}

export async function setStorageValue(key: string, value: unknown): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: value }, resolve);
  });
}

export async function removeStorageValue(key: string): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove(key, resolve);
  });
}

export interface OverlayPosition {
  x: number;
  y: number;
}

export async function getOverlayPosition(): Promise<OverlayPosition> {
  const pos = await getStorageValue<OverlayPosition>(STORAGE_KEYS.OVERLAY_POSITION);
  return pos ?? { x: window.innerWidth - 400, y: 20 };
}

export async function saveOverlayPosition(pos: OverlayPosition): Promise<void> {
  await setStorageValue(STORAGE_KEYS.OVERLAY_POSITION, pos);
}

export interface ActiveSession {
  sessionId: string;
  platform: string;
  startedAt: string;
  shopId: number;
  productIds: number[];
  personaId: number;
}

export async function getActiveSession(): Promise<ActiveSession | null> {
  return getStorageValue<ActiveSession>(STORAGE_KEYS.ACTIVE_SESSION);
}

export async function saveActiveSession(session: ActiveSession): Promise<void> {
  await setStorageValue(STORAGE_KEYS.ACTIVE_SESSION, session);
}

export async function clearActiveSession(): Promise<void> {
  await removeStorageValue(STORAGE_KEYS.ACTIVE_SESSION);
}
