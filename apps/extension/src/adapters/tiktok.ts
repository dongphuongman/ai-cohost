import type { Comment, PlatformAdapter, PlatformSelectors, SmartPasteResult } from './types';
import { smartPaste } from '@/content/smart-paste';

export class TikTokAdapter implements PlatformAdapter {
  readonly platform = 'tiktok' as const;
  readonly hostPatterns = ['www.tiktok.com'];
  readonly selectors: PlatformSelectors;
  private observer: MutationObserver | null = null;
  private seenTexts = new Set<string>();

  constructor(selectors?: Partial<PlatformSelectors>) {
    this.selectors = {
      liveIndicator: '[data-e2e="live-badge"], [class*="LiveTag"], [class*="live-indicator"]',
      chatContainer: '[data-e2e="chat-list"], [class*="DivChatListContainer"], [class*="chat-list"]',
      commentItem: '[data-e2e="chat-message"], [class*="DivChatMessage"], [class*="chat-message"]',
      commentAuthor: '[data-e2e="chat-username"], [class*="SpanUserName"], [class*="chat-username"]',
      commentText: '[data-e2e="chat-message-text"], [class*="SpanChatText"], [class*="chat-text"]',
      commentInput: '[data-e2e="chat-input"] input, [class*="DivInputContainer"] input, [class*="chat-input"] input',
      sendButton: '[data-e2e="chat-send-btn"], [class*="DivSendButton"], [class*="send-btn"]',
      ...selectors,
    };
  }

  detectLiveSession(): boolean {
    // TikTok live pages have /live/ in path or the live badge
    const isLivePath = window.location.pathname.includes('/@') && window.location.pathname.includes('/live');
    return isLivePath || !!document.querySelector(this.selectors.liveIndicator);
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
