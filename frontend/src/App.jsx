import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import LeadForm from "./components/LeadForm";
import { api } from "./api/client";
import { formatMessageTime } from "./utils/formatTime";
import { COUNSELOR_GREETING } from "./utils/conversation";

export default function App() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showLead, setShowLead] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [darkMode, setDarkMode] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

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
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        activeId={activeConversationId}
        onSelect={selectConversation}
        onNewChat={startNewChat}
        onDelete={deleteConversation}
        onLead={() => setShowLead(true)}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
      />

      <div className="flex flex-1 flex-col">
        {error && (
          <div className="border-b border-red-500/30 bg-red-500/10 px-4 py-2 text-center text-sm text-red-300">
            {error}
          </div>
        )}
        <ChatWindow
          messages={messages}
          loading={loading}
          onSend={handleSend}
          darkMode={darkMode}
          onToggleDark={() => setDarkMode((v) => !v)}
        />
      </div>

      {showLead && <LeadForm onClose={() => setShowLead(false)} />}
    </div>
  );
}
