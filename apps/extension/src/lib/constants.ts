export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";
export const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
export const DASHBOARD_URL = import.meta.env.VITE_DASHBOARD_URL ?? "http://localhost:3000";

export const STORAGE_KEYS = {
  AUTH_TOKEN: "authToken",
  REFRESH_TOKEN: "refreshToken",
  OVERLAY_POSITION: "overlayPosition",
  ONBOARDING_SEEN: "onboardingSeen",
  ACTIVE_SESSION: "activeSession",
} as const;

export const WS_PING_INTERVAL = 30_000;
export const WS_MAX_RECONNECTS = 10;
export const SMART_PASTE_SEND_TIMEOUT = 30_000;
