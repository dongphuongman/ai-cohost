import type { PlatformAdapter } from './types';
import { FacebookAdapter } from './facebook';
import { YouTubeAdapter } from './youtube';
import { TikTokAdapter } from './tiktok';
import { ShopeeAdapter } from './shopee';
import { SimulatorAdapter } from './simulator';

export type { PlatformAdapter, Comment, SmartPasteResult, PlatformName } from './types';

const adapters: PlatformAdapter[] = [
  new FacebookAdapter(),
  new YouTubeAdapter(),
  new TikTokAdapter(),
  new ShopeeAdapter(),
];

/**
 * Detect the live-stream platform adapter for the current page.
 * On localhost, checks for the simulator page before falling back to normal detection.
 */
export function detectPlatform(hostname: string): PlatformAdapter | null {
  // Simulator detection — dev only (localhost or file:// protocol)
  const path = window.location.pathname;
  const isLocalDev =
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    window.location.protocol === 'file:';
  if (isLocalDev && (path.includes('test-live') || path.includes('live-stream-simulator'))) {
    console.log('[AI Co-host] Detected: Live Stream Simulator');
    return new SimulatorAdapter();
  }

  return adapters.find((a) => a.hostPatterns.some((h) => hostname.includes(h))) ?? null;
}
