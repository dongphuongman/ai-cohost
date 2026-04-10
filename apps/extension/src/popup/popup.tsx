import { useState, useEffect } from 'preact/hooks';
import type { ActiveSession } from '@/lib/storage';

interface LiveDetection {
  isLive: boolean;
  platform: string | null;
  url: string | null;
}

export function Popup() {
  const [token, setToken] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [liveDetection, setLiveDetection] = useState<LiveDetection | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    // Load auth & session state
    chrome.runtime.sendMessage({ type: 'GET_AUTH_TOKEN' }, (res) => {
      setToken(res?.token ?? null);
    });
    chrome.runtime.sendMessage({ type: 'GET_SESSION_STATUS' }, (res) => {
      setActiveSession(res?.session ?? null);
      setWsConnected(res?.connected ?? false);
    });

    // Detect live on current tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (tab?.id) {
        chrome.tabs.sendMessage(tab.id, { type: 'DETECT_LIVE' }, (res) => {
          setLiveDetection(res ?? { isLive: false, platform: null, url: null });
          setLoading(false);
        });
      } else {
        setLoading(false);
      }
    });
  }, []);

  const handleStartSession = async () => {
    if (!liveDetection?.isLive || starting) return;
    setStarting(true);

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab?.id) return;

      chrome.runtime.sendMessage(
        {
          type: 'START_SESSION',
          tabId: tab.id,
          shopId: 1, // TODO: get from user selection
          productIds: [],
          personaId: 1, // TODO: get from user selection
          platform: liveDetection!.platform,
        },
        (res) => {
          setStarting(false);
          if (res?.sessionId) {
            setActiveSession({
              sessionId: res.sessionId,
              platform: liveDetection!.platform!,
              startedAt: new Date().toISOString(),
              shopId: 1,
              productIds: [],
              personaId: 1,
            });
          }
        },
      );
    });
  };

  const handleEndSession = () => {
    if (!activeSession) return;
    chrome.runtime.sendMessage({ type: 'END_SESSION', sessionId: activeSession.sessionId }, () => {
      setActiveSession(null);
      setWsConnected(false);
    });
  };

  if (!token) {
    return (
      <div class="p-4 space-y-4">
        <Header />
        <div class="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p class="text-sm text-gray-600">
            Vui lòng đăng nhập trên Dashboard trước khi sử dụng extension.
          </p>
        </div>
        <a
          href="http://localhost:3000/login"
          target="_blank"
          rel="noreferrer"
          class="block w-full rounded-md bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary/90"
        >
          Đăng nhập
        </a>
      </div>
    );
  }

  return (
    <div class="p-4 space-y-4">
      <Header />

      {/* Active session */}
      {activeSession && (
        <div class="rounded-lg border border-green-200 bg-green-50 p-3">
          <div class="flex items-center gap-2 mb-2">
            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span class="text-sm font-medium text-green-800">Session đang chạy</span>
          </div>
          <p class="text-xs text-green-600 mb-2">
            Platform: {activeSession.platform} | WS: {wsConnected ? 'Connected' : 'Disconnected'}
          </p>
          <button
            onClick={handleEndSession}
            class="w-full rounded-md border border-red-200 bg-white py-1.5 text-center text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Kết thúc session
          </button>
        </div>
      )}

      {/* Live detection */}
      {!activeSession && !loading && (
        <>
          {liveDetection?.isLive ? (
            <div class="rounded-lg border border-purple-200 bg-purple-50 p-3">
              <p class="text-sm text-purple-800 mb-2">
                Phát hiện livestream trên <strong>{liveDetection.platform}</strong>
              </p>
              <button
                onClick={handleStartSession}
                disabled={starting}
                class="w-full rounded-md bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
              >
                {starting ? 'Đang kết nối...' : 'Bắt đầu session'}
              </button>
            </div>
          ) : (
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <p class="text-sm text-gray-600">
                Mở một tab livestream trên Facebook, TikTok, YouTube hoặc Shopee để bắt đầu.
              </p>
            </div>
          )}
        </>
      )}

      {loading && (
        <div class="rounded-lg border border-gray-200 bg-gray-50 p-3 text-center">
          <p class="text-sm text-gray-500">Đang kiểm tra...</p>
        </div>
      )}

      <div class="space-y-2">
        <a
          href="http://localhost:3000/dashboard"
          target="_blank"
          rel="noreferrer"
          class="block w-full rounded-md border border-gray-200 py-2 text-center text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Mở Dashboard
        </a>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div class="flex items-center gap-2">
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
        AI
      </div>
      <span class="text-lg font-semibold text-gray-900">Co-host</span>
    </div>
  );
}
