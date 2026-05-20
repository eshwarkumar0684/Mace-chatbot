import { formatMessageTime } from "./formatTime";

export const COUNSELOR_GREETING = {
  id: "welcome-greeting",
  role: "assistant",
  content: `Hi there! 👋 I'm your **MACE AI Academy** counselor.

I'm here to chat about our courses, fees, career paths, and anything else on your mind about learning AI and data science.

What would you like to explore today?`,
  timestamp: formatMessageTime(),
};

export function getFollowUpSuggestions(lastUserMessage = "", lastBotMessage = "") {
  const combined = `${lastUserMessage} ${lastBotMessage}`.toLowerCase();

  if (/generative|gen ai|llm|prompt/i.test(combined)) {
    return [
      "What are the fees for this course?",
      "How long is the program?",
      "Do you help with placements?",
    ];
  }
  if (/fee|emi|cost|price|payment/i.test(combined)) {
    return [
      "Can I pay in monthly installments?",
      "Is there a discount for lump-sum payment?",
      "Which course fits a beginner budget?",
    ];
  }
  if (/data science|analytics/i.test(combined)) {
    return [
      "How is it different from the AI & ML course?",
      "What projects will I build?",
      "Tell me about placement support",
    ];
  }
  if (/placement|career|job/i.test(combined)) {
    return [
      "What companies hire from MACE?",
      "Do I need prior coding experience?",
      "Show me all course options",
    ];
  }
  if (/course|offer|program/i.test(combined)) {
    return [
      "Tell me more about Generative AI",
      "What are the fees and EMI options?",
      "I'm a complete beginner — where should I start?",
    ];
  }

  return [
    "What courses do you offer?",
    "Compare fees across programs",
    "I'd like a callback from a counselor",
  ];
}
