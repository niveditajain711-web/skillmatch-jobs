export function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70
      ? "bg-emerald-100 text-emerald-800"
      : score >= 40
        ? "bg-amber-100 text-amber-800"
        : "bg-slate-200 text-slate-700";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-sm font-semibold ${color}`}>
      {score.toFixed(0)}
    </span>
  );
}
