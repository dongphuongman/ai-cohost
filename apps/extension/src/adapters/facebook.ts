import type { LiveComment, PlatformAdapter } from "./types";

export const facebookAdapter: PlatformAdapter = {
  name: "facebook",
  hostPatterns: ["www.facebook.com"],

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
