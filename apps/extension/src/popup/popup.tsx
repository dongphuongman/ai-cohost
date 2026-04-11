import { useState, useEffect, useCallback } from 'preact/hooks';
import type { ActiveSession } from '@/lib/storage';
import { DASHBOARD_URL, API_URL } from '@/lib/constants';

interface LiveDetection {
  isLive: boolean;
  platform: string | null;
  url: string | null;
}

interface Shop {
  id: number;
  name: string;
}

interface Product {
  id: number;
  name: string;
}

interface Persona {
  id: number;
  name: string;
  is_default: boolean;
}

async function apiFetch<T>(path: string, token: string, shopId?: number): Promise<T | null> {
  try {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    };
    if (shopId) headers['X-Shop-Id'] = String(shopId);
    const res = await fetch(`${API_URL}${path}`, { headers });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function Popup() {
  const [token, setToken] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [liveDetection, setLiveDetection] = useState<LiveDetection | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  // Session config state
  const [shops, setShops] = useState<Shop[]>([]);
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersonaId, setSelectedPersonaId] = useState<number | null>(null);
  const [configLoading, setConfigLoading] = useState(false);

  useEffect(() => {
    chrome.runtime.sendMessage({ type: 'GET_AUTH_TOKEN' }, (res) => {
      const t = res?.token ?? null;
      setToken(t);
      if (t) loadShops(t);
    });
    chrome.runtime.sendMessage({ type: 'GET_SESSION_STATUS' }, (res) => {
      setActiveSession(res?.session ?? null);
      setWsConnected(res?.connected ?? false);
    });

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

  const loadShops = useCallback(async (t: string) => {
    const me = await apiFetch<{ shops: { shop_id: number; shop_name: string }[] }>('/auth/me', t);
    if (me?.shops?.length) {
      const shopList = me.shops.map((s) => ({ id: s.shop_id, name: s.shop_name }));
      setShops(shopList);
      // Auto-select first shop or restore from storage
      chrome.storage.local.get(['lastShopId'], (stored) => {
        const lastId = stored.lastShopId;
        const match = shopList.find((s) => s.id === lastId);
        const pick = match ?? shopList[0];
        setSelectedShopId(pick.id);
        loadShopData(t, pick.id);
      });
    }
  }, []);

  const loadShopData = useCallback(async (t: string, shopId: number) => {
    setConfigLoading(true);
    const [prodRes, persRes] = await Promise.all([
      apiFetch<{ items: Product[] }>('/products?page_size=100', t, shopId),
      apiFetch<Persona[]>('/personas', t, shopId),
    ]);
    setProducts(prodRes?.items ?? []);
    const personaList = persRes ?? [];
    setPersonas(personaList);

    // Restore last selections or use defaults
    chrome.storage.local.get(['lastProductIds', 'lastPersonaId'], (stored) => {
      if (stored.lastProductIds?.length) {
        const validIds = (stored.lastProductIds as number[]).filter((id: number) =>
          (prodRes?.items ?? []).some((p) => p.id === id),
        );
        setSelectedProductIds(validIds.length ? validIds : []);
      } else {
        setSelectedProductIds([]);
      }
      const defaultPersona = personaList.find((p) => p.is_default) ?? personaList[0];
      const lastPid = stored.lastPersonaId;
      const matchPersona = personaList.find((p) => p.id === lastPid);
      setSelectedPersonaId(matchPersona?.id ?? defaultPersona?.id ?? null);
    });

    setConfigLoading(false);
  }, []);

  const handleShopChange = (shopId: number) => {
    setSelectedShopId(shopId);
    setSelectedProductIds([]);
    setSelectedPersonaId(null);
    chrome.storage.local.set({ lastShopId: shopId });
    if (token) loadShopData(token, shopId);
  };

  const toggleProduct = (id: number) => {
    setSelectedProductIds((prev) => {
      const next = prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id].slice(0, 5);
      chrome.storage.local.set({ lastProductIds: next });
      return next;
    });
  };

  const handlePersonaChange = (id: number) => {
    setSelectedPersonaId(id);
    chrome.storage.local.set({ lastPersonaId: id });
  };

  const handleStartSession = async () => {
    if (!liveDetection?.isLive || starting || !selectedShopId || !selectedPersonaId) return;
    setStarting(true);

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab?.id) return;

      chrome.runtime.sendMessage(
        {
          type: 'START_SESSION',
          tabId: tab.id,
          shopId: selectedShopId,
          productIds: selectedProductIds,
          personaId: selectedPersonaId,
          platform: liveDetection!.platform,
        },
        (res) => {
          setStarting(false);
          if (res?.sessionId) {
            setActiveSession({
              sessionId: res.sessionId,
              platform: liveDetection!.platform!,
              startedAt: new Date().toISOString(),
              shopId: selectedShopId,
              productIds: selectedProductIds,
              personaId: selectedPersonaId,
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

  // --- Not authenticated ---
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
          href={`${DASHBOARD_URL}/login`}
          target="_blank"
          rel="noreferrer"
          class="block w-full rounded-md bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary/90"
        >
          Đăng nhập
        </a>
      </div>
    );
  }

  // --- Main UI ---
  return (
    <div class="p-4 space-y-3" style="width:360px">
      <Header />

      {/* Active session */}
      {activeSession && (
        <div class="rounded-lg border border-green-200 bg-green-50 p-3">
          <div class="flex items-center gap-2 mb-2">
            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span class="text-sm font-medium text-green-800">Session đang chạy</span>
          </div>
          <p class="text-xs text-green-600 mb-2">
            Platform: {activeSession.platform} | WS: {wsConnected ? 'Kết nối' : 'Mất kết nối'}
          </p>
          <button
            onClick={handleEndSession}
            class="w-full rounded-md border border-red-200 bg-white py-1.5 text-center text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Kết thúc session
          </button>
        </div>
      )}

      {/* Live detection + session config */}
      {!activeSession && !loading && (
        <>
          {liveDetection?.isLive ? (
            <div class="space-y-3">
              <div class="rounded-lg border border-purple-200 bg-purple-50 p-3">
                <p class="text-sm text-purple-800">
                  Phát hiện livestream trên <strong>{liveDetection.platform}</strong>
                </p>
              </div>

              {configLoading ? (
                <p class="text-xs text-gray-500 text-center">Đang tải cấu hình...</p>
              ) : (
                <>
                  {/* Shop selector */}
                  {shops.length > 1 && (
                    <div>
                      <label class="block text-xs font-medium text-gray-700 mb-1">Shop</label>
                      <select
                        class="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                        value={selectedShopId ?? ''}
                        onChange={(e) => handleShopChange(Number((e.target as HTMLSelectElement).value))}
                      >
                        {shops.map((s) => (
                          <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Product selector */}
                  <div>
                    <label class="block text-xs font-medium text-gray-700 mb-1">
                      Sản phẩm ({selectedProductIds.length}/5)
                    </label>
                    {products.length === 0 ? (
                      <p class="text-xs text-gray-400">Chưa có sản phẩm. Thêm trên Dashboard.</p>
                    ) : (
                      <div class="max-h-28 overflow-y-auto space-y-1 rounded-md border border-gray-200 p-2">
                        {products.map((p) => (
                          <label key={p.id} class="flex items-center gap-2 cursor-pointer text-xs">
                            <input
                              type="checkbox"
                              checked={selectedProductIds.includes(p.id)}
                              onChange={() => toggleProduct(p.id)}
                              class="rounded"
                            />
                            <span class="truncate">{p.name}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Persona selector */}
                  {personas.length > 0 && (
                    <div>
                      <label class="block text-xs font-medium text-gray-700 mb-1">Persona</label>
                      <div class="flex flex-wrap gap-1.5">
                        {personas.map((p) => (
                          <button
                            key={p.id}
                            onClick={() => handlePersonaChange(p.id)}
                            class={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                              selectedPersonaId === p.id
                                ? 'bg-primary text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            {p.name}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Start button */}
                  <button
                    onClick={handleStartSession}
                    disabled={starting || !selectedPersonaId}
                    class="w-full rounded-md bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
                  >
                    {starting ? 'Đang kết nối...' : 'Bắt đầu session'}
                  </button>
                </>
              )}
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
          href={`${DASHBOARD_URL}/dashboard`}
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
