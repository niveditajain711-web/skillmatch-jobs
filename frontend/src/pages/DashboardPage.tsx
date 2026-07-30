import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ScoreBadge } from "../components/ScoreBadge";

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: api.dashboard,
    refetchInterval: 5000,
  });

  if (isLoading) return <p className="text-slate-500">Loading dashboard…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;

  const run = data?.latest_run;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <p className="text-slate-500">Overview of your latest job search run</p>
      </div>

      {!run ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-slate-600">No searches yet.</p>
          <Link
            to="/search"
            className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Run your first search
          </Link>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <StatCard label="Status" value={run.status} />
            <StatCard label="Jobs fetched" value={String(run.jobs_fetched)} />
            <StatCard label="Jobs scored" value={String(run.jobs_scored)} />
            <StatCard
              label="Avg score"
              value={data?.avg_score != null ? data.avg_score.toFixed(1) : "—"}
            />
          </div>

          <div className="flex gap-3">
            <Link
              to={`/results/${run.id}`}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              View results
            </Link>
            <Link
              to="/search"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-50"
            >
              New search
            </Link>
          </div>

          <section>
            <h3 className="mb-3 text-lg font-semibold">Top matches</h3>
            <div className="space-y-2">
              {data?.top_matches.map((job) => (
                <Link
                  key={job.job_id}
                  to={`/results/${run.id}/jobs/${job.job_id}`}
                  className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-200"
                >
                  <div>
                    <p className="font-medium">{job.title}</p>
                    <p className="text-sm text-slate-500">
                      {job.company} · {job.source}
                    </p>
                  </div>
                  <ScoreBadge score={job.score} />
                </Link>
              ))}
            </div>
          </section>

          {data?.gaps && data.gaps.length > 0 && (
            <section>
              <h3 className="mb-3 text-lg font-semibold">Common skill gaps</h3>
              <div className="flex flex-wrap gap-2">
                {data.gaps.map((g) => (
                  <span
                    key={g.skill}
                    className="rounded-full bg-rose-50 px-3 py-1 text-sm text-rose-700"
                  >
                    {g.skill} ({g.jobs_missing_count})
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-bold capitalize">{value}</p>
    </div>
  );
}
