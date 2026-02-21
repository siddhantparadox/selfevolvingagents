import { promises as fs } from "node:fs";
import path from "node:path";
import { NextResponse } from "next/server";

type JsonObj = Record<string, unknown>;

function defaultStatus() {
  return {
    phase: "idle",
    reason: "No autotune status file found yet.",
    new_trace_count: 0,
    pending_trace_count: 0,
    variants: [],
    variant_runs: [],
    winner: null,
    promoted: null,
  };
}

async function readJson(filePath: string): Promise<JsonObj | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as JsonObj;
  } catch {
    return null;
  }
}

async function latestRunDir(runsRoot: string): Promise<string | null> {
  try {
    const entries = await fs.readdir(runsRoot, { withFileTypes: true });
    const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name).sort().reverse();
    if (dirs.length === 0) return null;
    return path.join(runsRoot, dirs[0]);
  } catch {
    return null;
  }
}

export async function GET() {
  const cwd = process.cwd();
  const statusPath = process.env.AUTOTUNE_STATUS_FILE ?? path.join(cwd, "artifacts/autotune/dashboard_status.json");
  const runsRoot = process.env.AUTOTUNE_RUNS_DIR ?? path.join(cwd, "artifacts/autotune/runs");

  const status = (await readJson(statusPath)) ?? defaultStatus();
  const runDir = (status.run_dir as string | undefined) ?? (await latestRunDir(runsRoot));

  if (!runDir) {
    return NextResponse.json({ ...status, server_time: new Date().toISOString() });
  }

  const [traces, findings, decision] = await Promise.all([
    readJson(path.join(runDir, "source_traces.json")),
    readJson(path.join(runDir, "findings_and_variants.json")),
    readJson(path.join(runDir, "promotion_decision.json")),
  ]);

  const merged: JsonObj = {
    ...status,
    run_dir: runDir,
    server_time: new Date().toISOString(),
  };

  if (traces && !("new_trace_count" in merged)) {
    const list = Array.isArray(traces) ? traces : [];
    merged.new_trace_count = list.length;
  }
  if (findings && (!Array.isArray(merged.variants) || merged.variants.length === 0)) {
    merged.variants = Array.isArray(findings.variants) ? findings.variants : [];
  }
  if (findings && (!Array.isArray(merged.findings) || merged.findings.length === 0)) {
    merged.findings = Array.isArray(findings.findings) ? findings.findings : [];
  }
  if (decision) {
    if (!Array.isArray(merged.variant_runs) || merged.variant_runs.length === 0) {
      merged.variant_runs = Array.isArray(decision.variant_runs) ? decision.variant_runs : [];
    }
    if (!("winner" in merged) || merged.winner == null) {
      merged.winner = decision.winner ?? null;
    }
    if (!("promoted" in merged) || merged.promoted == null) {
      merged.promoted = decision.promoted ?? null;
    }
    if (!("reason" in merged) || typeof merged.reason !== "string") {
      merged.reason = typeof decision.reason === "string" ? decision.reason : merged.reason;
    }
  }

  return NextResponse.json(merged);
}
