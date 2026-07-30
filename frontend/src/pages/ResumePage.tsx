import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "../api/client";

export function ResumePage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["resume"],
    queryFn: api.getResume,
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadResume(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["resume"] });
      setSelectedName(null);
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  if (isLoading) return <p className="text-slate-500">Loading resume…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Resume</h2>
        <p className="text-slate-500">Upload PDF or text — skills are extracted automatically</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-6">
        <p className="text-sm text-slate-500">
          Current file: <span className="font-medium text-slate-700">{data?.source_path}</span>
        </p>

        <div>
          <h3 className="mb-2 font-semibold">Detected skills ({data?.skills.length})</h3>
          <div className="flex flex-wrap gap-2">
            {data?.skills.map((s) => (
              <span key={s} className="rounded-full bg-indigo-50 px-3 py-1 text-sm text-indigo-700">
                {s}
              </span>
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-2 font-semibold">Preview</h3>
          <p className="rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600">
            {data?.text_preview}…
          </p>
        </div>

        <div className="rounded-xl border-2 border-dashed border-indigo-200 bg-indigo-50/40 p-6">
          <h3 className="mb-1 font-semibold text-slate-800">Upload new resume</h3>
          <p className="mb-4 text-sm text-slate-500">PDF or plain text (.pdf, .txt, .md)</p>

          <input
            ref={inputRef}
            id="resume-upload"
            type="file"
            accept=".pdf,.txt,.md"
            className="sr-only"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setSelectedName(f.name);
                upload.mutate(f);
              }
            }}
          />

          <div className="flex flex-wrap items-center gap-3">
            <label
              htmlFor="resume-upload"
              className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus-within:ring-2 focus-within:ring-indigo-500 focus-within:ring-offset-2"
            >
              <UploadIcon />
              Choose file
            </label>

            {selectedName && !upload.isPending && (
              <span className="text-sm text-slate-600">Selected: {selectedName}</span>
            )}
            {upload.isPending && (
              <span className="text-sm font-medium text-indigo-700">Uploading…</span>
            )}
            {upload.isSuccess && (
              <span className="text-sm font-medium text-emerald-700">Resume updated</span>
            )}
            {upload.isError && (
              <span className="text-sm text-red-600">{(upload.error as Error).message}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function UploadIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
      />
    </svg>
  );
}
