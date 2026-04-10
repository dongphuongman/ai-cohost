import type { PlatformAdapter } from "./types";
import { facebookAdapter } from "./facebook";
import { tiktokAdapter } from "./tiktok";
import { youtubeAdapter } from "./youtube";
import { shopeeAdapter } from "./shopee";

export type { PlatformAdapter, LiveComment } from "./types";

const adapters: PlatformAdapter[] = [
  facebookAdapter,
  tiktokAdapter,
  youtubeAdapter,
  shopeeAdapter,
];

export function detectPlatform(hostname: string): PlatformAdapter | null {
  return adapters.find((a) => a.hostPatterns.includes(hostname)) ?? null;
}
