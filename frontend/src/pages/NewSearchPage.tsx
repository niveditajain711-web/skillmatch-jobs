import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export function NewSearchPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });

  const search = settings?.search as Record<string, unknown> | undefined;
  const sources = settings?.sources ?? {};

  const [keywords, setKeywords] = useState(
    () => ((search?.keywords as string[]) ?? ["java", "backend"]).join(", ")
  );
  const [remoteOnly, setRemoteOnly] = useState(Boolean(search?.remote_only));
  const [country, setCountry] = useState(
    () => ((search?.countries as string[]) ?? ["in"])[0] ?? "in"
  );
  const [refresh, setRefresh] = useState(false);
  const [rescoreOnly, setRescoreOnly] = useState(false);
  const [remotive, setRemotive] = useState(sources.remotive?.enabled ?? true);
  const [arbeitnow, setArbeitnow] = useState(sources.arbeitnow?.enabled ?? true);
  const [jsearch, setJsearch] = useState(sources.jsearch?.enabled ?? false);

  const mutation = useMutation({
    mutationFn: () =>
      api.createRun({
        search: {
          keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
          remote_only: remoteOnly,
          countries: [country],
        },
        sources: { remotive, arbeitnow, jsearch },
        refresh,
        rescore_only: rescoreOnly,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      navigate("/history");
    },
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">New Search</h2>
        <p className="text-slate-500">Configure and run a job search</p>
      </div>

      <form
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-6"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Keywords (comma-separated)">
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
          />
        </Field>

        <Field label="Country code">
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="in"
          />
          <p className="mt-1 text-xs text-slate-500">
            Applied to JSearch and as a post-fetch filter for all sources (India cities, etc.).
          </p>
        </Field>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          Remote only
        </label>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-slate-700">Sources</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={remotive} onChange={(e) => setRemotive(e.target.checked)} />
            Remotive (free)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={arbeitnow} onChange={(e) => setArbeitnow(e.target.checked)} />
            Arbeitnow (free)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={jsearch} onChange={(e) => setJsearch(e.target.checked)} />
            JSearch / RapidAPI
          </label>
        </fieldset>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} />
          Ignore cache (refresh)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={rescoreOnly} onChange={(e) => setRescoreOnly(e.target.checked)} />
          Rescore only (no API fetch)
        </label>

        {mutation.error && (
          <p className="text-sm text-red-600">{(mutation.error as Error).message}</p>
        )}

        <button
          type="submit"
          disabled={mutation.isPending}
          className="w-full rounded-lg bg-indigo-600 py-2.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {mutation.isPending ? "Starting…" : "Run search"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}
