export interface Comment {
  externalUserId?: string;
  externalUserName: string;
  text: string;
  receivedAt: Date;
  rawElement?: HTMLElement;
}

export interface SmartPasteResult {
  success: boolean;
  error?: 'input_not_found' | 'paste_failed' | 'input_disabled';
}

export interface PlatformSelectors {
  liveIndicator: string;
  chatContainer: string;
  commentItem: string;
  commentAuthor: string;
  commentText: string;
  commentInput: string;
  sendButton: string;
}

export type PlatformName = 'facebook' | 'youtube' | 'tiktok' | 'shopee';

export interface PlatformAdapter {
  readonly platform: PlatformName;
  readonly hostPatterns: string[];
  readonly selectors: PlatformSelectors;

  detectLiveSession(): boolean;
  getLiveUrl(): string | null;
  readExistingComments(): Comment[];
  attachCommentObserver(callback: (comment: Comment) => void): void;
  detachCommentObserver(): void;
  findCommentInput(): HTMLElement | null;
  getOverlayMountPoint(): HTMLElement;
  smartPaste(text: string): Promise<SmartPasteResult>;
}
