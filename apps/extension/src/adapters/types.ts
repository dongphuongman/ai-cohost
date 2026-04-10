export interface LiveComment {
  userId: string;
  userName: string;
  text: string;
  timestamp: number;
}

export interface PlatformAdapter {
  name: string;
  hostPatterns: string[];
  detectLiveSession(): boolean;
  readComments(): LiveComment[];
  attachCommentObserver(callback: (comment: LiveComment) => void): () => void;
  injectOverlay(container: HTMLElement): void;
  smartPaste(text: string): Promise<boolean>;
}
