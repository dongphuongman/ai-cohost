import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json";

export default defineConfig({
  plugins: [preact(), crx({ manifest })],
  server: {
    port: 5174,
    strictPort: true,
    host: true,
    cors: true,
    hmr: {
      port: 5174,
    },
  },
  resolve: {
    alias: {
      "@": "/src",
    },
  },
});
