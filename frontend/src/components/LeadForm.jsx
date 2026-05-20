import { useState } from "react";
import { X } from "lucide-react";
import { api } from "../api/client";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg rounded-xl border border-surface-border bg-surface-elevated p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">Request a callback</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2">
          <input
            name="name"
            placeholder="Name"
            value={form.name}
            onChange={handleChange}
            required
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 outline-none focus:border-accent"
          />
          <input
            name="email"
            type="email"
            placeholder="Email"
            value={form.email}
            onChange={handleChange}
            required
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 outline-none focus:border-accent"
          />
          <input
            name="phone"
            placeholder="Phone"
            value={form.phone}
            onChange={handleChange}
            required
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 sm:col-span-2 outline-none focus:border-accent"
          />
          <select
            name="course_interest"
            value={form.course_interest}
            onChange={handleChange}
            className="rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-gray-100 sm:col-span-2 outline-none focus:border-accent"
          >
            <option>AI & ML with Generative AI</option>
            <option>Data Science with Generative AI</option>
            <option>Data Analytics with Generative AI</option>
            <option>General inquiry</option>
          </select>
          {status && (
            <p
              className={`text-sm sm:col-span-2 ${status.type === "success" ? "text-green-400" : "text-red-400"}`}
            >
              {status.text}
            </p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60 sm:col-span-2"
          >
            {loading ? "Submitting..." : "Submit"}
          </button>
        </form>
      </div>
    </div>
  );
}
