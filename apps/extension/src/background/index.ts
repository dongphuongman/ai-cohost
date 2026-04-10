import { wsClient } from '@/lib/ws-client';
import { getAuthToken } from '@/lib/auth';
import {
  getActiveSession,
  saveActiveSession,
  clearActiveSession,
  type ActiveSession,
} from '@/lib/storage';
import type { WSServerMessage } from '@/types/messages';

chrome.runtime.onInstalled.addListener(() => {
  console.log('[AI Co-host] Extension installed');
});

// Track which tab has the active session
let activeTabId: number | null = null;

// Handle messages from popup and content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender, sendResponse);
  return true; // keep channel open for async responses
});

async function handleMessage(
  message: Record<string, unknown>,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response?: unknown) => void,
) {
  try {
    switch (message.type) {
      case 'GET_AUTH_TOKEN': {
        const token = await getAuthToken();
        sendResponse({ token });
        break;
      }

      case 'START_SESSION': {
        const token = await getAuthToken();
        if (!token) {
          sendResponse({ error: 'not_authenticated' });
          return;
        }

        // Connect WS if not connected
        if (!wsClient.connected) {
          await wsClient.connect(token);
          setupWSHandlers();
        }

        // Send session.start to backend
        wsClient.send({
          type: 'session.start',
          shop_id: message.shopId as number,
          products: message.productIds as number[],
          persona_id: message.personaId as number,
          platform: message.platform as string,
        });

        // Wait for session.started response
        const sessionStarted = await waitForWSMessage('session.started', 10_000);
        if (!sessionStarted || sessionStarted.type !== 'session.started') {
          sendResponse({ error: 'session_start_timeout' });
          return;
        }

        const sessionData: ActiveSession = {
          sessionId: sessionStarted.session_id,
          platform: message.platform as string,
          startedAt: new Date().toISOString(),
          shopId: message.shopId as number,
          productIds: message.productIds as number[],
          personaId: message.personaId as number,
        };
        await saveActiveSession(sessionData);

        // Tell the content script to start
        activeTabId = message.tabId as number;
        chrome.tabs.sendMessage(activeTabId, {
          type: 'START_SESSION',
          sessionId: sessionStarted.session_id,
        });

        sendResponse({ sessionId: sessionStarted.session_id });
        break;
      }

      case 'END_SESSION_FROM_CONTENT':
      case 'END_SESSION': {
        const sid = (message.sessionId as string) ?? (await getActiveSession())?.sessionId;
        if (sid) {
          wsClient.send({ type: 'session.end', session_id: sid });
        }
        await clearActiveSession();
        wsClient.disconnect();
        activeTabId = null;
        sendResponse({ ok: true });
        break;
      }

      case 'NEW_COMMENT': {
        wsClient.send({
          type: 'comment.new',
          session_id: message.sessionId as string,
          comment: message.comment as {
            externalUserName: string;
            text: string;
            receivedAt: string;
            externalUserId?: string;
          },
        });
        sendResponse({ ok: true });
        break;
      }

      case 'SUGGESTION_ACTION': {
        const actionMsg: Record<string, unknown> = {
          type: 'suggestion.action',
          session_id: message.sessionId as string,
          suggestion_id: message.suggestionId as string,
          action: message.action as 'sent' | 'pasted_not_sent' | 'read' | 'dismissed' | 'edited',
        };
        if (message.editedText) {
          actionMsg.edited_text = message.editedText as string;
        }
        wsClient.send(actionMsg as any);
        sendResponse({ ok: true });
        break;
      }

      case 'SAVE_AS_FAQ': {
        // Call REST API to save FAQ learned from user edit
        const session = await getActiveSession();
        if (!session) {
          sendResponse({ error: 'no_session' });
          break;
        }
        try {
          const token = await getAuthToken();
          const productId = session.productIds?.[0];
          if (!token || !productId) {
            sendResponse({ error: 'missing_context' });
            break;
          }
          const { API_URL } = await import('@/lib/constants');
          const res = await fetch(
            `${API_URL}/products/${productId}/faqs/`,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({
                question: message.question as string,
                answer: message.answer as string,
                source: 'learned',
              }),
            },
          );
          sendResponse({ ok: res.ok });
        } catch (err) {
          sendResponse({ error: String(err) });
        }
        break;
      }

      case 'GET_SESSION_STATUS': {
        const session = await getActiveSession();
        sendResponse({ session, connected: wsClient.connected });
        break;
      }

      case 'DETECT_LIVE': {
        // Forward to content script in the given tab
        const tabId = message.tabId as number;
        chrome.tabs.sendMessage(tabId, { type: 'DETECT_LIVE' }, (response) => {
          sendResponse(response ?? { isLive: false, platform: null });
        });
        break;
      }

      default:
        sendResponse({ error: 'unknown_message_type' });
    }
  } catch (err) {
    console.error('[AI Co-host] Background error:', err);
    sendResponse({ error: String(err) });
  }
}

function setupWSHandlers() {
  // Forward WS messages to content script in active tab
  wsClient.on('*', (msg: WSServerMessage) => {
    if (
      activeTabId &&
      (msg.type === 'suggestion.new' ||
        msg.type === 'suggestion.stream' ||
        msg.type === 'suggestion.complete')
    ) {
      chrome.tabs.sendMessage(activeTabId, { type: 'WS_MESSAGE', data: msg });
    }
  });
}

function waitForWSMessage(type: string, timeoutMs: number): Promise<WSServerMessage | null> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      unsub();
      resolve(null);
    }, timeoutMs);

    const unsub = wsClient.on(type, (msg) => {
      clearTimeout(timer);
      unsub();
      resolve(msg);
    });
  });
}

// On startup, check for interrupted sessions
chrome.runtime.onStartup.addListener(async () => {
  const session = await getActiveSession();
  if (session) {
    // Previous session was interrupted (browser restart, etc.)
    await clearActiveSession();
  }
});
