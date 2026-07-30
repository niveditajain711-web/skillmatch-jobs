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

  useEffect(() => {
    if (data?.scoring) {
      setMust(data.scoring.must_have_weight ?? 0.6);
      setNice(data.scoring.nice_to_have_weight ?? 0.3);
      setTitle(data.scoring.title_weight ?? 0.1);
      setMinScore(data.scoring.min_score_to_save ?? 0);
    }
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      api.updateScoring({
        must_have_weight: must,
        nice_to_have_weight: nice,
        title_weight: title,
        min_score_to_save: minScore,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  if (isLoading) return <p className="text-slate-500">Loading settings…</p>;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Settings</h2>
        <p className="text-slate-500">Scoring weights (saved to config.yaml)</p>
      </div>

      <form
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-6"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
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
          disabled={save.isPending}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {save.isPending ? "Saving…" : "Save scoring"}
        </button>
        {save.isSuccess && <p className="text-sm text-emerald-600">Saved.</p>}
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
