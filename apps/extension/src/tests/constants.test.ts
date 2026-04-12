import { describe, it, expect } from "vitest";
import { STORAGE_KEYS, WS_PING_INTERVAL, WS_MAX_RECONNECTS } from "@/lib/constants";

describe("constants", () => {
  it("defines required storage keys", () => {
    expect(STORAGE_KEYS.AUTH_TOKEN).toBe("authToken");
    expect(STORAGE_KEYS.REFRESH_TOKEN).toBe("refreshToken");
    expect(STORAGE_KEYS.OVERLAY_POSITION).toBe("overlayPosition");
    expect(STORAGE_KEYS.ACTIVE_SESSION).toBe("activeSession");
  });

  it("has sensible WS config values", () => {
    expect(WS_PING_INTERVAL).toBe(30_000);
    expect(WS_MAX_RECONNECTS).toBe(10);
  });
});
