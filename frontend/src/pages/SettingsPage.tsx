import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api/client";

export function SettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });

  const [must, setMust] = useState(0.6);
  const [nice, setNice] = useState(0.3);
  const [title, setTitle] = useState(0.1);
  const [minScore, setMinScore] = useState(0);

  const [yearsOfExperience, setYearsOfExperience] = useState("5");
  const [experienceMin, setExperienceMin] = useState("");
  const [experienceMax, setExperienceMax] = useState("");
  const [keepUnknownExperience, setKeepUnknownExperience] = useState(true);
  const [experienceTolerance, setExperienceTolerance] = useState("2");
  const [country, setCountry] = useState("in");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [postedWithinDays, setPostedWithinDays] = useState("15");
  const [maxPages, setMaxPages] = useState("1");
  const [jsearchVariants, setJsearchVariants] = useState("1");
  const [cacheTtlHours, setCacheTtlHours] = useState("6");
  const [cacheEnabled, setCacheEnabled] = useState(true);

  useEffect(() => {
    if (data?.scoring) {
      setMust(data.scoring.must_have_weight ?? 0.6);
      setNice(data.scoring.nice_to_have_weight ?? 0.3);
      setTitle(data.scoring.title_weight ?? 0.1);
      setMinScore(data.scoring.min_score_to_save ?? 0);
    }
    if (data?.search) {
      const s = data.search;
      setYearsOfExperience(
        s.years_of_experience != null ? String(s.years_of_experience) : ""
      );
      setExperienceMin(s.experience_min != null ? String(s.experience_min) : "");
      setExperienceMax(s.experience_max != null ? String(s.experience_max) : "");
      setKeepUnknownExperience(Boolean(s.keep_unknown_experience ?? true));
      setExperienceTolerance(
        s.experience_tolerance != null ? String(s.experience_tolerance) : "2"
      );
      setPostedWithinDays(
        s.posted_within_days != null ? String(s.posted_within_days) : "15"
      );
      setMaxPages(s.max_pages != null ? String(s.max_pages) : "1");
      setJsearchVariants(
        s.jsearch_max_query_variants != null ? String(s.jsearch_max_query_variants) : "1"
      );
      const countries = s.countries as string[] | undefined;
      setCountry(countries?.[0] ?? "in");
      setRemoteOnly(Boolean(s.remote_only));
    }
    if (data?.cache) {
      setCacheTtlHours(
        data.cache.ttl_hours != null ? String(data.cache.ttl_hours) : "6"
      );
      setCacheEnabled(Boolean(data.cache.enabled ?? true));
    }
  }, [data]);

  const saveScoring = useMutation({
    mutationFn: () =>
      api.updateScoring({
        must_have_weight: must,
        nice_to_have_weight: nice,
        title_weight: title,
        min_score_to_save: minScore,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const saveSearch = useMutation({
    mutationFn: () => {
      const yoe = yearsOfExperience.trim();
      const emin = experienceMin.trim();
      const emax = experienceMax.trim();
      return api.updateSearchSettings({
        clear_years_of_experience: yoe === "",
        clear_experience_min: emin === "",
        clear_experience_max: emax === "",
        ...(yoe !== "" ? { years_of_experience: Number(yoe) } : {}),
        ...(emin !== "" ? { experience_min: Number(emin) } : {}),
        ...(emax !== "" ? { experience_max: Number(emax) } : {}),
        keep_unknown_experience: keepUnknownExperience,
        experience_tolerance: Number(experienceTolerance) || 1,
        remote_only: remoteOnly,
        countries: [country.trim() || "in"],
        posted_within_days: Number(postedWithinDays) || 15,
        max_pages: Number(maxPages) || 1,
        jsearch_max_query_variants: Number(jsearchVariants) || 1,
        cache_ttl_hours: Number(cacheTtlHours) || 6,
        cache_enabled: cacheEnabled,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  if (isLoading) return <p className="text-slate-500">Loading settings…</p>;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Settings</h2>
        <p className="text-slate-500">Search preferences — saved for future runs</p>
      </div>

      <form
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-6"
        onSubmit={(e) => {
          e.preventDefault();
          saveSearch.mutate();
        }}
      >
        <h3 className="font-semibold text-slate-800">Experience filter</h3>

        <label className="block text-sm">
          Your years of experience
          <input
            type="number"
            min={0}
            max={40}
            step={1}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={yearsOfExperience}
            onChange={(e) => setYearsOfExperience(e.target.value)}
            placeholder="e.g. 5"
          />
        </label>

        <label className="block text-sm">
          Max experience to include (years)
          <input
            type="number"
            min={0}
            max={40}
            step={1}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={experienceMax}
            onChange={(e) => setExperienceMax(e.target.value)}
            placeholder="e.g. 8 — leave blank for no cap"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Skip roles asking for more than this (e.g. Staff/Principal at 10+ yrs). Leave blank to
            include all seniority levels.
          </span>
        </label>

        <label className="block text-sm">
          Min experience to include (optional)
          <input
            type="number"
            min={0}
            max={40}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={experienceMin}
            onChange={(e) => setExperienceMin(e.target.value)}
            placeholder="e.g. 2 — skip pure junior roles"
          />
        </label>

        <label className="block text-sm">
          Tolerance (years)
          <input
            type="number"
            min={0}
            max={5}
            step={0.5}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={experienceTolerance}
            onChange={(e) => setExperienceTolerance(e.target.value)}
          />
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={keepUnknownExperience}
            onChange={(e) => setKeepUnknownExperience(e.target.checked)}
          />
          Keep jobs that don’t mention experience
        </label>

        <h3 className="pt-2 font-semibold text-slate-800">Search volume & freshness</h3>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            Posted within (days)
            <input
              type="number"
              min={1}
              max={90}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={postedWithinDays}
              onChange={(e) => setPostedWithinDays(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            JSearch pages
            <input
              type="number"
              min={1}
              max={5}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={maxPages}
              onChange={(e) => setMaxPages(e.target.value)}
            />
          </label>
        </div>

        <label className="block text-sm">
          JSearch query variants
          <input
            type="number"
            min={1}
            max={5}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={jsearchVariants}
            onChange={(e) => setJsearchVariants(e.target.value)}
          />
          <span className="mt-1 block text-xs text-slate-500">
            1 = single query only. 2–3 splits keywords into separate searches (uses more RapidAPI
            quota).
          </span>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            Cache TTL (hours)
            <input
              type="number"
              min={0}
              max={168}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={cacheTtlHours}
              onChange={(e) => setCacheTtlHours(e.target.value)}
            />
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={cacheEnabled}
              onChange={(e) => setCacheEnabled(e.target.checked)}
            />
            Enable API cache
          </label>
        </div>

        <h3 className="pt-2 font-semibold text-slate-800">Location</h3>

        <label className="block text-sm">
          Default country code
          <input
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="in"
          />
        </label>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={remoteOnly}
            onChange={(e) => setRemoteOnly(e.target.checked)}
          />
          Remote only (default)
        </label>

        <button
          type="submit"
          disabled={saveSearch.isPending}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {saveSearch.isPending ? "Saving…" : "Save search settings"}
        </button>
        {saveSearch.isSuccess && <p className="text-sm text-emerald-600">Saved.</p>}
        {saveSearch.error && (
          <p className="text-sm text-red-600">{(saveSearch.error as Error).message}</p>
        )}
      </form>

      <form
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-6"
        onSubmit={(e) => {
          e.preventDefault();
          saveScoring.mutate();
        }}
      >
        <h3 className="font-semibold text-slate-800">Scoring weights</h3>
        <Slider label="Must-have weight" value={must} onChange={setMust} />
        <Slider label="Nice-to-have weight" value={nice} onChange={setNice} />
        <Slider label="Title weight" value={title} onChange={setTitle} />
        <label className="block text-sm">
          Min score to save
          <input
            type="number"
            min={0}
            max={100}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
          />
        </label>

        <button
          type="submit"
          disabled={saveScoring.isPending}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {saveScoring.isPending ? "Saving…" : "Save scoring"}
        </button>
        {saveScoring.isSuccess && <p className="text-sm text-emerald-600">Saved.</p>}
      </form>

      <section className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
        <h3 className="mb-2 font-semibold text-slate-800">Active sources</h3>
        <ul className="list-inside list-disc">
          {Object.entries(data?.sources ?? {}).map(([name, cfg]) => (
            <li key={name}>
              {name}: {cfg.enabled ? "enabled" : "disabled"}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-500">
          Company boards match keywords against job descriptions (not titles only).
        </p>
      </section>
    </div>
  );
}

function Slider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block text-sm">
      {label}: {value.toFixed(2)}
      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        className="mt-1 w-full"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}
