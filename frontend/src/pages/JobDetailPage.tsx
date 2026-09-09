import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type ApplicationDraft } from "../api/client";
import { ScoreBadge } from "../components/ScoreBadge";

export function JobDetailPage() {
  const { runId, jobId } = useParams<{ runId: string; jobId: string }>();
  const rid = Number(runId);
  const jid = Number(jobId);
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["job", runId, jobId],
    queryFn: () => api.getRunJob(rid, jid),
    enabled: !!runId && !!jobId,
  });

  const { data: agentStatus } = useQuery({
    queryKey: ["agent-status"],
    queryFn: api.getAgentStatus,
  });

  const { data: draft } = useQuery({
    queryKey: ["draft", runId, jobId],
    queryFn: () => api.getJobDraft(rid, jid),
    enabled: !!runId && !!jobId,
    retry: false,
  });

  const analyze = useMutation({
    mutationFn: (force: boolean) => api.analyzeJob(rid, jid, force),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["draft", runId, jobId] });
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
    },
  });

  const updateQueue = useMutation({
    mutationFn: ({ status }: { status: string }) => {
      const queueId = (analyze.data ?? draft)?.queue_id;
      if (!queueId) throw new Error("No queue item");
      return api.updateQueueItem(queueId, status);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["draft", runId, jobId] });
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
    },
  });

  const openApply = useMutation({
    mutationFn: () => {
      const queueId = (analyze.data ?? draft)?.queue_id;
      if (!queueId) throw new Error("No queue item");
      return api.openApply(queueId);
    },
    onSuccess: (pack) => {
      qc.invalidateQueries({ queryKey: ["draft", runId, jobId] });
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
      if (pack.clipboard_pack) {
        void navigator.clipboard.writeText(pack.clipboard_pack);
      }
      if (pack.url) {
        window.open(pack.url, "_blank", "noopener,noreferrer");
      }
    },
  });

  const browserAssist = useMutation({
    mutationFn: () => {
      const queueId = (analyze.data ?? draft)?.queue_id;
      if (!queueId) throw new Error("No queue item");
      return api.startBrowserAssist(queueId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["draft", runId, jobId] });
      qc.invalidateQueries({ queryKey: ["apply-queue"] });
    },
  });

  if (isLoading) return <p className="text-slate-500">Loading…</p>;
  if (error || !data) return <p className="text-red-600">Job not found</p>;

  const shown: ApplicationDraft | undefined = analyze.data ?? draft;
  const analyzeError =
    analyze.error instanceof Error ? analyze.error.message : analyze.error
      ? String(analyze.error)
      : null;
  const assistError =
    browserAssist.error instanceof Error
      ? browserAssist.error.message
      : browserAssist.error
        ? String(browserAssist.error)
        : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Link to={`/results/${runId}`} className="text-sm text-indigo-600 hover:underline">
        ← Back to results
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold">{data.title}</h2>
          <p className="text-slate-500">
            {data.company} · {data.location} · {data.source}
          </p>
        </div>
        <ScoreBadge score={data.score} />
      </div>

      <div className="flex flex-wrap gap-2">
        {data.url && (
          <a
            href={data.url}
            target="_blank"
            rel="noreferrer"
            className="inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Apply / view posting
          </a>
        )}
        <button
          type="button"
          disabled={analyze.isPending || agentStatus?.enabled === false}
          onClick={() => analyze.mutate(!!shown)}
          className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-800 hover:bg-indigo-100 disabled:opacity-50"
        >
          {analyze.isPending
            ? "Analyzing with AI…"
            : shown
              ? "Re-analyze with AI"
              : "Analyze with AI"}
        </button>
        <Link
          to="/apply-queue"
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          Open Apply Queue
        </Link>
      </div>

      {agentStatus && (
        <p className="text-xs text-slate-500">
          Agent: {agentStatus.provider} / {agentStatus.model}
          {!agentStatus.enabled && " (disabled in config)"}
          {agentStatus.provider === "ollama" &&
            " · Needs Ollama running locally (ollama pull llama3.1:8b)"}
        </p>
      )}

      {analyzeError && (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800 whitespace-pre-wrap">
          {analyzeError}
        </div>
      )}
      {(assistError || browserAssist.data) && (
        <div
          className={`rounded-lg px-4 py-3 text-sm whitespace-pre-wrap ${
            assistError ? "bg-rose-50 text-rose-800" : "bg-teal-50 text-teal-900"
          }`}
        >
          {assistError || browserAssist.data?.message}
          {browserAssist.data?.filled?.length
            ? ` · Filled: ${browserAssist.data.filled.join(", ")}`
            : ""}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <SkillBox title="Matched skills" skills={data.matched_keywords} variant="match" />
        <SkillBox title="Missing skills" skills={data.missing_keywords} variant="missing" />
      </div>

      {shown && (
        <AiDraftPanel
          draft={shown}
          onQueueUpdate={(s) => updateQueue.mutate({ status: s })}
          onOpenApply={() => openApply.mutate()}
          openApplyPending={openApply.isPending}
          onBrowserAssist={
            agentStatus?.browser_assist_enabled === false
              ? undefined
              : () => browserAssist.mutate()
          }
          browserAssistPending={browserAssist.isPending}
        />
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-3 font-semibold">Description</h3>
        <div className="prose prose-sm max-w-none whitespace-pre-wrap text-slate-700">
          {stripHtml(data.description).slice(0, 8000)}
        </div>
      </section>
    </div>
  );
}

function AiDraftPanel({
  draft,
  onQueueUpdate,
  onOpenApply,
  openApplyPending,
  onBrowserAssist,
  browserAssistPending,
}: {
  draft: ApplicationDraft;
  onQueueUpdate: (status: string) => void;
  onOpenApply: () => void;
  openApplyPending?: boolean;
  onBrowserAssist?: () => void;
  browserAssistPending?: boolean;
}) {
  const decisionColor =
    draft.decision === "apply"
      ? "bg-emerald-50 text-emerald-800"
      : draft.decision === "skip"
        ? "bg-rose-50 text-rose-800"
        : "bg-amber-50 text-amber-800";

  return (
    <section className="space-y-4 rounded-xl border border-indigo-100 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold text-slate-900">AI analysis</h3>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${decisionColor}`}>
            {draft.decision}
          </span>
          <span className="text-sm text-slate-600">Fit {draft.fit_score.toFixed(0)}/100</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <ListBlock title="Why it fits" items={draft.reasons} />
        <ListBlock title="Gaps" items={draft.gaps} />
        <ListBlock title="Red flags" items={draft.red_flags} />
      </div>

      {draft.tailored_bullets.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Tailored bullets</h4>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {draft.tailored_bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
          <CopyButton text={draft.tailored_bullets.map((b) => `• ${b}`).join("\n")} label="Copy bullets" />
        </div>
      )}

      {draft.cover_letter && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Cover letter draft</h4>
          <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
            {draft.cover_letter}
          </pre>
          <CopyButton text={draft.cover_letter} label="Copy cover letter" />
        </div>
      )}

      {draft.form_answers && Object.keys(draft.form_answers).length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Suggested form answers</h4>
          <dl className="space-y-2 text-sm">
            {Object.entries(draft.form_answers).map(([k, v]) =>
              v ? (
                <div key={k}>
                  <dt className="font-medium text-slate-600">{k.replaceAll("_", " ")}</dt>
                  <dd className="text-slate-800">{v}</dd>
                </div>
              ) : null
            )}
          </dl>
        </div>
      )}

      {draft.clipboard_pack && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-slate-800">Apply pack</h4>
          <CopyButton text={draft.clipboard_pack} label="Copy full apply pack" />
        </div>
      )}

      {draft.queue_id && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
          <span className="text-xs text-slate-500">
            Queue: {draft.queue_status ?? "pending_review"}
          </span>
          <button
            type="button"
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
            onClick={() => onQueueUpdate("approved")}
          >
            Approve
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
            onClick={() => onQueueUpdate("skipped")}
          >
            Skip
          </button>
          <button
            type="button"
            disabled={openApplyPending}
            className="rounded-lg border border-indigo-200 px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            onClick={onOpenApply}
          >
            Open apply + copy pack
          </button>
          {onBrowserAssist && (
            <button
              type="button"
              disabled={browserAssistPending}
              className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-1.5 text-xs text-teal-800 hover:bg-teal-100 disabled:opacity-50"
              onClick={onBrowserAssist}
            >
              {browserAssistPending ? "Launching…" : "Browser fill (you submit)"}
            </button>
          )}
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs hover:bg-slate-50"
            onClick={() => onQueueUpdate("applied")}
          >
            Mark applied
          </button>
        </div>
      )}

      <p className="text-xs text-slate-400">
        {draft.provider}/{draft.model} · Review before submitting — nothing is auto-applied.
      </p>
    </section>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="mb-1 text-sm font-semibold text-slate-800">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400">None</p>
      ) : (
        <ul className="list-disc space-y-1 pl-4 text-sm text-slate-700">
          {items.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  return (
    <button
      type="button"
      className="mt-2 text-xs text-indigo-600 hover:underline"
      onClick={() => navigator.clipboard.writeText(text)}
    >
      {label}
    </button>
  );
}

function SkillBox({
  title,
  skills,
  variant,
}: {
  title: string;
  skills: string[];
  variant: "match" | "missing";
}) {
  const cls =
    variant === "match" ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="mb-2 font-semibold">{title}</h3>
      <div className="flex flex-wrap gap-2">
        {skills.length === 0 ? (
          <span className="text-sm text-slate-400">None</span>
        ) : (
          skills.map((s) => (
            <span key={s} className={`rounded-full px-2 py-0.5 text-xs ${cls}`}>
              {s}
            </span>
          ))
        )}
      </div>
    </div>
  );
}

function stripHtml(html: string): string {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}
