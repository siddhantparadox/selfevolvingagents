"use client";

import { useEffect, useMemo, useState } from "react";

type Variant = {
  name?: string;
  prompt?: string;
};

type VariantRun = {
  split?: string;
  dataset_name?: string;
  name?: string;
  experiment?: string;
  metrics?: Record<string, number>;
};

type StatusPayload = {
  phase?: string;
  reason?: string;
  updated_at?: string;
  server_time?: string;
  source_experiment?: string;
  last_run_prefix?: string;
  dataset_splits?: Array<{ split?: string; dataset_name?: string }>;
  new_trace_count?: number;
  pending_trace_count?: number;
  variants?: Variant[];
  findings?: string[];
  why_it_failed?: string[];
  variant_runs?: VariantRun[];
  winner?: VariantRun | null;
  promoted?: boolean | null;
};

const POLL_MS = 3000;
const PHASES = [
  "starting",
  "waiting_for_traces",
  "building_trace_snapshot",
  "strategies_generated",
  "evaluating_variants",
  "cycle_complete",
];
const METRIC_LABELS: Record<string, string> = {
  judge_calmer_end_state_binary: "Calmer End State",
  judge_emergency_services_when_needed_binary: "Emergency Policy Correct",
  judge_turns_to_calm_state: "Calm Achieved",
  judge_turns_to_emergency_services: "Emergency Mentioned",
};
const PRIMARY_METRICS = [
  "judge_calmer_end_state_binary",
  "judge_emergency_services_when_needed_binary",
  "judge_turns_to_calm_state",
  "judge_turns_to_emergency_services",
];

function formatWhen(ts?: string) {
  if (!ts) return "n/a";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

function fmtScore(v?: number) {
  if (typeof v !== "number") return "n/a";
  return `${Math.round(v * 100)}%`;
}

export default function AutotuneStatusPage() {
  const [data, setData] = useState<StatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;

    const load = async () => {
      try {
        const res = await fetch("/api/autotune/status", { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`status ${res.status}`);
        }
        const json = (await res.json()) as StatusPayload;
        if (!canceled) {
          setData(json);
          setError(null);
        }
      } catch (e) {
        if (!canceled) {
          setError(e instanceof Error ? e.message : "Failed to load status.");
        }
      }
    };

    void load();
    const id = setInterval(load, POLL_MS);
    return () => {
      canceled = true;
      clearInterval(id);
    };
  }, []);

  const metricKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const run of data?.variant_runs ?? []) {
      for (const key of Object.keys(run.metrics ?? {})) {
        keys.add(key);
      }
    }
    return [...keys].sort();
  }, [data?.variant_runs]);

  const phaseIndex = Math.max(0, PHASES.indexOf(data?.phase ?? ""));
  const progress = PHASES.includes(data?.phase ?? "")
    ? Math.round(((phaseIndex + 1) / PHASES.length) * 100)
    : 0;
  const splitRuns = useMemo(() => {
    const grouped: Record<string, VariantRun[]> = {};
    for (const run of data?.variant_runs ?? []) {
      const split = run.split ?? "all";
      grouped[split] = grouped[split] ?? [];
      grouped[split].push(run);
    }
    return grouped;
  }, [data?.variant_runs]);

  return (
    <main className="min-h-screen bg-[radial-gradient(1200px_500px_at_8%_0%,#25475d_0%,#101620_52%),linear-gradient(180deg,#0a1017,#0c131a)] text-slate-100">
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-2xl border border-cyan-200/25 bg-black/35 p-6 backdrop-blur">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-cyan-100 sm:text-3xl">
                Autotune Strategy Dashboard
              </h1>
              <p className="mt-2 text-sm text-cyan-50/80">
                Trace pull {"->"} strategy generation {"->"} Braintrust validation.
              </p>
            </div>
            <div className="rounded-xl border border-cyan-300/30 bg-cyan-400/10 px-4 py-2 text-right">
              <p className="text-xs uppercase tracking-wide text-cyan-100/80">Last Update</p>
              <p className="text-sm font-medium text-cyan-50">{formatWhen(data?.updated_at ?? data?.server_time)}</p>
            </div>
          </div>
          <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-400 via-teal-400 to-emerald-400 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-sm">
            <span className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-3 py-1">
              phase: <strong>{data?.phase ?? "loading"}</strong>
            </span>
            <span className="rounded-full border border-slate-300/20 bg-slate-700/40 px-3 py-1">
              run: <strong>{data?.last_run_prefix ?? "n/a"}</strong>
            </span>
          </div>
          {error ? <p className="mt-3 text-sm text-red-300">Error: {error}</p> : null}
        </header>

        <section className="mt-6 rounded-2xl border border-slate-200/10 bg-slate-950/40 p-5">
          <h2 className="text-lg font-semibold text-amber-200">1) Trace Intake Status</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-amber-200/20 bg-amber-400/10 p-4">
              <p className="text-xs uppercase tracking-widest text-amber-100/80">New Traces Pulled</p>
              <p className="mt-2 text-3xl font-bold text-amber-100">{data?.new_trace_count ?? 0}</p>
            </div>
            <div className="rounded-xl border border-blue-200/20 bg-blue-400/10 p-4">
              <p className="text-xs uppercase tracking-widest text-blue-100/80">Pending Queue</p>
              <p className="mt-2 text-3xl font-bold text-blue-100">{data?.pending_trace_count ?? 0}</p>
            </div>
            <div className="rounded-xl border border-emerald-200/20 bg-emerald-400/10 p-4">
              <p className="text-xs uppercase tracking-widest text-emerald-100/80">Source Experiment</p>
              <p className="mt-2 truncate text-sm font-medium text-emerald-50">
                {data?.source_experiment && data.source_experiment.length > 0
                  ? data.source_experiment
                  : "all project logs"}
              </p>
              <p className="mt-1 truncate text-xs text-emerald-100/70">
                run: {data?.last_run_prefix ?? "n/a"}
              </p>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            {(data?.dataset_splits ?? []).map((s, i) => (
              <span key={`${s.split ?? "split"}-${i}`} className="rounded-full border border-indigo-300/25 bg-indigo-400/10 px-2 py-1 text-indigo-100">
                {(s.split ?? "all").toUpperCase()}: {s.dataset_name ?? "n/a"}
              </span>
            ))}
          </div>
          <p className="mt-4 text-sm text-slate-300">{data?.reason ?? ""}</p>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200/10 bg-slate-950/40 p-5">
          <h2 className="text-lg font-semibold text-fuchsia-200">2) Strategies Under Test</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {(data?.variants ?? []).slice(0, 2).map((variant, idx) => (
              <article
                key={`${variant.name ?? "variant"}-${idx}`}
                className="rounded-xl border border-fuchsia-200/25 bg-gradient-to-b from-fuchsia-500/15 to-fuchsia-700/5 p-4"
              >
                <h3 className="text-sm font-semibold uppercase tracking-wide text-fuchsia-100">
                  {variant.name ?? `variant_${idx + 1}`}
                </h3>
                <p className="mt-1 text-xs text-fuchsia-100/70">
                  {variant.prompt ? `${variant.prompt.length} chars` : "pending"}
                </p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-fuchsia-50/90">
                  {variant.prompt ?? "Waiting for generated strategy prompt..."}
                </p>
              </article>
            ))}
            {(data?.variants ?? []).length === 0 ? (
              <div className="rounded-xl border border-slate-300/20 bg-slate-800/40 p-4 text-sm text-slate-300">
                Waiting for strategy generation...
              </div>
            ) : null}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200/10 bg-slate-950/40 p-5">
          <h2 className="text-lg font-semibold text-emerald-200">3) Braintrust / Validation Results</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(splitRuns).map(([split, runs]) => (
              <div key={split} className="rounded-xl border border-emerald-200/20 bg-emerald-500/10 p-3">
                <p className="text-xs uppercase tracking-wide text-emerald-100/80">{split} split</p>
                {runs.map((r, idx) => (
                  <p key={`${r.name ?? idx}`} className="mt-2 text-sm text-emerald-50">
                    {(r.name ?? `variant_${idx + 1}`)}: <span className="font-medium">
                      {fmtScore(r.metrics?.judge_calmer_end_state_binary)}
                    </span>{" "}
                    calm,{" "}
                    <span className="font-medium">
                      {fmtScore(r.metrics?.judge_emergency_services_when_needed_binary)}
                    </span>{" "}
                    emergency
                  </p>
                ))}
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PRIMARY_METRICS.map((metricKey) => {
              const vals = (data?.variant_runs ?? [])
                .map((r) => r.metrics?.[metricKey])
                .filter((v): v is number => typeof v === "number");
              const avg =
                vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : undefined;
              return (
                <div key={metricKey} className="rounded-xl border border-slate-300/20 bg-slate-900/50 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-300">
                    {METRIC_LABELS[metricKey] ?? metricKey}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-slate-100">{fmtScore(avg)}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-4 overflow-x-auto rounded-xl border border-emerald-200/20">
            <table className="min-w-full text-sm">
              <thead className="bg-emerald-500/10">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-emerald-100">Metric</th>
                  {(data?.variant_runs ?? []).map((run, idx) => (
                    <th key={`${run.name ?? "run"}-${idx}`} className="px-3 py-2 text-left font-semibold text-emerald-100">
                      {run.split ? `${run.split}:${run.name ?? `variant_${idx + 1}`}` : run.name ?? `variant_${idx + 1}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metricKeys.map((key) => (
                  <tr key={key} className="border-t border-emerald-100/10">
                    <td className="px-3 py-2 text-emerald-50/90">{METRIC_LABELS[key] ?? key}</td>
                    {(data?.variant_runs ?? []).map((run, idx) => (
                      <td key={`${key}-${run.name ?? idx}`} className="px-3 py-2 text-emerald-50/90">
                        {fmtScore(run.metrics?.[key])}
                      </td>
                    ))}
                  </tr>
                ))}
                {metricKeys.length === 0 ? (
                  <tr>
                    <td className="px-3 py-3 text-slate-300" colSpan={Math.max((data?.variant_runs?.length ?? 0) + 1, 2)}>
                      Waiting for evaluation metrics...
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-cyan-300/20 bg-cyan-400/10 p-3 text-sm text-cyan-50">
              Winner: {data?.winner?.split ? `${data.winner.split}:` : ""}{data?.winner?.name ?? "n/a"}{" "}
              {data?.winner?.experiment ? `(${data.winner.experiment})` : ""}
            </div>
            <div className="rounded-lg border border-amber-300/20 bg-amber-400/10 p-3 text-sm text-amber-50">
              Promotion: {data?.promoted == null ? "n/a" : data.promoted ? "promoted" : "not promoted"}
            </div>
          </div>
          {(data?.findings ?? []).length > 0 ? (
            <div className="mt-4 rounded-lg border border-slate-300/20 bg-slate-800/40 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-300">Latest Findings</p>
              <ul className="mt-2 list-disc pl-5 text-sm text-slate-200">
                {(data?.findings ?? []).slice(0, 4).map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
