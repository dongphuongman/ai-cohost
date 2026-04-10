import type { PlatformAdapter, Comment } from '@/adapters/types';

export type CommentCallback = (comment: Comment) => void;

/**
 * Wraps a PlatformAdapter's comment observation with deduplication.
 * Content script creates one of these per session.
 */
export class CommentReader {
  private adapter: PlatformAdapter;
  private callback: CommentCallback | null = null;
  private active = false;

  constructor(adapter: PlatformAdapter) {
    this.adapter = adapter;
  }

  /** Read existing comments on page (initial load) */
  readExisting(): Comment[] {
    return this.adapter.readExistingComments();
  }

  /** Start observing for new comments */
  start(callback: CommentCallback): void {
    if (this.active) this.stop();
    this.callback = callback;
    this.active = true;
    this.adapter.attachCommentObserver((comment) => {
      this.callback?.(comment);
    });
  }

  /** Stop observing */
  stop(): void {
    this.adapter.detachCommentObserver();
    this.callback = null;
    this.active = false;
  }

  get isActive(): boolean {
    return this.active;
  }
}
