import { detectPlatform } from '@/adapters';
import type { PlatformAdapter, Comment } from '@/adapters/types';
import type { SuggestionAction, WSServerMessage } from '@/types/messages';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth';
import { CommentReader } from './comment-reader';
import { mountOverlay, unmountOverlay, dispatchOverlayEvent } from './overlay/mount';

let adapter: PlatformAdapter | null = null;
let commentReader: CommentReader | null = null;
let sessionId: string | null = null;
let currentAudio: HTMLAudioElement | null = null;

function init() {
  adapter = detectPlatform(window.location.hostname);
  if (!adapter) return;

  console.log(`[AI Co-host] Platform detected: ${adapter.platform}`);

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type === 'START_SESSION') {
      startSession(message.sessionId);
      sendResponse({ ok: true });
    } else if (message.type === 'END_SESSION') {
      endSession();
      sendResponse({ ok: true });
    } else if (message.type === 'WS_MESSAGE') {
      handleWSMessage(message.data);
      sendResponse({ ok: true });
    } else if (message.type === 'DETECT_LIVE') {
      sendResponse({
        isLive: adapter?.detectLiveSession() ?? false,
        platform: adapter?.platform ?? null,
        url: adapter?.getLiveUrl() ?? null,
      });
    }
    return true;
  });
}

function startSession(id: string) {
  if (!adapter) return;
  sessionId = id;

  // Mount overlay
  mountOverlay(adapter, {
    onSendAction: handleSuggestionAction,
    onSaveAsFaq: handleSaveAsFaq,
    onReadAloud: handleReadAloud,
    onPauseSession: handlePauseSession,
    onEndSession: handleEndSession,
  });

  // Start reading comments
  commentReader = new CommentReader(adapter);

  // Read existing comments first
  const existing = commentReader.readExisting();
  for (const comment of existing) {
    sendCommentToBackground(comment);
  }

  // Then observe new ones
  commentReader.start((comment) => {
    sendCommentToBackground(comment);
    dispatchOverlayEvent('comment.counted', {});
  });

  console.log(`[AI Co-host] Session started: ${id}`);
}

function endSession() {
  commentReader?.stop();
  commentReader = null;
  unmountOverlay();

  if (sessionId) {
    chrome.runtime.sendMessage({ type: 'END_SESSION_FROM_CONTENT', sessionId });
  }
  sessionId = null;
  console.log('[AI Co-host] Session ended');
}

function handleWSMessage(msg: WSServerMessage) {
  if (msg.type === 'suggestion.new') {
    dispatchOverlayEvent('suggestion.new', { suggestion: msg.suggestion });
  } else if (msg.type === 'suggestion.stream') {
    dispatchOverlayEvent('suggestion.stream', {
      suggestion_id: msg.suggestion_id,
      chunk: msg.chunk,
    });
  } else if (msg.type === 'suggestion.complete') {
    dispatchOverlayEvent('suggestion.complete', {
      suggestion_id: msg.suggestion_id,
    });
  }
}

function handleSuggestionAction(suggestionId: string, action: SuggestionAction, text?: string) {
  if (!adapter || !sessionId) return;

  if (action === 'sent' || action === 'edited') {
    // Smart paste the reply text into the comment input
    const pasteText = text ?? '';
    adapter.smartPaste(pasteText).then((result) => {
      const finalAction = result.success ? action : 'pasted_not_sent';
      const msg: Record<string, unknown> = {
        type: 'SUGGESTION_ACTION',
        sessionId,
        suggestionId,
        action: finalAction,
      };
      if (action === 'edited' && text) {
        msg.editedText = text;
      }
      chrome.runtime.sendMessage(msg);
    });
  } else {
    chrome.runtime.sendMessage({
      type: 'SUGGESTION_ACTION',
      sessionId,
      suggestionId,
      action,
    });
  }
}

function handlePauseSession() {
  commentReader?.stop();
  console.log('[AI Co-host] Session paused');
}

function handleEndSession() {
  endSession();
}

async function handleSaveAsFaq(question: string, answer: string) {
  try {
    const token = await getAuthToken();
    if (!token) return;
    // Use the first active product for now — the backend FAQ endpoint is per-product
    chrome.runtime.sendMessage({
      type: 'SAVE_AS_FAQ',
      question,
      answer,
    });
  } catch (err) {
    console.error('[AI Co-host] Save FAQ failed:', err);
  }
}

async function handleReadAloud(text: string) {
  try {
    // Stop any currently playing audio
    if (currentAudio) {
      currentAudio.pause();
      currentAudio = null;
    }
    const token = await getAuthToken();
    if (!token) return;
    const res = await fetch(`${API_URL}/tts/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      console.error('[AI Co-host] TTS failed:', res.status);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    currentAudio = new Audio(url);
    currentAudio.play();
    currentAudio.onended = () => {
      URL.revokeObjectURL(url);
      currentAudio = null;
    };
  } catch (err) {
    console.error('[AI Co-host] TTS error:', err);
  }
}

function sendCommentToBackground(comment: Comment) {
  if (!sessionId) return;
  chrome.runtime.sendMessage({
    type: 'NEW_COMMENT',
    sessionId,
    comment: {
      externalUserName: comment.externalUserName,
      externalUserId: comment.externalUserId,
      text: comment.text,
      receivedAt: comment.receivedAt.toISOString(),
    },
  });
}

// Initialize on load
init();
