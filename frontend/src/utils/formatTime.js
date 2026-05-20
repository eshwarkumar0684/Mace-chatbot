export function formatMessageTime(date = new Date()) {
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function parseMessageTime(timestamp) {
  if (!timestamp) return formatMessageTime();
  const d = new Date(timestamp);
  return Number.isNaN(d.getTime()) ? formatMessageTime() : formatMessageTime(d);
}
