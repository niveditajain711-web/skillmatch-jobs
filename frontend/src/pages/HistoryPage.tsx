import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export function HistoryPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["runs"],
    queryFn: api.listRuns,
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">History</h2>
          <p className="text-slate-500">Past search runs</p>
        </div>
        <Link
          to="/search"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          New search
        </Link>
      </div>

      {isLoading ? (
        <p className="text-slate-500">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-slate-600">
              <tr>
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Keywords</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Fetched</th>
                <th className="px-4 py-3">Scored</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data?.map((run) => (
                <tr key={run.id} className="border-b border-slate-100">
                  <td className="px-4 py-3">#{run.id}</td>
                  <td className="px-4 py-3">{run.keywords}</td>
                  <td className="px-4 py-3 capitalize">{run.status}</td>
                  <td className="px-4 py-3">{run.jobs_fetched}</td>
                  <td className="px-4 py-3">{run.jobs_scored}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/results/${run.id}`} className="text-indigo-600 hover:underline">
                      View
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
