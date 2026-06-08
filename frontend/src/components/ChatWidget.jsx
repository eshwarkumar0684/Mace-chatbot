import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { History, Minus, X, CalendarDays } from "lucide-react";
import BotAvatar from "./BotAvatar";
import ChatWindow from "./ChatWindow";
import LeadForm from "./LeadForm";
import DemoBookForm from "./DemoBookForm";
import Sidebar from "./Sidebar";

const PANEL_MOTION = {
  initial: { opacity: 0, y: 20, scale: 0.96 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: 12, scale: 0.97 },
  transition: { type: "spring", stiffness: 380, damping: 32 },
};

const LAUNCHER_MOTION = {
  whileHover: { scale: 1.06 },
  whileTap: { scale: 0.96 },
  transition: { type: "spring", stiffness: 400, damping: 22 },
};

export default function ChatWidget({
  conversations,
  activeId,
  messages,
  loading,
  error,
  showLead,
  showDemo,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  onLead,
  onDemo,
  onSend,
  onCloseLead,
  onCloseDemo,
  onEnsureConversation,
  onDemoBooked,
  onRetryBackend,
}) {
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const panelRef = useRef(null);
  const launcherRef = useRef(null);

  const openPanel = useCallback(() => setIsPanelOpen(true), []);
  const minimizePanel = useCallback(() => {
    setIsPanelOpen(false);
    setShowHistory(false);
  }, []);

  const handleClose = useCallback(() => {
    setIsPanelOpen(false);
    setShowHistory(false);
  }, []);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === "Escape" && isPanelOpen) minimizePanel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isPanelOpen, minimizePanel]);

  const onBackdropClick = (e) => {
    if (panelRef.current?.contains(e.target)) return;
    if (launcherRef.current?.contains(e.target)) return;
    minimizePanel();
  };

  return (
    <>
      <AnimatePresence>
        {!isPanelOpen && (
          <motion.button
            ref={launcherRef}
            type="button"
            onClick={openPanel}
            className="launcher-fab fixed bottom-5 right-5 z-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 sm:bottom-6 sm:right-6"
            aria-label="Open MACE AI Assistant"
            aria-expanded={false}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.6 }}
            transition={{ duration: 0.2 }}
            {...LAUNCHER_MOTION}
          >
            <BotAvatar size="launcher" />
            {messages.some((m) => m.role === "user") && (
              <span
                className="absolute right-0 top-0 flex h-4 w-4 items-center justify-center rounded-full border-2 border-surface bg-accent text-[10px] font-bold text-white"
                aria-hidden
              >
                •
              </span>
            )}
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isPanelOpen && (
          <>
            <motion.button
              type="button"
              aria-label="Close chat overlay"
              className="fixed inset-0 z-40 bg-ink/10 backdrop-blur-[1px]"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={onBackdropClick}
            />

            <motion.div
              ref={panelRef}
              role="dialog"
              aria-label="MACE AI Assistant chat"
              aria-modal="true"
              className="fixed z-50 flex flex-col inset-x-3 bottom-[5.25rem] top-auto h-[min(78vh,620px)] sm:inset-x-auto sm:bottom-24 sm:right-6 sm:left-auto sm:h-[min(72vh,600px)] sm:w-[min(100vw-2rem,400px)]"
              {...PANEL_MOTION}
            >
              <div className="widget-shell flex h-full flex-col">
                <header className="flex shrink-0 items-center gap-2.5 border-b border-surface-border bg-surface px-3 py-3 sm:px-4">
                  <BotAvatar size="header" />
                  <div className="min-w-0 flex-1">
                    <h1 className="truncate text-sm font-bold text-ink">MACE AI Assistant</h1>
                    <p className="flex items-center gap-1.5 text-[11px] text-ink-muted">
                      <span
                        className="inline-block h-2 w-2 shrink-0 rounded-full bg-emerald-500"
                        aria-hidden
                      />
                      <span>Online</span>
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      onClick={onDemo}
                      className="btn-icon text-accent"
                      title="Book a free demo"
                      aria-label="Book a free demo"
                    >
                      <CalendarDays size={18} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowHistory((v) => !v)}
                      className="btn-icon"
                      title="Chat history"
                      aria-label="Chat history"
                    >
                      <History size={18} />
                    </button>
                    <button
                      type="button"
                      onClick={minimizePanel}
                      className="btn-icon"
                      title="Minimize"
                      aria-label="Minimize chat"
                    >
                      <Minus size={18} />
                    </button>
                    <button
                      type="button"
                      onClick={handleClose}
                      className="btn-icon btn-icon-danger"
                      title="Close"
                      aria-label="Close chat"
                    >
                      <X size={18} />
                    </button>
                  </div>
                </header>

                {error && (
                  <div className="shrink-0 flex items-center justify-center gap-2 border-b border-red-200 bg-red-50 px-3 py-2 text-center text-xs text-red-700">
                    <span className="flex-1">{error}</span>
                    {onRetryBackend && (
                      <button
                        type="button"
                        onClick={onRetryBackend}
                        className="shrink-0 rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                      >
                        Retry
                      </button>
                    )}
                  </div>
                )}

                <div className="relative flex min-h-0 flex-1 flex-col bg-surface-muted">
                  {showHistory && (
                    <Sidebar
                      drawer
                      conversations={conversations}
                      activeId={activeId}
                      onSelect={onSelectConversation}
                      onNewChat={onNewChat}
                      onDelete={onDeleteConversation}
                      onLead={onLead}
                      onDemo={onDemo}
                      onCloseDrawer={() => setShowHistory(false)}
                    />
                  )}
                  <ChatWindow
                    messages={messages}
                    loading={loading}
                    onSend={onSend}
                    onDemo={onDemo}
                    widget
                  />
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {showLead && <LeadForm onClose={onCloseLead} />}
      {showDemo && (
        <DemoBookForm
          onClose={onCloseDemo}
          conversationId={activeId}
          onEnsureConversation={onEnsureConversation}
          onBooked={onDemoBooked}
        />
      )}
    </>
  );
}
