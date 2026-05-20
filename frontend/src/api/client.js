/** Dev/proxy vs production backend URL */
function resolveApiBase() {
  const envUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
  const isDev = !!import.meta.env.DEV;
  if (isDev) {
    if (typeof window !== "undefined") {
      return `${window.location.origin}/api`;
    }
    return "/api";
  }
  return envUrl || "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const url = `${API_BASE}${path}`;
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err) {
    const msg =
      err?.message || "Network error — is the backend running on port 8000?";
    throw new Error(msg);
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || d).join(", ")
          : `Request failed (${response.status})`;
    throw new Error(message);
  }

  return data;
}

export const api = {
  health: () => request("/health"),
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
  reingest: () => request("/reingest", { method: "POST" }),
  analytics: () => request("/admin/analytics"),
};

export { API_BASE };
