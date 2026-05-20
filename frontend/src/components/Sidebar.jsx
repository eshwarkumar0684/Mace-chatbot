import {
  MessageSquarePlus,
  Trash2,
  PanelLeftClose,
  PanelLeft,
  Phone,
} from "lucide-react";

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onLead,
  collapsed,
  onToggleCollapse,
}) {
  return (
    <aside
      className={`flex h-full flex-col border-r border-surface-border bg-surface-elevated transition-all ${
        collapsed ? "w-14" : "w-72"
      }`}
    >
      <div className="flex items-center gap-2 border-b border-surface-border p-3">
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-gray-100">MACE AI Academy</p>
            <p className="truncate text-xs text-gray-400">Course Counselor</p>
          </div>
        )}
        <button
          type="button"
          onClick={onToggleCollapse}
          className="rounded p-2 text-gray-400 hover:bg-gray-800 hover:text-white"
          title="Toggle sidebar"
        >
          {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <div className="space-y-1 p-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-surface-border px-3 py-2 text-sm text-gray-200 hover:bg-gray-800"
        >
          <MessageSquarePlus size={16} />
          {!collapsed && "New chat"}
        </button>
        <button
          type="button"
          onClick={onLead}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-300 hover:bg-gray-800"
        >
          <Phone size={16} />
          {!collapsed && "Request callback"}
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
          <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            History
          </p>
          {conversations.length === 0 && (
            <p className="px-2 text-xs text-gray-500">No conversations yet</p>
          )}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`group mb-1 flex items-center gap-1 rounded-lg ${
                activeId === conv.id ? "bg-gray-800" : "hover:bg-gray-800/60"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(conv.id)}
                className="flex-1 truncate px-3 py-2 text-left text-sm text-gray-200"
              >
                {conv.title}
              </button>
              <button
                type="button"
                onClick={() => onDelete(conv.id)}
                className="mr-1 hidden rounded p-1 text-gray-500 group-hover:block hover:text-red-400"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
