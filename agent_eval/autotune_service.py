import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import braintrust
import requests
from dotenv import load_dotenv
from elevenlabs import ElevenLabs


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_created(ts: str) -> datetime:
    # Braintrust often returns e.g. 2026-02-21T20:50:17.624Z
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _env_any(*names: str) -> str | None:
    for n in names:
        v = os.getenv(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


@dataclass
class TraceRecord:
    created: str
    root_span_id: str
    input: Any
    output: Any
    metadata: dict[str, Any]


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "last_cycle_started_at": None,
            "baseline_metrics": None,
            "last_processed_root_ids": [],
            "last_run_prefix": None,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_cycle_started_at": None,
            "baseline_metrics": None,
            "last_processed_root_ids": [],
            "last_run_prefix": None,
        }


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _fetch_new_root_traces(
    project_name: str,
    source_experiment: str,
    since_iso: str | None,
    already_seen: set[str],
) -> list[TraceRecord]:
    exp = braintrust.init(project=project_name, experiment=source_experiment, open=True)
    rows = list(exp.fetch())

    since_dt = _parse_created(since_iso) if since_iso else None
    traces: list[TraceRecord] = []
    for row in rows:
        if row.get("is_root") is not True:
            continue
        root_id = row.get("root_span_id") or row.get("span_id")
        created = row.get("created")
        if not isinstance(root_id, str) or not isinstance(created, str):
            continue
        if root_id in already_seen:
            continue
        created_dt = _parse_created(created)
        if since_dt and created_dt <= since_dt:
            continue
        traces.append(
            TraceRecord(
                created=created,
                root_span_id=root_id,
                input=row.get("input"),
                output=row.get("output"),
                metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
            )
        )

    traces.sort(key=lambda t: t.created)
    return traces


def _call_gemini(prompt: str, model: str, api_key: str, retries: int = 4) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60,
            )
            if resp.status_code == 429 and attempt < retries:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            body = resp.json()
            candidates = body.get("candidates") or []
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            return "\n".join(texts).strip()
        except Exception:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            return ""
    return ""


def _extract_json_obj(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        parts = t.split("\n", 1)
        if len(parts) == 2:
            t = parts[1]
    start = t.find("{")
    end = t.rfind("}")
    if start >= 0 and end > start:
        t = t[start : end + 1]
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _generate_findings_and_variants(
    traces: list[TraceRecord],
    judge_model: str,
    gemini_api_key: str,
) -> dict[str, Any]:
    compact = []
    for t in traces[-30:]:
        compact.append(
            {
                "root_span_id": t.root_span_id,
                "created": t.created,
                "input": t.input,
                "output": t.output,
                "metadata": t.metadata,
            }
        )

    prompt = f"""
You are optimizing a crisis-response voice agent.
Given recent traces, extract findings and propose exactly 2 new prompt variants.

Return strict JSON with this schema:
{{
  "findings": ["..."],
  "why_it_failed": ["..."],
  "variants": [
    {{"name":"variant_1","prompt":"..."}},
    {{"name":"variant_2","prompt":"..."}}
  ]
}}

Rules:
- Focus on emergency escalation timing and user de-escalation.
- Prompts must be directly usable as system instructions.
- Exactly 2 variants.

Recent traces:
{json.dumps(compact)}
""".strip()

    text = _call_gemini(prompt, model=judge_model, api_key=gemini_api_key)
    obj = _extract_json_obj(text)
    variants = obj.get("variants") if isinstance(obj.get("variants"), list) else []
    cleaned = []
    for i, v in enumerate(variants[:2], start=1):
        if not isinstance(v, dict):
            continue
        p = v.get("prompt")
        if isinstance(p, str) and p.strip():
            cleaned.append({"name": v.get("name", f"variant_{i}"), "prompt": p.strip()})

    if len(cleaned) < 2:
        # Safe fallback prompts
        cleaned = [
            {
                "name": "variant_1",
                "prompt": "You are a calm emergency responder. In immediate danger cases, first validate emotions, then instruct contacting emergency services, then provide exactly three concrete safety steps.",
            },
            {
                "name": "variant_2",
                "prompt": "You are a high-urgency crisis assistant. If flood/fire/trapped risk appears, immediately escalate to emergency services and provide concise step-by-step evacuation/safety actions before follow-up questions.",
            },
        ]

    return {
        "findings": obj.get("findings", []),
        "why_it_failed": obj.get("why_it_failed", []),
        "variants": cleaned,
    }


def _build_eval_command(
    run_prefix: str,
    variant_prompts: list[str],
    dataset_project: str,
    dataset_name: str,
    dataset_version: str | None,
    agent_llm: str,
    reasoning_effort: str,
) -> list[str]:
    cmd = [
        "elevenlabs-braintrust-eval",
        "--project",
        dataset_project,
        "--dataset-name",
        dataset_name,
        "--experiment-name",
        run_prefix,
        "--llm",
        agent_llm,
        "--reasoning-effort",
        reasoning_effort,
        "--turn-limit",
        "20",
        "--output-mode",
        "structured",
        "--no-exact-match",
        "--evaluator",
        "agent_eval.custom_metrics:judge_calmer_end_state_binary",
        "--evaluator",
        "agent_eval.custom_metrics:judge_emergency_services_when_needed_binary",
        "--evaluator",
        "agent_eval.custom_metrics:judge_turns_to_calm_state",
        "--evaluator",
        "agent_eval.custom_metrics:judge_turns_to_emergency_services",
    ]
    if dataset_version:
        cmd.extend(["--dataset-version", dataset_version])
    for p in variant_prompts:
        cmd.extend(["--prompt", p])
    return cmd


def _summarize_experiment(project: str, experiment_name: str) -> dict[str, float]:
    exp = braintrust.init(project=project, experiment=experiment_name, open=True)
    rows = list(exp.fetch())
    per_metric: dict[str, list[float]] = {}
    for row in rows:
        span_type = (row.get("span_attributes") or {}).get("type")
        if span_type != "score":
            continue
        for k, v in (row.get("scores") or {}).items():
            num = None
            if isinstance(v, bool):
                num = 1.0 if v else 0.0
            elif isinstance(v, (int, float)):
                num = float(v)
            elif isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
                num = float(v.get("score"))
            if num is None:
                continue
            per_metric.setdefault(k, []).append(num)
    summary: dict[str, float] = {}
    for k, vals in per_metric.items():
        if vals:
            summary[k] = sum(vals) / len(vals)
    return summary


def _score_tuple(metrics: dict[str, float]) -> tuple[float, float, float, float]:
    calm = metrics.get("judge_calmer_end_state_binary", 0.0)
    emergency = metrics.get("judge_emergency_services_when_needed_binary", 0.0)
    turns_calm = metrics.get("judge_turns_to_calm_state", -1.0)
    turns_emergency = metrics.get("judge_turns_to_emergency_services", -1.0)

    # Lower turns is better, -1 means not achieved (treat as worst = 999)
    t_c = turns_calm if turns_calm >= 0 else 999.0
    t_e = turns_emergency if turns_emergency >= 0 else 999.0
    return (calm, emergency, -t_c, -t_e)


def _pick_winner(variant_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    scored = []
    for m in variant_metrics:
        scored.append((
            _score_tuple(m["metrics"]),
            m,
        ))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _update_live_prompt_if_better(
    winner_prompt: str,
    winner_metrics: dict[str, float],
    baseline_metrics: dict[str, float] | None,
    update_live: bool,
) -> tuple[bool, str]:
    if baseline_metrics is None:
        improved = True
    else:
        improved = _score_tuple(winner_metrics) > _score_tuple(baseline_metrics)

    if not improved:
        return False, "winner did not improve baseline"
    if not update_live:
        return True, "improved; live update disabled"

    api_key = _env_any("ELEVENLABS_API_KEY", "ELLEVENLABS_API_KEY")
    agent_id = _env_any("ELEVENLABS_AGENT_ID", "ELLEVENLABS_AGENT_ID")
    if not api_key or not agent_id:
        return True, "improved; skipped live update (missing ElevenLabs credentials)"

    try:
        client = ElevenLabs(api_key=api_key)
        agent = client.conversational_ai.agents.get(agent_id=agent_id)
        payload = agent.model_dump() if hasattr(agent, "model_dump") else dict(agent)
        cc = payload.get("conversation_config") if isinstance(payload, dict) else None
        if not isinstance(cc, dict):
            return True, "improved; skipped live update (conversation_config missing)"
        agent_cfg = cc.get("agent") if isinstance(cc.get("agent"), dict) else {}
        prompt_cfg = agent_cfg.get("prompt") if isinstance(agent_cfg.get("prompt"), dict) else {}
        prompt_cfg["prompt"] = winner_prompt
        agent_cfg["prompt"] = prompt_cfg
        cc["agent"] = agent_cfg

        client.conversational_ai.agents.update(
            agent_id=agent_id,
            conversation_config=cc,
            version_description="autotune promotion",
        )
        return True, "improved; live prompt updated"
    except Exception as exc:
        return True, f"improved; live update failed: {exc}"


def run_service(args: argparse.Namespace) -> None:
    load_dotenv()

    project = args.project or os.getenv("AUTOTUNE_PROJECT")
    source_experiment = args.source_experiment or os.getenv("AUTOTUNE_SOURCE_EXPERIMENT")
    dataset_project = args.dataset_project or os.getenv("AUTOTUNE_DATASET_PROJECT", project)
    dataset_name = args.dataset_name or os.getenv("AUTOTUNE_DATASET_NAME")
    dataset_version = args.dataset_version or os.getenv("AUTOTUNE_DATASET_VERSION")
    judge_model = args.judge_model or os.getenv("AUTOTUNE_JUDGE_MODEL", "gemini-3-pro-preview")
    agent_llm = args.agent_llm or os.getenv("AUTOTUNE_AGENT_LLM", "gemini-3-pro-preview")
    reasoning_effort = args.reasoning_effort or os.getenv("AUTOTUNE_AGENT_REASONING_EFFORT", "low")
    poll_seconds = args.poll_seconds
    update_live = args.update_live_prompt

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not project:
        raise ValueError("AUTOTUNE_PROJECT (or --project) is required")
    if not source_experiment:
        raise ValueError("AUTOTUNE_SOURCE_EXPERIMENT (or --source-experiment) is required")
    if not dataset_name:
        raise ValueError("AUTOTUNE_DATASET_NAME (or --dataset-name) is required")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required")

    state_path = Path(args.state_file)
    artifacts_root = Path(args.artifacts_dir)
    state = _load_state(state_path)

    pending: list[TraceRecord] = []
    pending_seen: set[str] = set(state.get("last_processed_root_ids", []))

    print(f"[autotune] start poll={poll_seconds}s project={project} source_experiment={source_experiment}")

    while True:
        try:
            new_traces = _fetch_new_root_traces(
                project_name=project,
                source_experiment=source_experiment,
                since_iso=state.get("last_cycle_started_at"),
                already_seen=pending_seen,
            )
            for t in new_traces:
                pending.append(t)
                pending_seen.add(t.root_span_id)

            if not pending:
                time.sleep(poll_seconds)
                continue

            cycle_start = _utcnow_iso()
            run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            run_prefix = f"autotune-{run_stamp}"
            run_dir = artifacts_root / run_stamp
            run_dir.mkdir(parents=True, exist_ok=True)

            # Snapshot pending traces since last cycle started.
            trace_payload = [
                {
                    "created": t.created,
                    "root_span_id": t.root_span_id,
                    "input": t.input,
                    "output": t.output,
                    "metadata": t.metadata,
                }
                for t in pending
            ]
            (run_dir / "source_traces.json").write_text(json.dumps(trace_payload, indent=2), encoding="utf-8")

            generated = _generate_findings_and_variants(
                traces=pending,
                judge_model=judge_model,
                gemini_api_key=gemini_api_key,
            )
            (run_dir / "findings_and_variants.json").write_text(json.dumps(generated, indent=2), encoding="utf-8")

            prompts = [v["prompt"] for v in generated.get("variants", [])[:2]]
            cmd = _build_eval_command(
                run_prefix=run_prefix,
                variant_prompts=prompts,
                dataset_project=dataset_project,
                dataset_name=dataset_name,
                dataset_version=dataset_version,
                agent_llm=agent_llm,
                reasoning_effort=reasoning_effort,
            )
            (run_dir / "eval_command.txt").write_text(" ".join(cmd), encoding="utf-8")

            print(f"[autotune] running eval {run_prefix} with {len(prompts)} variants")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            (run_dir / "eval_stdout.log").write_text(proc.stdout or "", encoding="utf-8")
            (run_dir / "eval_stderr.log").write_text(proc.stderr or "", encoding="utf-8")
            if proc.returncode != 0:
                print(f"[autotune] eval failed rc={proc.returncode}")
                state["last_cycle_started_at"] = cycle_start
                _save_state(state_path, state)
                pending = []
                time.sleep(poll_seconds)
                continue

            # Current runner names prompt variants cli-1, cli-2
            variant_runs = [
                {"name": "cli-1", "experiment": f"{run_prefix}-cli-1", "prompt": prompts[0] if len(prompts) > 0 else ""},
                {"name": "cli-2", "experiment": f"{run_prefix}-cli-2", "prompt": prompts[1] if len(prompts) > 1 else ""},
            ]
            for vr in variant_runs:
                vr["metrics"] = _summarize_experiment(project=dataset_project, experiment_name=vr["experiment"])

            winner = _pick_winner(variant_runs)
            baseline_metrics = state.get("baseline_metrics") if isinstance(state.get("baseline_metrics"), dict) else None
            promoted, reason = _update_live_prompt_if_better(
                winner_prompt=winner.get("prompt", ""),
                winner_metrics=winner.get("metrics", {}),
                baseline_metrics=baseline_metrics,
                update_live=update_live,
            )

            decision = {
                "run_prefix": run_prefix,
                "promoted": promoted,
                "reason": reason,
                "winner": winner,
                "variant_runs": variant_runs,
                "baseline_metrics_before": baseline_metrics,
            }
            (run_dir / "promotion_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")

            if promoted:
                state["baseline_metrics"] = winner.get("metrics", {})

            state["last_cycle_started_at"] = cycle_start
            state["last_processed_root_ids"] = list(pending_seen)[-5000:]
            state["last_run_prefix"] = run_prefix
            _save_state(state_path, state)

            pending = []
            print(f"[autotune] cycle done promoted={promoted} reason={reason}")

        except KeyboardInterrupt:
            print("[autotune] stopping")
            return
        except Exception as exc:
            print(f"[autotune] loop error: {exc}")

        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polling autotune service for Braintrust traces -> prompt variants -> eval")
    parser.add_argument("--project", default=None, help="Braintrust project containing source experiment")
    parser.add_argument("--source-experiment", default=None, help="Source experiment to watch for new root traces")
    parser.add_argument("--dataset-project", default=None, help="Braintrust project containing evaluation dataset")
    parser.add_argument("--dataset-name", default=None, help="Braintrust dataset name for eval runs")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--agent-llm", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--state-file", default="artifacts/autotune/state.json")
    parser.add_argument("--artifacts-dir", default="artifacts/autotune/runs")
    parser.add_argument("--update-live-prompt", action="store_true", help="If set, updates live ElevenLabs prompt when winner improves baseline")
    args = parser.parse_args()
    run_service(args)


if __name__ == "__main__":
    main()
