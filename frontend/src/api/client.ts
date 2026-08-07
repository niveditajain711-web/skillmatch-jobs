const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export interface Run {
  id: number;
  started_at: string | null;
  keywords: string;
  status: string;
  jobs_fetched: number;
  jobs_scored: number;
  report_path: string | null;
  resume_skills: string[] | null;
}

export interface JobScore {
  job_id: number;
  score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  title: string;
  company: string;
  location: string;
  source: string;
  url: string;
  is_remote: boolean | null;
  posted_at: string | null;
}

export interface JobDetail extends JobScore {
  run_id: number;
  description: string;
}

export interface Dashboard {
  latest_run: Run | null;
  top_matches: JobScore[];
  avg_score: number | null;
  gaps: { skill: string; jobs_missing_count: number }[];
}

export interface ResumeInfo {
  source_path: string;
  skills: string[];
  text_preview: string;
}

export interface Settings {
  search: Record<string, unknown>;
  sources: Record<string, { enabled: boolean }>;
  scoring: Record<string, number>;
  cache: Record<string, unknown>;
}

export interface CreateRunBody {
  search?: {
    keywords?: string[];
    location?: string;
    remote_only?: boolean;
    countries?: string[];
    max_results_per_source?: number;
    posted_within_days?: number;
    max_pages?: number;
    years_of_experience?: number | null;
    experience_min?: number;
    experience_max?: number | null;
    keep_unknown_experience?: boolean;
    experience_tolerance?: number;
  };
  sources?: {
    jsearch?: boolean;
    remotive?: boolean;
    arbeitnow?: boolean;
    company_boards?: boolean;
  };
  scoring?: {
    must_have_weight?: number;
    nice_to_have_weight?: number;
    title_weight?: number;
    min_score_to_save?: number;
  };
  refresh?: boolean;
  rescore_only?: boolean;
}

export const api = {
  health: () => request<{ status: string }>("/../health".replace("/v1/../", "/")),
  dashboard: () => request<Dashboard>("/dashboard"),
  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: number) => request<Run>(`/runs/${id}`),
  createRun: (body: CreateRunBody) =>
    request<{ run_id: number; status: string; message: string }>("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  listRunJobs: (runId: number, opts?: { minScore?: number; source?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (opts?.minScore != null && opts.minScore > 0) {
      params.set("min_score", String(opts.minScore));
    }
    if (opts?.source) params.set("source", opts.source);
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    const q = params.toString() ? `?${params.toString()}` : "";
    return request<JobScore[]>(`/runs/${runId}/jobs${q}`);
  },
  getRunJob: (runId: number, jobId: number) =>
    request<JobDetail>(`/runs/${runId}/jobs/${jobId}`),
  getResume: () => request<ResumeInfo>("/resume"),
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ResumeInfo>("/resume", { method: "POST", body: form });
  },
  getSettings: () => request<Settings>("/settings"),
  updateScoring: (scoring: Record<string, number>) =>
    request<Settings>("/settings/scoring", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scoring),
    }),
  updateSearchSettings: (search: {
    years_of_experience?: number | null;
    experience_min?: number | null;
    experience_max?: number | null;
    keep_unknown_experience?: boolean;
    experience_tolerance?: number;
    remote_only?: boolean;
    countries?: string[];
    max_pages?: number;
    posted_within_days?: number;
    max_results_per_source?: number;
    jsearch_max_query_variants?: number;
    cache_ttl_hours?: number;
    cache_enabled?: boolean;
    clear_years_of_experience?: boolean;
    clear_experience_min?: boolean;
    clear_experience_max?: boolean;
  }) =>
    request<Settings>("/settings/search", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(search),
    }),
};
