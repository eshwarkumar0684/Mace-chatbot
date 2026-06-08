/** Dev/proxy vs production backend URL */
function isLocalHost() {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
}

function resolveApiBase() {
  const envUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, "");

  // Dev always uses Vite proxy — avoids CORS and "Failed to fetch"
  if (import.meta.env.DEV) {
    return typeof window !== "undefined"
      ? `${window.location.origin}/api`
      : "/api";
  }

  // Preview / local build on localhost: use /api proxy when configured in vite.config
  if (typeof window !== "undefined" && isLocalHost()) {
    return `${window.location.origin}/api`;
  }

  if (envUrl) return envUrl;

  return "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();
const DIRECT_BACKEND = "http://127.0.0.1:8000";

function networkErrorMessage(err, triedUrl) {
  const raw = err?.message || "";
  if (/failed to fetch|networkerror|load failed/i.test(raw)) {
    return (
      "Cannot reach the API. Start the backend: .\\start_backend.ps1 (port 8000), " +
      "then the frontend: .\\start_frontend.ps1 (port 3000). Open http://localhost:3000 and retry."
    );
  }
  return raw || `Network error (${triedUrl})`;
}

function extractErrorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || d).join(", ");
  if (detail && typeof detail === "object") {
    if (detail.message) return detail.message;
    if (detail.msg) return detail.msg;
  }
  if (status === 409) {
    return "You already have a demo on this date. Please pick another date.";
  }
  return `Request failed (${status})`;
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const bases = [API_BASE];
  // If Vite proxy fails but backend is up, try direct local API (CORS is open in dev)
  if (API_BASE.endsWith("/api") && isLocalHost()) {
    bases.push(DIRECT_BACKEND);
  }

  let lastErr = null;
  for (const base of bases) {
    const url = `${base}${path}`;
    try {
      const response = await fetch(url, { ...options, headers });
      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { detail: text };
        }
      }

      if (!response.ok) {
        const raw = extractErrorMessage(data, response.status);
        const isProxyOrDown =
          [502, 503, 504].includes(response.status) ||
          (response.status >= 500 &&
            (!raw ||
              /ECONNREFUSED|ECONNRESET|proxy error|socket hang up|ETIMEDOUT/i.test(
                raw
              ) ||
              /Internal Server Error|Bad Gateway|Gateway Timeout/i.test(
                String(text).slice(0, 300)
              )));
        if (isProxyOrDown && base !== bases[bases.length - 1]) {
          continue;
        }
        const err = new Error(
          isProxyOrDown
            ? "Backend unavailable — run .\\start_backend.ps1, wait for Uvicorn, then Retry."
            : raw
        );
        if (response.status === 409 && data?.detail && typeof data.detail === "object") {
          err.code = data.detail.code || "conflict";
          err.alternatives = data.detail.alternatives || [];
        }
        throw err;
      }

      return data;
    } catch (err) {
      if (err instanceof Error && err.message.startsWith("Request failed")) {
        throw err;
      }
      if (err instanceof Error && err.message.startsWith("Backend unavailable")) {
        lastErr = err;
        continue;
      }
      lastErr = new Error(networkErrorMessage(err, url));
      if (base !== bases[bases.length - 1]) continue;
    }
  }

  throw lastErr || new Error("Request failed.");
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const bases = [API_BASE];
  if (API_BASE.endsWith("/api") && isLocalHost()) {
    bases.push(DIRECT_BACKEND);
  }

  let lastErr = null;
  for (const base of bases) {
    const url = `${base}/upload`;
    try {
      const response = await fetch(url, { method: "POST", body: formData });
      const text = await response.text();
      let data = null;
      if (text) {
        try {
          data = JSON.parse(text);
        } catch {
          data = { detail: text };
        }
      }
      if (!response.ok) {
        const detail = data?.detail;
        const msg =
          typeof detail === "string"
            ? detail
            : `Upload failed (${response.status})`;
        if (
          [502, 503, 504].includes(response.status) &&
          base !== bases[bases.length - 1]
        ) {
          continue;
        }
        throw new Error(msg);
      }
      return data;
    } catch (err) {
      lastErr =
        err instanceof Error ? err : new Error(networkErrorMessage(err, url));
      if (base !== bases[bases.length - 1]) continue;
    }
  }
  throw lastErr || new Error("Upload failed.");
}

export const api = {
  health: () => request("/health"),
  uploadFile,
  listConversations: () => request("/conversations"),
  createConversation: (title = "New Chat") =>
    request("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (id) =>
    request(`/conversations/${id}`, { method: "DELETE" }),
  getHistory: (id) => request(`/conversations/${id}/history`),
  chat: (question, conversationId) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({ question, conversation_id: conversationId }),
    }),
  submitLead: (body) =>
    request("/leads", { method: "POST", body: JSON.stringify(body) }),
  getDemoDates: () => request("/demo/dates"),
  getBookingEmailStatus: (bookingId) =>
    request(`/demo/bookings/id/${bookingId}/email`),
  retryBookingEmail: (bookingId) =>
    request(`/demo/bookings/id/${bookingId}/retry-email`, { method: "POST" }),
  getEmailLogs: (status) =>
    request(status ? `/demo/email/logs?status=${encodeURIComponent(status)}` : "/demo/email/logs"),
  bookDemo: async (body) => {
    const bases = [API_BASE];
    if (API_BASE.endsWith("/api") && isLocalHost()) {
      bases.push(DIRECT_BACKEND);
    }
    let lastErr = null;
    for (const base of bases) {
      const url = `${base}/demo/book`;
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const text = await response.text();
        let data = null;
        if (text) {
          try {
            data = JSON.parse(text);
          } catch {
            data = { detail: text };
          }
        }
        if (response.status === 409) {
          const detail = data?.detail;
          const message =
            typeof detail === "object" && detail?.message
              ? detail.message
              : extractErrorMessage(data, 409);
          const err = new Error(message);
          err.code = (typeof detail === "object" && detail?.code) || "duplicate_booking";
          err.alternatives =
            (typeof detail === "object" && detail?.alternatives) || [];
          throw err;
        }
        if (!response.ok) {
          const detail = data?.detail;
          const msg =
            typeof detail === "string"
              ? detail
              : typeof detail === "object" && detail?.message
                ? detail.message
                : extractErrorMessage(data, response.status);
          throw new Error(msg);
        }
        return data;
      } catch (err) {
        if (err?.code === "duplicate_booking") throw err;
        lastErr = err instanceof Error ? err : new Error(String(err));
        if (base !== bases[bases.length - 1]) continue;
      }
    }
    throw lastErr || new Error("Booking failed.");
  },
  reingest: () => request("/reingest", { method: "POST" }),
  analytics: () => request("/admin/analytics"),
};

export { API_BASE };
