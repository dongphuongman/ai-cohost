import type { LiveComment, PlatformAdapter } from "./types";

export const shopeeAdapter: PlatformAdapter = {
  name: "shopee",
  hostPatterns: ["live.shopee.vn"],

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
