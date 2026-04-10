import { detectPlatform } from "@/adapters";

const platform = detectPlatform(window.location.hostname);

if (platform) {
  console.log(`[AI Co-host] Platform detected: ${platform.name}`);
}
