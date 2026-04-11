import type { Comment, PlatformAdapter, PlatformSelectors, SmartPasteResult } from './types';
import { smartPaste } from '@/content/smart-paste';

/**
 * Adapter for the live-stream-simulator.html test page.
 * Reuses Facebook-compatible DOM selectors so the same detection logic works.
 * DEV ONLY — should not ship to Chrome Web Store.
 */
export class SimulatorAdapter implements PlatformAdapter {
  readonly platform = 'facebook' as const;
  readonly hostPatterns = ['localhost'];
  readonly selectors: PlatformSelectors;
  private observer: MutationObserver | null = null;
  private seenTexts = new Set<string>();

  constructor() {
    this.selectors = {
      liveIndicator: '[data-testid="live_video_badge"]',
      chatContainer: '[role="log"], #chatMessages',
      commentItem: '[data-testid="UFI2Comment/root_depth_0"]',
      commentAuthor: '.chat-author a[role="link"], .chat-author',
      commentText: '.chat-text',
      commentInput: '[role="textbox"][contenteditable="true"], #chatInput',
      sendButton: '.send-button',
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
