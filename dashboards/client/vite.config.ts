import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies the client API to the aggregator (typically forwarded
// from a remote droplet via SSH tunnel — `ssh -L 9201:127.0.0.1:9201`).
// Set FT_DEV_SLUG when running locally so /api/client/{slug}/* resolves to
// a real profile — without it the SPA tries to use window.location.hostname,
// which on `localhost` doesn't carry a slug.
const AGGREGATOR_URL = process.env.AGGREGATOR_URL ?? "http://127.0.0.1:9201";

export default defineConfig({
  // Served under /dash/ on each per-client subdomain — built assets reference
  // /dash/assets/* so Caddy's `handle_path /dash/*` strips the prefix correctly.
  base: "/dash/",
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      "/api/client": { target: AGGREGATOR_URL, changeOrigin: true },
      "/healthz": { target: AGGREGATOR_URL, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
