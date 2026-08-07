import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useMemo, useState } from "react";
import { api, type JobScore } from "../api/client";
import { ScoreBadge } from "../components/ScoreBadge";

type RemoteFilter = "all" | "remote" | "onsite";

function formatLocation(job: JobScore): string {
  const loc = (job.location || "").trim();
  if (job.is_remote === true) {
    return loc ? `${loc} · Remote` : "Remote";
  }
  if (job.is_remote === false && loc) return loc;
  return loc || "—";
}

function formatPosted(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "—";
  }
}

export function ResultsPage() {
  const { runId } = useParams<{ runId: string }>();
  const id = Number(runId);

  const [minScore, setMinScore] = useState(0);
  const [sourceFilter, setSourceFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [companyFilter, setCompanyFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [skillFilter, setSkillFilter] = useState("");
  const [remoteFilter, setRemoteFilter] = useState<RemoteFilter>("all");

  const { data: run } = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.listRunJobs(id, { limit: 500 }),
    enabled: !!id && run?.status === "completed",
    refetchInterval: run?.status === "running" ? 3000 : false,
  });

  const sources = useMemo(() => {
    const set = new Set((jobs ?? []).map((j) => j.source));
    return Array.from(set).sort();
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    let list = jobs ?? [];

    if (minScore > 0) {
      list = list.filter((j) => j.score >= minScore);
    }
    if (sourceFilter) {
      list = list.filter((j) => j.source === sourceFilter);
    }
    if (locationFilter.trim()) {
      const q = locationFilter.trim().toLowerCase();
      list = list.filter((j) => formatLocation(j).toLowerCase().includes(q));
    }
    if (companyFilter.trim()) {
      const q = companyFilter.trim().toLowerCase();
      list = list.filter((j) => j.company.toLowerCase().includes(q));
    }
    if (titleFilter.trim()) {
      const q = titleFilter.trim().toLowerCase();
      list = list.filter((j) => j.title.toLowerCase().includes(q));
    }
    if (skillFilter.trim()) {
      const q = skillFilter.trim().toLowerCase();
      list = list.filter(
        (j) =>
          j.matched_keywords.some((k) => k.toLowerCase().includes(q)) ||
          j.missing_keywords.some((k) => k.toLowerCase().includes(q))
      );
    }
    if (remoteFilter === "remote") {
      list = list.filter((j) => j.is_remote === true);
    } else if (remoteFilter === "onsite") {
      list = list.filter((j) => j.is_remote === false);
    }

    return [...list].sort((a, b) => b.score - a.score);
  }, [
    jobs,
    minScore,
    sourceFilter,
    locationFilter,
    companyFilter,
    titleFilter,
    skillFilter,
    remoteFilter,
  ]);

  const clearFilters = () => {
    setMinScore(0);
    setSourceFilter("");
    setLocationFilter("");
    setCompanyFilter("");
    setTitleFilter("");
    setSkillFilter("");
    setRemoteFilter("all");
  };

  const hasActiveFilters =
    minScore > 0 ||
    sourceFilter !== "" ||
    locationFilter.trim() !== "" ||
    companyFilter.trim() !== "" ||
    titleFilter.trim() !== "" ||
    skillFilter.trim() !== "" ||
    remoteFilter !== "all";

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

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800">Filters</h3>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span>
              Showing {filteredJobs.length} of {jobs?.length ?? 0} jobs
            </span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-indigo-600 hover:underline"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <FilterField label="Min score">
            <input
              type="number"
              min={0}
              max={100}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            />
          </FilterField>

          <FilterField label="Source">
            <select
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </FilterField>

          <FilterField label="Location">
            <input
              type="text"
              placeholder="e.g. Bangalore, Remote, India"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={locationFilter}
              onChange={(e) => setLocationFilter(e.target.value)}
            />
          </FilterField>

          <FilterField label="Remote">
            <select
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={remoteFilter}
              onChange={(e) => setRemoteFilter(e.target.value as RemoteFilter)}
            >
              <option value="all">All</option>
              <option value="remote">Remote only</option>
              <option value="onsite">On-site only</option>
            </select>
          </FilterField>

          <FilterField label="Company">
            <input
              type="text"
              placeholder="Company name"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
            />
          </FilterField>

          <FilterField label="Title">
            <input
              type="text"
              placeholder="Job title"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={titleFilter}
              onChange={(e) => setTitleFilter(e.target.value)}
            />
          </FilterField>

          <FilterField label="Skill (matched or missing)">
            <input
              type="text"
              placeholder="e.g. java, kafka"
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={skillFilter}
              onChange={(e) => setSkillFilter(e.target.value)}
            />
          </FilterField>
        </div>
      </div>

      {isLoading ? (
        <p className="text-slate-500">Loading jobs…</p>
      ) : filteredJobs.length === 0 ? (
        <p className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-slate-500">
          No jobs match your filters.
          {hasActiveFilters && (
            <>
              {" "}
              <button type="button" onClick={clearFilters} className="text-indigo-600 hover:underline">
                Clear filters
              </button>
            </>
          )}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Posted</th>
                <th className="px-4 py-3">Matched</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map((job) => (
                <tr key={job.job_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <ScoreBadge score={job.score} />
                  </td>
                  <td className="max-w-xs px-4 py-3 font-medium">{job.title}</td>
                  <td className="px-4 py-3">{job.company || "—"}</td>
                  <td className="max-w-[200px] px-4 py-3 text-slate-600">
                    <span className="line-clamp-2" title={formatLocation(job)}>
                      {formatLocation(job)}
                    </span>
                    {job.is_remote === true && (
                      <span className="mt-0.5 inline-block rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">
                        Remote
                      </span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {formatPosted(job.posted_at)}
                  </td>
                  <td className="max-w-[180px] px-4 py-3 text-slate-500">
                    <span className="line-clamp-2" title={job.matched_keywords.join(", ")}>
                      {job.matched_keywords.slice(0, 4).join(", ") || "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-600">{job.source}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <Link
                      to={`/results/${id}/jobs/${job.job_id}`}
                      className="text-indigo-600 hover:underline"
                    >
                      Details
                    </Link>
                    {job.url && (
                      <>
                        {" · "}
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-600 hover:underline"
                        >
                          Apply
                        </a>
                      </>
                    )}
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

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1 text-sm">
      <span className="font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}
