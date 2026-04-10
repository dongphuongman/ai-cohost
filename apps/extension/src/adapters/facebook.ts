import type { Comment, PlatformAdapter, PlatformSelectors, SmartPasteResult } from './types';
import { smartPaste } from '@/content/smart-paste';

export class FacebookAdapter implements PlatformAdapter {
  readonly platform = 'facebook' as const;
  readonly hostPatterns = ['www.facebook.com'];
  readonly selectors: PlatformSelectors;
  private observer: MutationObserver | null = null;
  private seenTexts = new Set<string>();

  constructor(selectors?: Partial<PlatformSelectors>) {
    this.selectors = {
      liveIndicator: '[data-testid="live_video_badge"], .x1cy8zhl, [aria-label*="LIVE"], [aria-label*="Trực tiếp"]',
      chatContainer: '[role="log"], [aria-label*="Comment"], [aria-label*="chat"], [aria-label*="Bình luận"]',
      commentItem: '[data-testid="UFI2Comment/root_depth_0"], div[class*="x1lliihq"][class*="xkrqix3"]',
      commentAuthor: 'span.x3nfvp2 > a, span[dir="auto"] > a[role="link"]',
      commentText: 'div[dir="auto"][style], span[dir="auto"]',
      commentInput: 'div[role="textbox"][contenteditable="true"]',
      sendButton: 'div[aria-label="Comment"], div[aria-label="Bình luận"]',
      ...selectors,
    };
  }

  detectLiveSession(): boolean {
    return !!document.querySelector(this.selectors.liveIndicator);
  }

  getLiveUrl(): string | null {
    if (!this.detectLiveSession()) return null;
    return window.location.href;
  }

  readExistingComments(): Comment[] {
    const container = document.querySelector(this.selectors.chatContainer);
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

    const container = document.querySelector(this.selectors.chatContainer);
    if (!container) {
      // Retry after DOM settles — Facebook lazy-loads chat
      setTimeout(() => this.attachCommentObserver(callback), 2000);
      return;
    }

    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (!(node instanceof HTMLElement)) continue;

          // Check if the added node itself is a comment
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
    return document.querySelector(this.selectors.commentInput);
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
