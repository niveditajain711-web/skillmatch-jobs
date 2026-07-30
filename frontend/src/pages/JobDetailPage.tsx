import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ScoreBadge } from "../components/ScoreBadge";

export function JobDetailPage() {
  const { runId, jobId } = useParams<{ runId: string; jobId: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["job", runId, jobId],
    queryFn: () => api.getRunJob(Number(runId), Number(jobId)),
    enabled: !!runId && !!jobId,
  });

  if (isLoading) return <p className="text-slate-500">Loading…</p>;
  if (error || !data) return <p className="text-red-600">Job not found</p>;

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

      <div className="grid gap-4 sm:grid-cols-2">
        <SkillBox title="Matched skills" skills={data.matched_keywords} variant="match" />
        <SkillBox title="Missing skills" skills={data.missing_keywords} variant="missing" />
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h3 className="mb-3 font-semibold">Description</h3>
        <div className="prose prose-sm max-w-none whitespace-pre-wrap text-slate-700">
          {stripHtml(data.description).slice(0, 8000)}
        </div>
      </section>
    </div>
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
    variant === "match"
      ? "bg-emerald-50 text-emerald-800"
      : "bg-rose-50 text-rose-800";
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
