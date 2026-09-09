import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { api, type ApplicationDraft } from "../api/client";

const STATUSES = [
  { value: "", label: "All" },
  { value: "pending_review", label: "Pending review" },
  { value: "approved", label: "Approved" },
  { value: "skipped", label: "Skipped" },
  { value: "opened", label: "Opened" },
  { value: "applied", label: "Applied" },
];

export function ApplyQueuePage() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["apply-queue", status],
    queryFn: () => api.listApplyQueue(status || undefined),
  });

  const update = useMutation({
    mutationFn: ({ id, next }: { id: number; next: string }) =>
      api.updateQueueItem(id, next),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["apply-queue"] }),
  });

  const openApply = useMutation({
    mutationFn: (queueId: number) => api.openApply(queueId),
    onSuccess: (pack) => {
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
      if (pack.clipboard_pack) {
        void navigator.clipboard.writeText(pack.clipboard_pack);
        setCopiedId(pack.queue_id ?? pack.id);
      }
      if (pack.url) {
        window.open(pack.url, "_blank", "noopener,noreferrer");
      }
    },
  });

  const [assistMsg, setAssistMsg] = useState<string | null>(null);
  const browserAssist = useMutation({
    mutationFn: (queueId: number) => api.startBrowserAssist(queueId),
    onSuccess: (st) => {
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
      setAssistMsg(
        `${st.message} (filled: ${st.filled.join(", ") || "none"}; review in the browser window and Submit yourself)`
      );
    },
    onError: (err) => {
      setAssistMsg((err as Error).message);
    },
  });

  const copyPack = async (item: ApplicationDraft) => {
    const text =
      item.clipboard_pack ||
      [
        item.cover_letter,
        ...(item.tailored_bullets || []).map((b) => `• ${b}`),
        ...Object.entries(item.form_answers || {}).map(
          ([k, v]) => `${k.replaceAll("_", " ")}: ${v}`
        ),
      ]
        .filter(Boolean)
        .join("\n\n");
    await navigator.clipboard.writeText(text);
    setCopiedId(item.queue_id ?? item.id);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Apply Queue</h2>
        <p className="text-slate-500">
          AI drafts awaiting your review. Copy the apply pack, open the official
          link, paste answers yourself — nothing is submitted automatically.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <button
            key={s.value || "all"}
            type="button"
            onClick={() => setStatus(s.value)}
            className={`rounded-full px-3 py-1 text-sm ${
              status === s.value
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {assistMsg && (
        <div className="rounded-lg bg-teal-50 px-4 py-3 text-sm text-teal-900 whitespace-pre-wrap">
          {assistMsg}
        </div>
      )}

      {isLoading && <p className="text-slate-500">Loading queue…</p>}
      {error && (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      )}

      {!isLoading && (data?.length ?? 0) === 0 && (
        <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-slate-500">
          No drafts yet. From Results, click <strong>Analyze top N with AI</strong>{" "}
          or open a job and click <strong>Analyze with AI</strong>.
        </p>
      )}

      <div className="space-y-4">
        {data?.map((item) => (
          <article
            key={item.id}
            className="rounded-xl border border-slate-200 bg-white p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold text-slate-900">{item.title}</h3>
                <p className="text-sm text-slate-500">
                  {item.company} · {item.location || "—"} · {item.source}
                </p>
              </div>
              <div className="text-right text-sm">
                <div className="font-medium">Fit {item.fit_score.toFixed(0)}</div>
                <div className="capitalize text-slate-500">{item.decision}</div>
                <div className="text-xs text-slate-400">{item.queue_status}</div>
              </div>
            </div>

            {item.reasons?.length > 0 && (
              <p className="mt-2 text-sm text-slate-600">
                {item.reasons.slice(0, 2).join(" · ")}
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                to={`/results/${item.search_run_id}/jobs/${item.job_id}`}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs hover:bg-slate-50"
              >
                View details
              </Link>
              <button
                type="button"
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs hover:bg-slate-50"
                onClick={() =>
                  setExpanded(expanded === item.id ? null : item.id)
                }
              >
                {expanded === item.id ? "Hide pack" : "Show pack"}
              </button>
              <button
                type="button"
                className="rounded-lg border border-indigo-200 px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50"
                onClick={() => void copyPack(item)}
              >
                {copiedId === (item.queue_id ?? item.id)
                  ? "Copied!"
                  : "Copy apply pack"}
              </button>
              {item.queue_id && (
                <>
                  <button
                    type="button"
                    className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white hover:bg-emerald-700"
                    onClick={() =>
                      update.mutate({ id: item.queue_id!, next: "approved" })
                    }
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
                    onClick={() =>
                      update.mutate({ id: item.queue_id!, next: "skipped" })
                    }
                  >
                    Skip
                  </button>
                  <button
                    type="button"
                    disabled={openApply.isPending}
                    className="rounded-lg border border-indigo-200 px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                    onClick={() => openApply.mutate(item.queue_id!)}
                  >
                    Open apply + copy
                  </button>
                  <button
                    type="button"
                    disabled={browserAssist.isPending}
                    className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs text-teal-800 hover:bg-teal-100 disabled:opacity-50"
                    onClick={() => browserAssist.mutate(item.queue_id!)}
                    title="Opens a local Chromium window, prefills fields, never clicks Submit"
                  >
                    {browserAssist.isPending ? "Launching browser…" : "Browser fill (you submit)"}
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
                    onClick={() =>
                      update.mutate({ id: item.queue_id!, next: "applied" })
                    }
                  >
                    Mark applied
                  </button>
                </>
              )}
            </div>

            {expanded === item.id && (
              <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
                {item.clipboard_pack ||
                  item.cover_letter ||
                  "No pack content yet."}
              </pre>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
