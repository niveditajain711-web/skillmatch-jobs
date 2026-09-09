import { useState } from "react";

export const NOT_APPLIED_REASONS = [
  { value: "no_link", label: "Missing / broken apply link" },
  { value: "job_closed", label: "Job closed or filled" },
  { value: "not_eligible", label: "Not eligible (YOE, location, visa…)" },
  { value: "login_wall", label: "Login / SSO / captcha blocked" },
  { value: "form_blocked", label: "ATS form error / can’t submit" },
  { value: "duplicate", label: "Already applied elsewhere" },
  { value: "other", label: "Other (note required)" },
] as const;

export type NotAppliedReason = (typeof NOT_APPLIED_REASONS)[number]["value"];

export function NotAppliedModal({
  open,
  title,
  pending,
  error,
  onClose,
  onConfirm,
}: {
  open: boolean;
  title?: string | null;
  pending?: boolean;
  error?: string | null;
  onClose: () => void;
  onConfirm: (reason: NotAppliedReason, notes: string) => void;
}) {
  const [reason, setReason] = useState<NotAppliedReason | "">("");
  const [notes, setNotes] = useState("");

  if (!open) return null;

  const canSubmit =
    !!reason && (reason !== "other" || notes.trim().length > 0) && !pending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="not-applied-title"
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-lg"
      >
        <h3 id="not-applied-title" className="text-lg font-semibold text-slate-900">
          Couldn’t apply
        </h3>
        {title && <p className="mt-1 text-sm text-slate-500">{title}</p>}
        <p className="mt-2 text-sm text-slate-600">
          Skip means you don’t want the role. This logs that you wanted to apply
          but couldn’t — used to improve future analysis.
        </p>

        <label className="mt-4 block text-sm font-medium text-slate-700">
          Reason
          <select
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value as NotAppliedReason | "")}
          >
            <option value="">Select a reason…</option>
            {NOT_APPLIED_REASONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>

        <label className="mt-3 block text-sm font-medium text-slate-700">
          Notes {reason === "other" ? "(required)" : "(optional)"}
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. link 404, role requires 8+ YOE…"
          />
        </label>

        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            onClick={onClose}
            disabled={pending}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-900 disabled:opacity-50"
            onClick={() => {
              if (!reason) return;
              onConfirm(reason, notes.trim());
            }}
          >
            {pending ? "Saving…" : "Mark not applied"}
          </button>
        </div>
      </div>
    </div>
  );
}
