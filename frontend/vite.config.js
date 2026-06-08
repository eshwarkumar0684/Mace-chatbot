import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Resolve backend URL: same machine default; docker-compose frontend can override VITE_BACKEND_URL at build/dev time */
function backendTarget() {
  const fromEnv =
    typeof process.env.VITE_DEV_BACKEND_TARGET === "string"
      ? process.env.VITE_DEV_BACKEND_TARGET.trim()
      : "";
  return fromEnv || "http://127.0.0.1:8000";
}

const apiProxy = {
  "/api": {
    target: backendTarget(),
    changeOrigin: true,
    secure: false,
    ws: false,
    // First chat loads the embedding model — can take 1–3 minutes
    timeout: 300000,
    proxyTimeout: 300000,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: false,
    host: true,
    proxy: apiProxy,
  },
  preview: {
    port: 3000,
    host: true,
    proxy: apiProxy,
  },
});
