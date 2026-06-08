import { useCallback, useEffect, useState } from "react";
import ChatWidget from "./components/ChatWidget";
import { api } from "./api/client";
import { formatMessageTime } from "./utils/formatTime";
import { COUNSELOR_GREETING } from "./utils/conversation";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [backendOnline, setBackendOnline] = useState(true);
  const [showLead, setShowLead] = useState(false);
  const [showDemo, setShowDemo] = useState(false);

  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      setBackendOnline(true);
      setError("");
    } catch (err) {
      setBackendOnline(false);
      setError(err.message);
    }
  }, []);

  const checkBackend = useCallback(async () => {
    try {
      await api.health();
      setBackendOnline(true);
      setError("");
      await loadConversations();
      return true;
    } catch (err) {
      setBackendOnline(false);
      setError(
        err?.message ||
          "Backend unavailable — run .\\start_backend.ps1, then .\\start_frontend.ps1, open http://localhost:3000, and click Retry."
      );
      return false;
    }
  }, [loadConversations]);

  useEffect(() => {
    checkBackend();
  }, [checkBackend]);

  useEffect(() => {
    if (backendOnline) return undefined;
    const id = setInterval(() => {
      checkBackend();
    }, 5000);
    return () => clearInterval(id);
  }, [backendOnline, checkBackend]);

  const loadHistory = async (conversationId) => {
    try {
      const history = await api.getHistory(conversationId);
      setMessages(
        history.map((m, i) => ({
          id: `${conversationId}-${i}`,
          role: m.role,
          content: m.content,
          sources: m.sources,
          timestamp: m.timestamp,
        }))
      );
    } catch (err) {
      setError(err.message);
    }
  };

  const startNewChat = async () => {
    try {
      const conv = await api.createConversation();
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      setMessages([
        {
          ...COUNSELOR_GREETING,
          id: `greeting-${conv.id}`,
          timestamp: formatMessageTime(),
        },
      ]);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  };

  const selectConversation = async (id) => {
    setActiveConversationId(id);
    await loadHistory(id);
  };

  const deleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const ensureConversation = async () => {
    if (activeConversationId) return activeConversationId;
    const conv = await api.createConversation();
    setActiveConversationId(conv.id);
    setConversations((prev) => [conv, ...prev]);
    if (messages.length === 0) {
      setMessages([
        {
          ...COUNSELOR_GREETING,
          id: `greeting-${conv.id}`,
          timestamp: formatMessageTime(),
        },
      ]);
    }
    return conv.id;
  };

  const handleDemoBooked = (message, conversationId) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `demo-${Date.now()}`,
        role: "assistant",
        content: message,
        timestamp: formatMessageTime(),
      },
    ]);
    if (conversationId && conversationId !== activeConversationId) {
      setActiveConversationId(conversationId);
    }
  };

  const handleSend = async (question) => {
    let conversationId = activeConversationId;
    if (!conversationId) {
      const conv = await api.createConversation();
      conversationId = conv.id;
      setActiveConversationId(conv.id);
      setConversations((prev) => [conv, ...prev]);
      if (messages.length === 0) {
        setMessages([
          {
            ...COUNSELOR_GREETING,
            id: `greeting-${conv.id}`,
            timestamp: formatMessageTime(),
          },
        ]);
      }
    }

    const userMsg = {
      id: `u-${Date.now()}`,
      role: "user",
      content: question,
      timestamp: formatMessageTime(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError("");

    try {
      const data = await api.chat(question, conversationId);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: data.response,
          sources: data.sources,
          timestamp: formatMessageTime(),
          animate: true,
        },
      ]);
      loadConversations();
    } catch (err) {
      setError(err.message);
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `Sorry, something went wrong: ${err.message}`,
          timestamp: formatMessageTime(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative h-full w-full overflow-hidden bg-surface-muted">
      <div className="pointer-events-none flex h-full flex-col items-center justify-center p-6 text-center">
        <p className="max-w-md text-sm text-ink-muted">
          MACE AI Academy — use the chat assistant in the bottom-right corner for course
          guidance.
        </p>
      </div>

      <ChatWidget
        conversations={conversations}
        activeId={activeConversationId}
        messages={messages}
        loading={loading}
        error={error}
        showLead={showLead}
        showDemo={showDemo}
        onSelectConversation={selectConversation}
        onNewChat={startNewChat}
        onDeleteConversation={deleteConversation}
        onLead={() => setShowLead(true)}
        onDemo={() => setShowDemo(true)}
        onSend={handleSend}
        onCloseLead={() => setShowLead(false)}
        onCloseDemo={() => setShowDemo(false)}
        onEnsureConversation={ensureConversation}
        onDemoBooked={handleDemoBooked}
        onRetryBackend={checkBackend}
      />
    </div>
  );
}
