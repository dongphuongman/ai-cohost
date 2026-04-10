import { WS_URL, WS_PING_INTERVAL, WS_MAX_RECONNECTS } from './constants';
import type { WSClientMessage, WSServerMessage } from '@/types/messages';

type MessageHandler = (msg: WSServerMessage) => void;

export class WSClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private handlers = new Map<string, MessageHandler[]>();
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private token: string | null = null;
  private _connected = false;

  get connected(): boolean {
    return this._connected;
  }

  async connect(token: string): Promise<void> {
    this.token = token;
    this.cleanup();

    return new Promise((resolve, reject) => {
      const url = `${WS_URL}?token=${encodeURIComponent(token)}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this._connected = true;
        this.reconnectAttempts = 0;
        this.startPing();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg: WSServerMessage = JSON.parse(event.data);
          this.emit(msg.type, msg);
        } catch {
          // ignore malformed messages
        }
      };

      this.ws.onclose = (event) => {
        this._connected = false;
        this.stopPing();
        // 4001 = auth failed, don't reconnect
        if (event.code !== 4001) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        if (!this._connected) {
          reject(new Error('WebSocket connection failed'));
        }
      };
    });
  }

  send(msg: WSClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) this.handlers.set(type, []);
    this.handlers.get(type)!.push(handler);
    return () => {
      const list = this.handlers.get(type);
      if (list) {
        const idx = list.indexOf(handler);
        if (idx >= 0) list.splice(idx, 1);
      }
    };
  }

  disconnect(): void {
    this.cleanup();
    this.token = null;
    this.reconnectAttempts = WS_MAX_RECONNECTS; // prevent reconnect
    if (this.ws) {
      this.ws.close(1000, 'client disconnect');
      this.ws = null;
    }
    this._connected = false;
  }

  private emit(type: string, msg: WSServerMessage): void {
    const handlers = this.handlers.get(type);
    if (handlers) {
      for (const h of handlers) {
        try { h(msg); } catch { /* handler error */ }
      }
    }
    // Also emit to wildcard listeners
    const wildcardHandlers = this.handlers.get('*');
    if (wildcardHandlers) {
      for (const h of wildcardHandlers) {
        try { h(msg); } catch { /* handler error */ }
      }
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this.send({ type: 'ping' });
    }, WS_PING_INTERVAL);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= WS_MAX_RECONNECTS || !this.token) return;

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30_000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      if (this.token) {
        this.connect(this.token).catch(() => {
          // reconnect failed, will retry via onclose
        });
      }
    }, delay);
  }

  private cleanup(): void {
    this.stopPing();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

/** Singleton WS client for the extension */
export const wsClient = new WSClient();
