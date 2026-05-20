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

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: false,
    host: true,
    proxy: {
      "/api": {
        target: backendTarget(),
        changeOrigin: true,
        secure: false,
        ws: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
