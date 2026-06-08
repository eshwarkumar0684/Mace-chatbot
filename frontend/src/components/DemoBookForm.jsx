import { useCallback, useEffect, useState } from "react";
import { Calendar, Loader2, RefreshCw, X } from "lucide-react";
import { api } from "../api/client";
import BotAvatar from "./BotAvatar";

const COURSES = [
  "AI & ML with Generative AI",
  "Data Science with Generative AI",
  "Data Analytics with Generative AI",
  "General inquiry",
];

export default function DemoBookForm({ onClose, conversationId, onEnsureConversation, onBooked }) {
  const [convId, setConvId] = useState(conversationId);
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    course_interest: COURSES[0],
    demo_date: "",
  });
  const [dates, setDates] = useState([]);
  const [loadingDates, setLoadingDates] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState(null);

  const ensureConv = useCallback(async () => {
    if (convId) return convId;
    if (conversationId) {
      setConvId(conversationId);
      return conversationId;
    }
    if (onEnsureConversation) {
      const id = await onEnsureConversation();
      setConvId(id);
      return id;
    }
    return null;
  }, [convId, conversationId, onEnsureConversation]);

  const loadDates = useCallback(async (preferred) => {
    setLoadingDates(true);
    try {
      const data = await api.getDemoDates();
      const list = data.dates || [];
      setDates(list);
      setForm((prev) => {
        const pick =
          (preferred && list.some((d) => d.value === preferred) && preferred) ||
          (prev.demo_date && list.some((d) => d.value === prev.demo_date) && prev.demo_date) ||
          list[0]?.value ||
          "";
        return { ...prev, demo_date: pick };
      });
      return list;
    } catch (err) {
      setStatus({ type: "error", text: err.message || "Could not load available dates." });
      return [];
    } finally {
      setLoadingDates(false);
    }
  }, []);

  useEffect(() => {
    loadDates();
  }, [loadDates]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setStatus(null);
    try {
      const id = await ensureConv();
      if (!id) throw new Error("Start a chat first, then book your demo.");

      const result = await api.bookDemo({
        conversation_id: id,
        name: form.name,
        email: form.email,
        phone: form.phone,
        course_interest: form.course_interest,
        demo_date: form.demo_date,
      });

      if (result.email_delivery?.pending) {
        setStatus({
          type: "success",
          text: `${result.message}\n\nBooking confirmed. Confirmation email could not be sent — use Retry or contact support.`,
        });
      } else {
        setStatus({ type: "success", text: result.message });
      }
      onBooked?.(result.message, id, result);
    } catch (err) {
      if (err.code === "duplicate_booking" && err.alternatives?.length) {
        const options = err.alternatives.map((value) => {
          const existing = dates.find((d) => d.value === value);
          return existing || { value, label: value };
        });
        setDates(options.length ? options : dates);
        setForm((prev) => ({ ...prev, demo_date: options[0]?.value || prev.demo_date }));
        setStatus({
          type: "error",
          text: err.message || "You already have a demo on this date. Please pick another date.",
        });
      } else {
        setStatus({
          type: "error",
          text: err.message || "Booking failed. Please try another date.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/20 p-4 backdrop-blur-sm">
      <div className="widget-shell max-h-[90vh] w-full max-w-lg overflow-y-auto p-6 md:p-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <BotAvatar size="header" />
            <div>
              <h2 className="text-lg font-semibold text-ink">Book a free demo</h2>
              <p className="text-xs text-ink-muted">Live session with a MACE counselor</p>
            </div>
          </div>
          <button type="button" onClick={onClose} className="btn-icon" aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
          <input
            name="name"
            placeholder="Full name"
            value={form.name}
            onChange={handleChange}
            required
            className="field-input"
          />
          <input
            name="email"
            type="email"
            placeholder="Email"
            value={form.email}
            onChange={handleChange}
            required
            className="field-input"
          />
          <input
            name="phone"
            placeholder="Phone"
            value={form.phone}
            onChange={handleChange}
            required
            className="field-input sm:col-span-2"
          />
          <select
            name="course_interest"
            value={form.course_interest}
            onChange={handleChange}
            className="field-input sm:col-span-2"
          >
            {COURSES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <div className="sm:col-span-2">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="flex items-center gap-1.5 text-xs font-medium text-ink-muted">
                <Calendar size={14} />
                Select a date
              </label>
              <button
                type="button"
                onClick={() => loadDates(form.demo_date)}
                disabled={loadingDates}
                className="flex items-center gap-1 text-xs text-accent hover:underline disabled:opacity-50"
              >
                <RefreshCw size={12} className={loadingDates ? "animate-spin" : ""} />
                Refresh dates
              </button>
            </div>
            {loadingDates ? (
              <div className="flex items-center gap-2 rounded-xl border border-surface-border bg-surface-muted px-4 py-3 text-sm text-ink-muted">
                <Loader2 size={16} className="animate-spin" />
                Loading available dates…
              </div>
            ) : dates.length === 0 ? (
              <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                No dates available right now. Tap refresh or try again tomorrow.
              </p>
            ) : (
              <select
                name="demo_date"
                value={form.demo_date}
                onChange={handleChange}
                required
                className="field-input"
              >
                {dates.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            )}
          </div>

          {status && (
            <p
              className={`whitespace-pre-wrap text-sm sm:col-span-2 ${
                status.type === "success"
                  ? "rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-800"
                  : status.type === "info"
                    ? "rounded-lg border border-accent/20 bg-accent-light p-3 text-accent"
                    : "rounded-lg border border-red-200 bg-red-50 p-3 text-red-700"
              }`}
            >
              {status.text}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting || loadingDates || !dates.length}
            className="btn-primary py-3 sm:col-span-2"
          >
            {submitting ? "Booking…" : "Confirm demo booking"}
          </button>
        </form>
      </div>
    </div>
  );
}
