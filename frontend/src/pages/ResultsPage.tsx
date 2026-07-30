import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import { ScoreBadge } from "../components/ScoreBadge";

export function ResultsPage() {
  const { runId } = useParams<{ runId: string }>();
  const id = Number(runId);
  const [minScore, setMinScore] = useState(0);

  const { data: run } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["jobs", id, minScore],
    queryFn: () => api.listRunJobs(id, minScore || undefined),
    enabled: !!id && run?.status === "completed",
    refetchInterval: run?.status === "running" ? 3000 : false,
  });

  if (!id) return <p>Invalid run</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold">Results</h2>
          <p className="text-slate-500">
            Run #{id} · {run?.keywords} ·{" "}
            <span className="capitalize">{run?.status ?? "…"}</span>
          </p>
        </div>
        {run?.report_path && (
          <span className="text-xs text-slate-400">Excel: {run.report_path}</span>
        )}
      </div>

      {run?.status === "running" && (
        <div className="rounded-lg bg-amber-50 px-4 py-3 text-amber-800">
          Search in progress… this page refreshes automatically.
        </div>
      )}

      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-600">
          Min score:
          <input
            type="number"
            min={0}
            max={100}
            className="ml-2 w-20 rounded border border-slate-300 px-2 py-1"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
          />
        </label>
      </div>

      {isLoading ? (
        <p className="text-slate-500">Loading jobs…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Matched</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {jobs?.map((job) => (
                <tr key={job.job_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <ScoreBadge score={job.score} />
                  </td>
                  <td className="px-4 py-3 font-medium">{job.title}</td>
                  <td className="px-4 py-3">{job.company}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {job.matched_keywords.slice(0, 4).join(", ")}
                  </td>
                  <td className="px-4 py-3">{job.source}</td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/results/${id}/jobs/${job.job_id}`}
                      className="text-indigo-600 hover:underline"
                    >
                      Details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
