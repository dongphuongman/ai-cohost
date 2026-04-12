import { describe, it, expect } from "vitest";
import { detectPlatform } from "@/adapters/index";

describe("detectPlatform", () => {
  it("detects Facebook", () => {
    const adapter = detectPlatform("www.facebook.com");
    expect(adapter).not.toBeNull();
    expect(adapter!.platform).toBe("facebook");
  });

  it("detects YouTube", () => {
    const adapter = detectPlatform("www.youtube.com");
    expect(adapter).not.toBeNull();
    expect(adapter!.platform).toBe("youtube");
  });

  it("detects TikTok", () => {
    const adapter = detectPlatform("www.tiktok.com");
    expect(adapter).not.toBeNull();
    expect(adapter!.platform).toBe("tiktok");
  });

  it("detects Shopee", () => {
    const adapter = detectPlatform("live.shopee.vn");
    expect(adapter).not.toBeNull();
    expect(adapter!.platform).toBe("shopee");
  });

  it("returns null for unknown domains", () => {
    expect(detectPlatform("google.com")).toBeNull();
    expect(detectPlatform("example.org")).toBeNull();
  });
});
