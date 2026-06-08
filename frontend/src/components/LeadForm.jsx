import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../api/client";
import BotAvatar from "./BotAvatar";

export default function LeadForm({ onClose }) {
  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    course_interest: "AI & ML with Generative AI",
  });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus(null);
    try {
      await api.submitLead(form);
      setStatus({ type: "success", text: "Thank you! Our counselor will contact you soon." });
    } catch (err) {
      setStatus({ type: "error", text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/20 p-4 backdrop-blur-sm">
      <div className="widget-shell w-full max-w-lg p-6 md:p-8">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <BotAvatar size="header" />
            <h2 className="text-lg font-semibold text-ink">Request a callback</h2>
          </div>
          <button type="button" onClick={onClose} className="btn-icon" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
          <input
            name="name"
            placeholder="Name"
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
            <option>AI & ML with Generative AI</option>
            <option>Data Science with Generative AI</option>
            <option>Data Analytics with Generative AI</option>
            <option>General inquiry</option>
          </select>
          {status && (
            <p
              className={`text-sm sm:col-span-2 ${
                status.type === "success" ? "text-emerald-600" : "text-red-600"
              }`}
            >
              {status.text}
            </p>
          )}
          <button type="submit" disabled={loading} className="btn-primary py-3 sm:col-span-2">
            {loading ? "Submitting..." : "Submit"}
          </button>
        </form>
      </div>
    </div>
  );
}
