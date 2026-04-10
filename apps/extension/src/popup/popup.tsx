export function Popup() {
  return (
    <div class="p-4 space-y-4">
      <div class="flex items-center gap-2">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
          AI
        </div>
        <span class="text-lg font-semibold text-gray-900">Co-host</span>
      </div>

      <div class="rounded-lg border border-gray-200 bg-gray-50 p-3">
        <p class="text-sm text-gray-600">
          Mở một tab livestream trên Facebook, TikTok, YouTube hoặc Shopee để
          bắt đầu.
        </p>
      </div>

      <div class="space-y-2">
        <a
          href="http://localhost:3000/dashboard"
          target="_blank"
          rel="noreferrer"
          class="block w-full rounded-md bg-primary py-2 text-center text-sm font-medium text-white hover:bg-primary/90"
        >
          Mở Dashboard
        </a>
        <a
          href="http://localhost:3000/settings"
          target="_blank"
          rel="noreferrer"
          class="block w-full rounded-md border border-gray-200 py-2 text-center text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Trợ giúp
        </a>
      </div>
    </div>
  );
}
