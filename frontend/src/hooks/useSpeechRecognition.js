import { useCallback, useEffect, useRef, useState } from "react";

const SUPPORTED =
  typeof window !== "undefined" &&
  !!(window.SpeechRecognition || window.webkitSpeechRecognition);

function speechErrorMessage(code) {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access denied. Allow mic permission for this site in browser settings.";
    case "no-speech":
      return "No speech detected. Try again and speak clearly.";
    case "audio-capture":
      return "No microphone found. Connect a mic and retry.";
    case "network":
      return "Voice recognition needs an internet connection (browser speech service).";
    case "aborted":
      return "";
    default:
      return code ? `Voice input error: ${code}` : "Voice input failed. Try again.";
  }
}

export function useSpeechRecognition({ onTranscript, lang = "en-US" } = {}) {
  const recognitionRef = useRef(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const onTranscriptRef = useRef(onTranscript);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    if (!SUPPORTED) return undefined;

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = lang;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setListening(true);
      setError("");
    };

    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const part = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += part;
        else interimText += part;
      }
      const text = (finalText || interimText).trim();
      if (text) onTranscriptRef.current?.(text, !!finalText);
      if (finalText) setListening(false);
    };

    recognition.onerror = (event) => {
      setListening(false);
      const msg = speechErrorMessage(event.error);
      if (msg) setError(msg);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      try {
        recognition.abort();
      } catch {
        /* ignore */
      }
      recognitionRef.current = null;
    };
  }, [lang]);

  const toggle = useCallback(() => {
    if (!SUPPORTED) {
      setError(
        "Voice input is not supported in this browser. Use Chrome or Edge on desktop."
      );
      return;
    }
    const recognition = recognitionRef.current;
    if (!recognition) return;

    if (listening) {
      try {
        recognition.stop();
      } catch {
        recognition.abort();
      }
      setListening(false);
      return;
    }

    setError("");
    try {
      recognition.start();
    } catch {
      try {
        recognition.abort();
        recognition.start();
      } catch {
        setError("Could not start voice input. Wait a moment and try again.");
        setListening(false);
      }
    }
  }, [listening]);

  const clearError = useCallback(() => setError(""), []);

  return {
    supported: SUPPORTED,
    listening,
    error,
    toggle,
    clearError,
  };
}
