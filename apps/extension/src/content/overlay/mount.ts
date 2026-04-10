import { render, h } from 'preact';
import type { PlatformAdapter } from '@/adapters/types';
import type { SuggestionAction } from '@/types/messages';
import { Overlay } from './Overlay';

let overlayMounted = false;

/**
 * Mount the overlay Preact component into the page.
 * Injects a shadow DOM host to isolate styles from the page.
 */
export function mountOverlay(
  adapter: PlatformAdapter,
  callbacks: {
    onSendAction: (suggestionId: string, action: SuggestionAction, text?: string) => void;
    onSaveAsFaq: (question: string, answer: string) => void;
    onReadAloud: (text: string) => void;
    onPauseSession: () => void;
    onEndSession: () => void;
  },
): void {
  if (overlayMounted) return;

  const mountPoint = adapter.getOverlayMountPoint();

  // Create shadow root to isolate styles
  const shadow = mountPoint.attachShadow({ mode: 'open' });

  // Inject overlay styles
  const styleEl = document.createElement('style');
  // We'll inline the styles since we can't load CSS in shadow DOM from extension URL easily
  styleEl.textContent = getOverlayStyles();
  shadow.appendChild(styleEl);

  // Create Preact mount container
  const container = document.createElement('div');
  shadow.appendChild(container);

  render(
    h(Overlay, {
      onSendAction: callbacks.onSendAction,
      onSaveAsFaq: callbacks.onSaveAsFaq,
      onReadAloud: callbacks.onReadAloud,
      onPauseSession: callbacks.onPauseSession,
      onEndSession: callbacks.onEndSession,
      platform: adapter.platform,
    }),
    container,
  );

  overlayMounted = true;
}

/** Unmount the overlay from the page */
export function unmountOverlay(): void {
  const mountPoint = document.getElementById('ai-cohost-overlay-root');
  if (mountPoint) {
    mountPoint.remove();
    overlayMounted = false;
  }
}

/** Dispatch custom event to the overlay for incoming WS messages */
export function dispatchOverlayEvent(type: string, data: Record<string, unknown>): void {
  window.dispatchEvent(
    new CustomEvent('aco-overlay-event', { detail: { type, data } }),
  );
}

function getOverlayStyles(): string {
  // Inlined from styles.css — keeps overlay isolated in shadow DOM
  return `
#ai-cohost-overlay {
  position: fixed;
  z-index: 2147483647;
  width: 380px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  color: #1a1a2e;
  user-select: none;
}
.aco-panel {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,.12), 0 2px 8px rgba(0,0,0,.08);
  overflow: hidden;
  border: 1px solid rgba(91,71,224,.15);
}
.aco-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: linear-gradient(135deg, #5B47E0, #7C6CF0);
  color: #fff;
  cursor: grab;
}
.aco-header:active { cursor: grabbing; }
.aco-header-left { display: flex; align-items: center; gap: 8px; }
.aco-logo { font-weight: 700; font-size: 15px; }
.aco-live-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #10B981;
  animation: aco-pulse 1.5s ease-in-out infinite;
}
@keyframes aco-pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
.aco-header-actions { display: flex; gap: 6px; }
.aco-header-btn {
  background: rgba(255,255,255,.2); border: none; color: #fff;
  width: 26px; height: 26px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; transition: background .15s;
}
.aco-header-btn:hover { background: rgba(255,255,255,.3); }
.aco-stats {
  display: flex; justify-content: space-around; padding: 8px 14px;
  background: #f8f7ff; border-bottom: 1px solid #e8e5f5;
  font-size: 12px; color: #6b6b8a;
}
.aco-stat-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.aco-stat-value { font-weight: 600; font-size: 16px; color: #1a1a2e; }
.aco-suggestion { padding: 14px; border-bottom: 1px solid #eee; }
.aco-comment-display { background: #f5f5f7; border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; }
.aco-comment-user { font-weight: 600; font-size: 12px; color: #5B47E0; margin-bottom: 4px; }
.aco-comment-text { font-size: 13px; color: #333; line-height: 1.4; }
.aco-reply-preview {
  background: #f0eeff; border: 1px solid #d4cff7; border-radius: 8px;
  padding: 10px 12px; margin-bottom: 10px; font-size: 13px;
  line-height: 1.5; color: #1a1a2e; white-space: pre-wrap;
}
.aco-reply-preview[contenteditable="true"] { outline: none; border-color: #5B47E0; background: #fff; }
.aco-actions { display: flex; gap: 8px; }
.aco-btn {
  flex: 1; padding: 8px 0; border: none; border-radius: 8px;
  font-size: 13px; font-weight: 500; cursor: pointer; transition: all .15s;
}
.aco-btn-primary { background: #5B47E0; color: #fff; }
.aco-btn-primary:hover { background: #4a37d0; }
.aco-btn-secondary { background: #f0eeff; color: #5B47E0; }
.aco-btn-secondary:hover { background: #e2deff; }
.aco-shortcut { font-size: 10px; opacity: .7; margin-left: 4px; }
.aco-history { max-height: 200px; overflow-y: auto; padding: 8px 14px; }
.aco-history-empty { text-align: center; padding: 16px; color: #999; font-size: 13px; }
.aco-history-item {
  display: flex; align-items: center; gap: 8px; padding: 8px 0;
  border-bottom: 1px solid #f0f0f0; font-size: 12px;
}
.aco-history-item:last-child { border-bottom: none; }
.aco-history-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #555; }
.aco-history-badge { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 500; white-space: nowrap; }
.aco-badge-sent { background: #d1fae5; color: #065f46; }
.aco-badge-read { background: #dbeafe; color: #1e40af; }
.aco-badge-dismissed { background: #f3f4f6; color: #6b7280; }
.aco-badge-edited { background: #fef3c7; color: #92400e; }
.aco-badge-pasted_not_sent { background: #fde68a; color: #78350f; }
.aco-session-controls { display: flex; gap: 8px; padding: 10px 14px; border-top: 1px solid #eee; }
.aco-collapsed .aco-suggestion, .aco-collapsed .aco-history, .aco-collapsed .aco-session-controls { display: none; }
.aco-history::-webkit-scrollbar { width: 4px; }
.aco-history::-webkit-scrollbar-track { background: transparent; }
.aco-history::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }
.aco-streaming { opacity: 0.9; }
.aco-cursor {
  display: inline-block; width: 2px; height: 14px; background: #5B47E0;
  margin-left: 2px; vertical-align: text-bottom;
  animation: aco-blink 0.8s step-end infinite;
}
@keyframes aco-blink { 0%,100%{opacity:1} 50%{opacity:0} }
.aco-faq-checkbox {
  display: flex; align-items: center; gap: 6px; padding: 6px 0;
  font-size: 12px; color: #5B47E0; cursor: pointer; user-select: none;
}
.aco-faq-checkbox input { accent-color: #5B47E0; cursor: pointer; }
.aco-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  `;
}
