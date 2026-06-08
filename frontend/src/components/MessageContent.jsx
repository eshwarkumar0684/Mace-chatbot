import {
  Brain,
  BarChart3,
  Sparkles,
  Cloud,
  Lightbulb,
  Check,
  GraduationCap,
} from "lucide-react";

const ICON_RULES = [
  { pattern: /artificial intelligence|\bai\b|machine learning|\bml\b/i, Icon: Brain },
  { pattern: /data science|analytics/i, Icon: BarChart3 },
  { pattern: /generative|gen ai|llm|prompt/i, Icon: Sparkles },
  { pattern: /devops|cloud|aws|azure/i, Icon: Cloud },
  { pattern: /placement|career|tip|recommend/i, Icon: Lightbulb },
  { pattern: /course|academy|mace/i, Icon: GraduationCap },
];

function pickIcon(text) {
  for (const { pattern, Icon } of ICON_RULES) {
    if (pattern.test(text)) return Icon;
  }
  return null;
}

function renderInline(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-accent">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function isNumberedHeader(line) {
  return /^\d+\.\s+/.test(line.trim());
}

function isBullet(line) {
  const t = line.trim();
  return /^[-•*✓✔]\s+/.test(t) || /^[✓✔]\s/.test(t);
}

function isCheckLine(line) {
  const t = line.trim();
  return t.startsWith("✓") || t.startsWith("✔");
}

export default function MessageContent({ content, isTyping }) {
  if (!content && isTyping) {
    return <span className="typing-cursor text-ink-muted"> </span>;
  }

  const lines = content.split("\n");
  const elements = [];

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (!trimmed) {
      elements.push(<br key={`br-${idx}`} />);
      return;
    }

    if (isNumberedHeader(trimmed)) {
      const text = trimmed.replace(/^\d+\.\s+/, "");
      const Icon = pickIcon(text);
      elements.push(
        <p key={idx} className="section-title flex items-center gap-2 text-[15px]">
          {Icon && (
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-muted text-accent">
              <Icon size={15} />
            </span>
          )}
          <span>{renderInline(text)}</span>
        </p>
      );
      return;
    }

    if (isCheckLine(trimmed)) {
      const text = trimmed.replace(/^[-•*✓✔]\s*/, "");
      elements.push(
        <div key={idx} className="check-item text-[15px] text-ink">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent/20 text-accent">
            <Check size={12} strokeWidth={3} />
          </span>
          <span>{renderInline(text)}</span>
        </div>
      );
      return;
    }

    if (isBullet(trimmed)) {
      const text = trimmed.replace(/^[-•*]\s+/, "");
      const Icon = pickIcon(text);
      elements.push(
        <div key={idx} className="course-item text-[15px] text-ink">
          {Icon ? (
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-muted text-accent">
              <Icon size={13} />
            </span>
          ) : (
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
          )}
          <span>{renderInline(text)}</span>
        </div>
      );
      return;
    }

    elements.push(
      <p key={idx} className="text-[15px] leading-relaxed text-ink">
        {renderInline(trimmed)}
        {idx === lines.length - 1 && isTyping && <span className="typing-cursor" />}
      </p>
    );
  });

  return <div className="bot-message-content space-y-1">{elements}</div>;
}
