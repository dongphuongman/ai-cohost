import type { LiveComment, PlatformAdapter } from "./types";

export const tiktokAdapter: PlatformAdapter = {
  name: "tiktok",
  hostPatterns: ["www.tiktok.com"],

  detectLiveSession() {
    return false;
  },

  readComments(): LiveComment[] {
    return [];
  },

  attachCommentObserver(_callback) {
    return () => {};
  },

  injectOverlay(_container) {},

  async smartPaste(_text) {
    return false;
  },
};
