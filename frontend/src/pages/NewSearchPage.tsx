import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export function NewSearchPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });

  const [keywords, setKeywords] = useState("java, backend");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [country, setCountry] = useState("in");
  const [yearsOfExperience, setYearsOfExperience] = useState("5");
  const [experienceMax, setExperienceMax] = useState("");
  const [postedWithinDays, setPostedWithinDays] = useState("15");
  const [maxPages, setMaxPages] = useState("1");
  const [keepUnknownExperience, setKeepUnknownExperience] = useState(true);
  const [refresh, setRefresh] = useState(false);
  const [rescoreOnly, setRescoreOnly] = useState(false);
  const [remotive, setRemotive] = useState(true);
  const [arbeitnow, setArbeitnow] = useState(true);
  const [jsearch, setJsearch] = useState(true);
  const [companyBoards, setCompanyBoards] = useState(true);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (!settings || hydrated) return;
    const search = settings.search ?? {};
    const sources = settings.sources ?? {};
    setKeywords(((search.keywords as string[]) ?? ["java", "backend"]).join(", "));
    setRemoteOnly(Boolean(search.remote_only));
    setCountry(((search.countries as string[]) ?? ["in"])[0] ?? "in");
    setYearsOfExperience(
      search.years_of_experience != null ? String(search.years_of_experience) : ""
    );
    setExperienceMax(search.experience_max != null ? String(search.experience_max) : "");
    setPostedWithinDays(
      search.posted_within_days != null ? String(search.posted_within_days) : "15"
    );
    setMaxPages(search.max_pages != null ? String(search.max_pages) : "1");
    setKeepUnknownExperience(Boolean(search.keep_unknown_experience ?? true));
    setRemotive(sources.remotive?.enabled ?? true);
    setArbeitnow(sources.arbeitnow?.enabled ?? true);
    setJsearch(sources.jsearch?.enabled ?? true);
    setCompanyBoards(sources.company_boards?.enabled ?? true);
    setHydrated(true);
  }, [settings, hydrated]);

  const mutation = useMutation({
    mutationFn: () => {
      const yoe = yearsOfExperience.trim();
      const emax = experienceMax.trim();
      return api.createRun({
        search: {
          keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
          remote_only: remoteOnly,
          countries: [country],
          years_of_experience: yoe === "" ? null : Number(yoe),
          experience_max: emax === "" ? null : Number(emax),
          keep_unknown_experience: keepUnknownExperience,
          posted_within_days: Number(postedWithinDays) || undefined,
          max_pages: Number(maxPages) || undefined,
        },
        sources: { remotive, arbeitnow, jsearch, company_boards: companyBoards },
        refresh,
        rescore_only: rescoreOnly,
      });
    },
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
        <p className="text-slate-500">
          Defaults load from Settings. Override here for this run only.
        </p>
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

        <div className="grid grid-cols-2 gap-3">
          <Field label="Country code">
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="in"
            />
          </Field>
          <Field label="Posted within (days)">
            <input
              type="number"
              min={1}
              max={90}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={postedWithinDays}
              onChange={(e) => setPostedWithinDays(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Your years of experience">
            <input
              type="number"
              min={0}
              max={40}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={yearsOfExperience}
              onChange={(e) => setYearsOfExperience(e.target.value)}
              placeholder="e.g. 5"
            />
          </Field>
          <Field label="Max experience to include">
            <input
              type="number"
              min={0}
              max={40}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              value={experienceMax}
              onChange={(e) => setExperienceMax(e.target.value)}
              placeholder="blank = no cap"
            />
          </Field>
        </div>

        <Field label="JSearch pages (this run)">
          <input
            type="number"
            min={1}
            max={5}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
            value={maxPages}
            onChange={(e) => setMaxPages(e.target.value)}
          />
        </Field>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={keepUnknownExperience}
            onChange={(e) => setKeepUnknownExperience(e.target.checked)}
          />
          Keep jobs that don’t mention experience
        </label>

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
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={companyBoards}
              onChange={(e) => setCompanyBoards(e.target.checked)}
            />
            Company boards (keyword match on description)
          </label>
        </fieldset>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} />
          Ignore cache (refresh) — use when results look stale
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
