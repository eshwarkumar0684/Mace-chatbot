import { User } from "lucide-react";
import BotAvatar from "./BotAvatar";
import MessageContent from "./MessageContent";
import { parseMessageTime } from "../utils/formatTime";

export default function MessageBubble({ message, isTyping, widget = false }) {
  const isUser = message.role === "user";
  const time = parseMessageTime(message.timestamp);

  if (widget) {
    return (
      <div
        className={`animate-message-in flex px-3 py-2 ${isUser ? "justify-end" : "justify-start gap-2"}`}
      >
        {!isUser && <BotAvatar size="sm" className="mt-0.5" />}
        <div className={`max-w-[88%] space-y-1 ${isUser ? "items-end" : ""}`}>
          <div className={isUser ? "bubble-user" : "bubble-bot"}>
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <MessageContent content={message.content} isTyping={isTyping} />
            )}
          </div>
          <span className="block px-1 text-[10px] text-ink-muted">{time}</span>
          {!isUser && !isTyping && message.sources?.length > 0 && (
            <details className="px-1 text-[11px] text-ink-muted">
              <summary className="cursor-pointer text-accent hover:text-accent-hover">
                Sources ({message.sources.length})
              </summary>
              <ul className="mt-1 space-y-1 pl-2">
                {message.sources.map((src, i) => (
                  <li key={i} className="border-l-2 border-accent/40 pl-2">
                    {src.source}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-message-in flex gap-3 px-2 py-4 md:gap-4 md:px-4 md:py-5">
      {isUser ? (
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-white shadow-input">
          <User size={18} />
        </div>
      ) : (
        <BotAvatar size="md" />
      )}
      <div
        className={`min-w-0 flex-1 space-y-2 rounded-2xl border px-4 py-3.5 md:px-5 md:py-4 ${
          isUser
            ? "border-transparent bg-transparent"
            : "border-surface-border bg-surface-muted shadow-input"
        }`}
      >
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-sm font-semibold text-ink">{isUser ? "You" : "MACE Assistant"}</p>
          <span className="shrink-0 text-[11px] text-ink-muted">{time}</span>
        </div>
        {isUser ? (
          <div className="bubble-user inline-block">
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        ) : (
          <div className="text-[15px] leading-relaxed text-ink">
            <MessageContent content={message.content} isTyping={isTyping} />
          </div>
        )}
        {!isUser && !isTyping && message.sources?.length > 0 && (
          <details className="mt-1 text-xs text-ink-muted">
            <summary className="cursor-pointer text-accent hover:text-accent-hover">
              Sources ({message.sources.length})
            </summary>
            <ul className="mt-2 space-y-1.5 pl-2">
              {message.sources.map((src, i) => (
                <li key={i} className="border-l-2 border-accent/40 pl-2 text-ink-muted">
                  {src.source}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
