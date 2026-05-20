// In dev, use Vite proxy (/api -> backend) to avoid CORS and connection issues
const API_BASE = import.meta.env.DEV
  ? "/api"
  : (import.meta.env.VITE_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000");

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

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
