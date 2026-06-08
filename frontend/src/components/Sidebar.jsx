import { useMemo, useState } from "react";
import {
  MessageSquarePlus,
  Trash2,
  Phone,
  CalendarDays,
  Search,
  X,
  ArrowLeft,
} from "lucide-react";

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onLead,
  onDemo,
  drawer = false,
  onCloseDrawer,
}) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title?.toLowerCase().includes(q));
  }, [conversations, search]);

  if (!drawer) return null;

  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-surface">
      <div className="flex items-center justify-between border-b border-surface-border bg-surface px-4 py-3">
        <button type="button" onClick={onCloseDrawer} className="btn-icon" aria-label="Back to chat">
          <ArrowLeft size={18} />
        </button>
        <p className="text-sm font-semibold text-ink">Chat history</p>
        <button type="button" onClick={onCloseDrawer} className="btn-icon" aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="space-y-2 border-b border-surface-border bg-surface-muted p-3">
        <button
          type="button"
          onClick={() => {
            onNewChat();
            onCloseDrawer?.();
          }}
          className="btn-primary w-full py-2.5"
        >
          <MessageSquarePlus size={18} />
          New chat
        </button>
        <button
          type="button"
          onClick={() => {
            onDemo?.();
            onCloseDrawer?.();
          }}
          className="btn-primary w-full"
        >
          <CalendarDays size={18} />
          Book free demo
        </button>
        <button
          type="button"
          onClick={() => {
            onLead();
            onCloseDrawer?.();
          }}
          className="btn-secondary w-full"
        >
          <Phone size={16} />
          Request callback
        </button>
      </div>

      <div className="px-3 py-2">
        <div className="flex items-center gap-2 rounded-xl border border-surface-border bg-surface px-3 py-2 shadow-input">
          <Search size={16} className="shrink-0 text-ink-muted" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search chats..."
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-2 pb-4">
        <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
          History
        </p>
        {filtered.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-ink-muted">
            {search ? "No matching chats" : "No conversations yet"}
          </p>
        )}
        {filtered.map((conv) => {
          const isActive = activeId === conv.id;
          return (
            <div
              key={conv.id}
              className={`group mb-1 flex items-center gap-0.5 rounded-xl transition duration-200 ${
                isActive
                  ? "bg-accent-light ring-1 ring-accent/30"
                  : "hover:bg-accent-light/60"
              }`}
            >
              <button
                type="button"
                onClick={() => {
                  onSelect(conv.id);
                  onCloseDrawer?.();
                }}
                className={`flex-1 truncate px-3 py-2.5 text-left text-sm ${
                  isActive ? "font-semibold text-accent" : "text-ink"
                }`}
              >
                {conv.title}
              </button>
              <button
                type="button"
                onClick={() => onDelete(conv.id)}
                className="mr-1 rounded-lg p-1.5 text-ink-muted opacity-0 transition group-hover:opacity-100 hover:bg-red-50 hover:text-red-600"
                aria-label="Delete chat"
              >
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
