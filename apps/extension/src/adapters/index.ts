import type { PlatformAdapter } from './types';
import { FacebookAdapter } from './facebook';
import { YouTubeAdapter } from './youtube';
import { TikTokAdapter } from './tiktok';
import { ShopeeAdapter } from './shopee';

export type { PlatformAdapter, Comment, SmartPasteResult, PlatformName } from './types';

const adapters: PlatformAdapter[] = [
  new FacebookAdapter(),
  new YouTubeAdapter(),
  new TikTokAdapter(),
  new ShopeeAdapter(),
];

export function detectPlatform(hostname: string): PlatformAdapter | null {
  return adapters.find((a) => a.hostPatterns.some((h) => hostname.includes(h))) ?? null;
}
