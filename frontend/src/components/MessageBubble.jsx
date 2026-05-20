import { User, Bot } from "lucide-react";
import MessageContent from "./MessageContent";
import { parseMessageTime } from "../utils/formatTime";

export default function MessageBubble({ message, isTyping }) {
  const isUser = message.role === "user";
  const time = parseMessageTime(message.timestamp);

  return (
    <div
      className={`flex gap-3 px-4 py-5 ${isUser ? "bg-transparent" : "bg-surface-elevated/40"}`}
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${
          isUser ? "bg-accent text-white" : "bg-gray-700 text-gray-200"
        }`}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-gray-300">
            {isUser ? "You" : "MACE Assistant"}
          </p>
          <span className="shrink-0 text-[11px] text-gray-500">{time}</span>
        </div>
        {isUser ? (
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-100">
            {message.content}
          </p>
        ) : (
          <div className="text-[15px] leading-relaxed text-gray-100">
            <MessageContent content={message.content} isTyping={isTyping} />
          </div>
        )}
        {!isUser && !isTyping && message.sources?.length > 0 && (
          <details className="mt-2 text-xs text-gray-400">
            <summary className="cursor-pointer hover:text-accent">
              Sources ({message.sources.length})
            </summary>
            <ul className="mt-2 space-y-1 pl-2">
              {message.sources.map((src, i) => (
                <li key={i} className="border-l-2 border-accent/40 pl-2">
                  <span className="font-medium text-gray-300">{src.source}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
