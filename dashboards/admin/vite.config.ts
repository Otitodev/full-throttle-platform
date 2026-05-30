import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies admin API + healthz to the aggregator running on the
// droplet (or whatever AGGREGATOR_URL points at). Lets the SPA hit
// `/api/admin/*` directly without CORS in dev.
const AGGREGATOR_URL = process.env.AGGREGATOR_URL ?? "http://127.0.0.1:9201";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api/admin": { target: AGGREGATOR_URL, changeOrigin: true },
      "/healthz": { target: AGGREGATOR_URL, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
