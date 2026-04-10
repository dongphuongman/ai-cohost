import type { LiveComment, PlatformAdapter } from "./types";

export const youtubeAdapter: PlatformAdapter = {
  name: "youtube",
  hostPatterns: ["www.youtube.com"],

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
