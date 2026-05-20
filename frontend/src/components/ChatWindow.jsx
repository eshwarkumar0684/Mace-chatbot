import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Send, Sun, Moon } from "lucide-react";
import MessageBubble from "./MessageBubble";
import { useTypingEffect } from "../hooks/useTypingEffect";
import { getFollowUpSuggestions } from "../utils/conversation";

const SUGGESTIONS = [
  "What courses does MACE AI Academy offer?",
  "What are the fees and EMI options?",
  "Do you provide placement support?",
  "What is the duration of the Data Science course?",
];

function AssistantMessage({ message, animate }) {
  const typed = useTypingEffect(message.content, 10, animate);
  return (
    <MessageBubble
      message={{ ...message, content: typed }}
      isTyping={animate && typed.length < message.content.length}
    />
  );
}

function FollowUpChips({ suggestions, onSelect, disabled }) {
  if (!suggestions?.length) return null;
  return (
    <div className="flex flex-wrap gap-2 px-4 pb-3">
      {suggestions.map((text) => (
        <button
          key={text}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(text)}
          className="rounded-full border border-surface-border bg-surface-elevated px-3 py-1.5 text-xs text-gray-300 transition hover:border-accent/50 hover:text-accent disabled:opacity-50"
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export default function ChatWindow({ messages, loading, onSend, darkMode, onToggleDark }) {
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const bottomRef = useRef(null);
  const recognitionRef = useRef(null);

  const hasUserMessages = messages.some((m) => m.role === "user");
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const lastBot = [...messages].reverse().find((m) => m.role === "assistant");
  const followUps =
    !loading && lastBot && hasUserMessages
      ? getFollowUpSuggestions(lastUser?.content, lastBot?.content)
      : [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, followUps]);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
        setListening(false);
      };
      recognitionRef.current.onerror = () => setListening(false);
      recognitionRef.current.onend = () => setListening(false);
    }
  }, []);

  const toggleVoice = () => {
    if (!recognitionRef.current) {
      alert("Voice input is not supported in this browser.");
      return;
    }
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
    } else {
      setListening(true);
      recognitionRef.current.start();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    onSend(text);
  };

  return (
    <main className="flex h-full flex-1 flex-col bg-surface">
      <header className="flex items-center justify-between border-b border-surface-border px-4 py-3">
        <div>
          <h1 className="text-base font-semibold text-gray-100">Course Counselor</h1>
          <p className="text-xs text-gray-400">Powered by RAG + Groq Llama 3</p>
        </div>
        <button
          type="button"
          onClick={onToggleDark}
          className="rounded-lg p-2 text-gray-400 hover:bg-gray-800"
          title="Toggle theme"
        >
          {darkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center">
            <h2 className="mb-2 text-2xl font-semibold text-gray-100">
              Welcome to MACE AI Academy
            </h2>
            <p className="mb-8 max-w-md text-sm text-gray-400">
              Ask about courses, fees, syllabus, placements, and certifications.
            </p>
            <div className="grid w-full max-w-2xl gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSend(s)}
                  className="rounded-xl border border-surface-border bg-surface-elevated px-4 py-3 text-left text-sm text-gray-300 hover:border-accent/50 hover:bg-accent-muted/30"
                >
                  {s}
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
                return <AssistantMessage key={msg.id} message={msg} animate={isLastAssistant} />;
              }
              return <MessageBubble key={msg.id} message={msg} />;
            })}
            {loading && (
              <div className="px-4 py-5 text-sm text-gray-400">
                <span className="inline-flex gap-1">
                  <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent" />
                  <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent [animation-delay:150ms]" />
                  <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent [animation-delay:300ms]" />
                </span>
                <span className="ml-2">Thinking...</span>
              </div>
            )}
            <FollowUpChips suggestions={followUps} onSelect={onSend} disabled={loading} />
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <form className="border-t border-surface-border bg-surface-elevated/80 p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-surface-border bg-surface px-3 py-2 shadow-lg">
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
            placeholder="Ask about MACE courses..."
            className="max-h-32 min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm text-gray-100 outline-none placeholder:text-gray-500"
          />
          <button
            type="button"
            onClick={toggleVoice}
            className={`rounded-lg p-2 ${
              listening ? "bg-red-500/20 text-red-400" : "text-gray-400 hover:bg-gray-800"
            }`}
            title="Voice input"
          >
            {listening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-accent p-2 text-white hover:bg-accent-hover disabled:opacity-50"
          >
            <Send size={18} />
          </button>
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-gray-500">
          Answers are grounded in MACE Academy course documents.
        </p>
      </form>
    </main>
  );
}
