import { useEffect, useRef, useState } from "react";
import {
  Mic,
  MicOff,
  Send,
  Paperclip,
  GraduationCap,
  Wallet,
  Briefcase,
  Clock,
  Loader2,
  CalendarDays,
} from "lucide-react";
import { api } from "../api/client";
import BotAvatar from "./BotAvatar";
import MessageBubble from "./MessageBubble";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useTypingEffect } from "../hooks/useTypingEffect";
import { getFollowUpSuggestions } from "../utils/conversation";

const DEMO_PROMPT = "I'd like to book a free demo session";

const SUGGESTIONS = [
  { text: DEMO_PROMPT, Icon: CalendarDays, demo: true, featured: true },
  { text: "What courses does MACE AI Academy offer?", Icon: GraduationCap },
  { text: "What are the fees and EMI options?", Icon: Wallet },
  { text: "Do you provide placement support?", Icon: Briefcase },
  { text: "What is the duration of the Data Science course?", Icon: Clock },
];

const ACCEPT_FILES = ".pdf,.txt,.docx,.csv";

function AssistantMessage({ message, animate, widget }) {
  const typed = useTypingEffect(message.content, 10, animate);
  return (
    <MessageBubble
      message={{ ...message, content: typed }}
      isTyping={animate && typed.length < message.content.length}
      widget={widget}
    />
  );
}

function FollowUpChips({ suggestions, onSelect, onDemo, disabled }) {
  if (!suggestions?.length) return null;
  return (
    <div className="flex flex-wrap gap-2 px-3 pb-2">
      {suggestions.map((text) => {
        const isDemo = /book.*demo|demo session/i.test(text);
        return (
          <button
            key={text}
            type="button"
            disabled={disabled}
            onClick={() => (isDemo && onDemo ? onDemo() : onSelect(text))}
            className={`rounded-full border px-3 py-1.5 text-xs transition duration-200 disabled:opacity-50 ${
              isDemo
                ? "border-accent bg-accent-light font-medium text-accent hover:bg-accent hover:text-white"
                : "border-surface-border bg-surface text-ink hover:border-accent/40 hover:bg-accent-light hover:text-accent"
            }`}
          >
            {text}
          </button>
        );
      })}
    </div>
  );
}

export default function ChatWindow({ messages, loading, onSend, onDemo, widget = false }) {
  const [input, setInput] = useState("");
  const [attachStatus, setAttachStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);
  const voiceBaseRef = useRef("");

  const { listening, error: voiceError, toggle: toggleVoice, clearError } =
    useSpeechRecognition({
      onTranscript: (text, isFinal) => {
        if (isFinal) {
          setInput((prev) => {
            const base = voiceBaseRef.current || prev;
            return base ? `${base} ${text}`.trim() : text;
          });
          voiceBaseRef.current = "";
        } else {
          setInput(() => {
            const base = voiceBaseRef.current;
            return base ? `${base} ${text}`.trim() : text;
          });
        }
      },
    });

  const hasUserMessages = messages.some((m) => m.role === "user");
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const lastBot = [...messages].reverse().find((m) => m.role === "assistant");
  const followUps =
    !loading && lastBot && hasUserMessages
      ? getFollowUpSuggestions(lastUser?.content, lastBot?.content)
      : [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, followUps, attachStatus, voiceError]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    voiceBaseRef.current = "";
    onSend(text);
  };

  const handleAttachClick = () => {
    if (uploading || loading) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (![".pdf", ".txt", ".docx", ".csv"].includes(ext)) {
      setAttachStatus({
        type: "error",
        text: "Unsupported file. Use PDF, TXT, DOCX, or CSV.",
      });
      return;
    }

    setUploading(true);
    setAttachStatus({ type: "info", text: `Uploading ${file.name}…` });

    try {
      const result = await api.uploadFile(file);
      setAttachStatus({
        type: "success",
        text: result?.message || `${file.name} uploaded and indexed.`,
      });
    } catch (err) {
      setAttachStatus({
        type: "error",
        text: err.message || "Upload failed.",
      });
    } finally {
      setUploading(false);
    }
  };

  const handleVoiceClick = () => {
    clearError();
    if (!listening) {
      voiceBaseRef.current = input.trim();
    }
    toggleVoice();
  };

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT_FILES}
        className="hidden"
        aria-hidden
        onChange={handleFileChange}
      />

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-6 text-center">
            <BotAvatar size="xl" className="mb-4" />
            <p className="mb-1 text-sm font-semibold text-ink">Hi! I&apos;m your AI assistant</p>
            <p className="mb-4 text-xs leading-relaxed text-ink-muted">
              Ask about MACE courses, fees, placements & more.
            </p>

            <button
              type="button"
              onClick={() => onDemo?.()}
              className="mb-4 flex w-full items-center gap-3 rounded-2xl border-2 border-accent/30 bg-gradient-to-r from-accent-light to-surface p-4 text-left shadow-card transition hover:border-accent hover:shadow-float"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent text-white">
                <CalendarDays size={22} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-bold text-ink">Book a free demo</span>
                <span className="block text-xs text-ink-muted">
                  Pick a date · Email confirmation
                </span>
              </span>
            </button>

            <div className="grid w-full gap-2">
              {SUGGESTIONS.filter((s) => !s.featured).map(({ text, Icon }) => (
                <button
                  key={text}
                  type="button"
                  onClick={() => onSend(text)}
                  className="ui-card flex w-full items-center gap-3 rounded-2xl p-3 text-left"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-light text-accent">
                    <Icon size={16} />
                  </span>
                  <span className="text-xs font-medium leading-snug text-ink">{text}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div>
            {messages.map((msg, i) => {
              const isLastAssistant =
                msg.role === "assistant" && i === messages.length - 1 && !loading;
              if (msg.role === "assistant" && msg.animate) {
                return (
                  <AssistantMessage
                    key={msg.id}
                    message={msg}
                    animate={isLastAssistant}
                    widget={widget}
                  />
                );
              }
              return <MessageBubble key={msg.id} message={msg} widget={widget} />;
            })}
            {loading && (
              <div className="flex gap-2 px-3 py-3">
                <BotAvatar size="sm" />
                <div className="bubble-bot flex items-center gap-2">
                  <span className="inline-flex gap-1">
                    <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent" />
                    <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent [animation-delay:150ms]" />
                    <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent [animation-delay:300ms]" />
                  </span>
                  <span className="text-sm text-ink-muted">Thinking...</span>
                </div>
              </div>
            )}
            <FollowUpChips
              suggestions={followUps}
              onSelect={onSend}
              onDemo={onDemo}
              disabled={loading}
            />
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t border-surface-border bg-surface p-3"
      >
        {onDemo && (
          <button
            type="button"
            onClick={onDemo}
            disabled={loading}
            className="mb-2 flex w-full items-center justify-center gap-2 rounded-xl border border-accent/25 bg-accent-light py-2 text-xs font-semibold text-accent transition hover:bg-accent hover:text-white disabled:opacity-50"
          >
            <CalendarDays size={16} />
            Book a free demo
          </button>
        )}

        {(attachStatus || voiceError) && (
          <div
            className={`mb-2 rounded-lg px-3 py-2 text-xs ${
              attachStatus?.type === "error" || voiceError
                ? "border border-red-200 bg-red-50 text-red-700"
                : attachStatus?.type === "success"
                  ? "border border-emerald-200 bg-emerald-50 text-emerald-800"
                  : "border border-surface-border bg-surface-muted text-ink-muted"
            }`}
            role="status"
          >
            {voiceError || attachStatus?.text}
          </div>
        )}

        <div className="widget-input-bar">
          <button
            type="button"
            onClick={handleAttachClick}
            disabled={uploading || loading}
            title="Attach PDF, TXT, DOCX, or CSV"
            className="btn-icon disabled:opacity-40"
            aria-label="Attach file"
          >
            {uploading ? (
              <Loader2 size={18} className="animate-spin text-accent" />
            ) : (
              <Paperclip size={18} />
            )}
          </button>
          <textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder={
              listening ? "Listening… speak now" : "Ask about MACE courses..."
            }
            className="max-h-24 min-h-[40px] flex-1 resize-none bg-transparent py-2 text-sm text-ink outline-none placeholder:text-ink-muted"
            aria-label="Message input"
          />
          <button
            type="button"
            onClick={handleVoiceClick}
            disabled={loading || uploading}
            className={`btn-icon ${listening ? "bg-red-50 text-red-600" : ""}`}
            title={listening ? "Stop listening" : "Voice input"}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            aria-pressed={listening}
          >
            {listening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
          <button
            type="submit"
            disabled={loading || uploading || !input.trim()}
            className="btn-primary shrink-0 rounded-xl px-3 py-2"
            title="Send message"
          >
            <Send size={18} />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-ink-muted">
          Attach course docs (PDF, TXT, DOCX, CSV) · Voice works in Chrome/Edge
        </p>
      </form>
    </div>
  );
}
