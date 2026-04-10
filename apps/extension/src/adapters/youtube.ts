import type { Comment, PlatformAdapter, PlatformSelectors, SmartPasteResult } from './types';
import { smartPaste } from '@/content/smart-paste';

export class YouTubeAdapter implements PlatformAdapter {
  readonly platform = 'youtube' as const;
  readonly hostPatterns = ['www.youtube.com'];
  readonly selectors: PlatformSelectors;
  private observer: MutationObserver | null = null;
  private seenTexts = new Set<string>();

  constructor(selectors?: Partial<PlatformSelectors>) {
    this.selectors = {
      liveIndicator: '.ytp-live-badge[disabled], .ytp-live, ytd-badge-supported-renderer .badge-style-type-live-now',
      chatContainer: 'yt-live-chat-item-list-renderer #items',
      commentItem: 'yt-live-chat-text-message-renderer',
      commentAuthor: '#author-name',
      commentText: '#message',
      commentInput: 'yt-live-chat-text-input-field-renderer #input',
      sendButton: 'yt-live-chat-text-input-field-renderer #send-button button',
      ...selectors,
    };
  }

  detectLiveSession(): boolean {
    // YouTube live chat is inside an iframe
    const chatFrame = document.querySelector('iframe#chatframe') as HTMLIFrameElement | null;
    if (chatFrame) return true;
    // Also check for inline live badge
    return !!document.querySelector(this.selectors.liveIndicator);
  }

  getLiveUrl(): string | null {
    if (!this.detectLiveSession()) return null;
    return window.location.href;
  }

  private getChatDocument(): Document | null {
    const chatFrame = document.querySelector('iframe#chatframe') as HTMLIFrameElement | null;
    try {
      return chatFrame?.contentDocument ?? document;
    } catch {
      // Cross-origin — fall back to main document (popout chat)
      return document;
    }
  }

  readExistingComments(): Comment[] {
    const doc = this.getChatDocument();
    if (!doc) return [];

    const container = doc.querySelector(this.selectors.chatContainer);
    if (!container) return [];

    const items = container.querySelectorAll(this.selectors.commentItem);
    const comments: Comment[] = [];

    items.forEach((item) => {
      const comment = this.parseCommentElement(item as HTMLElement);
      if (comment && !this.seenTexts.has(comment.text)) {
        this.seenTexts.add(comment.text);
        comments.push(comment);
      }
    });

    return comments;
  }

  attachCommentObserver(callback: (comment: Comment) => void): void {
    this.detachCommentObserver();

    const doc = this.getChatDocument();
    if (!doc) return;

    const container = doc.querySelector(this.selectors.chatContainer);
    if (!container) {
      setTimeout(() => this.attachCommentObserver(callback), 2000);
      return;
    }

    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;

          const items = node.matches(this.selectors.commentItem)
            ? [node]
            : Array.from(node.querySelectorAll(this.selectors.commentItem));

          for (const item of items) {
            const comment = this.parseCommentElement(item as HTMLElement);
            if (comment && !this.seenTexts.has(comment.text)) {
              this.seenTexts.add(comment.text);
              callback(comment);
            }
          }
        }
      }
    });

    this.observer.observe(container, { childList: true, subtree: true });
  }

  detachCommentObserver(): void {
    this.observer?.disconnect();
    this.observer = null;
  }

  findCommentInput(): HTMLElement | null {
    const doc = this.getChatDocument();
    return doc?.querySelector(this.selectors.commentInput) ?? null;
  }

  getOverlayMountPoint(): HTMLElement {
    let mount = document.getElementById('ai-cohost-overlay-root');
    if (!mount) {
      mount = document.createElement('div');
      mount.id = 'ai-cohost-overlay-root';
      document.body.appendChild(mount);
    }
    return mount;
  }

  async smartPaste(text: string): Promise<SmartPasteResult> {
    return smartPaste(text, this);
  }

  private parseCommentElement(el: HTMLElement): Comment | null {
    const authorEl = el.querySelector(this.selectors.commentAuthor);
    const textEl = el.querySelector(this.selectors.commentText);

    const userName = authorEl?.textContent?.trim();
    const text = textEl?.textContent?.trim();

    if (!userName || !text) return null;

    return {
      externalUserName: userName,
      text,
      receivedAt: new Date(),
      rawElement: el,
    };
  }
}
