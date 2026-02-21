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


def _json_if_possible(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return value
    try:
        return json.loads(text)
    except Exception:
        return value


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


def _write_dashboard_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = dict(payload)
    safe_payload["updated_at"] = _utcnow_iso()
    path.write_text(json.dumps(safe_payload, indent=2), encoding="utf-8")


def _row_payload_score(row: dict[str, Any]) -> int:
    score = 0
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

    if row.get("input") not in (None, "", [], {}):
        score += 5
    if row.get("output") not in (None, "", [], {}):
        score += 5

    for key in [
        "input.value",
        "output.value",
        "gen_ai.input.messages",
        "weather_agent.full_transcript",
        "weather_agent.full_transcript_text",
        "full_transcript",
        "full_transcript_text",
    ]:
        if metadata.get(key):
            score += 2

    span_name = str((row.get("span_attributes") or {}).get("name", "")).lower()
    if "weather_agent" in span_name:
        score += 2
    return score


def _looks_like_chat_messages(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if isinstance(role, str) and isinstance(content, str):
            return True
    return False


def _has_conversation_payload(row: dict[str, Any], input_value: Any, output_value: Any) -> bool:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    span_name = str((row.get("span_attributes") or {}).get("name", "")).lower()

    # Strong signals from known logging fields.
    for key in [
        "gen_ai.input.messages",
        "weather_agent.full_transcript",
        "weather_agent.full_transcript_text",
        "full_transcript",
        "full_transcript_text",
    ]:
        if metadata.get(key):
            return True

    # Typical conversational message arrays.
    if _looks_like_chat_messages(input_value) or _looks_like_chat_messages(output_value):
        return True

    # Structured tool payloads that include transcript context.
    if isinstance(input_value, dict) and (
        "full_transcript" in input_value or "full_transcript_text" in input_value
    ):
        return True
    if isinstance(output_value, dict) and (
        "full_transcript" in output_value or "full_transcript_text" in output_value
    ):
        return True

    # Weather agent spans are usually relevant even with sparse fields.
    if "weather_agent" in span_name:
        return True

    return False


def _extract_row_payload(row: dict[str, Any]) -> tuple[Any, Any, dict[str, Any]]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    input_value = row.get("input")
    output_value = row.get("output")

    if input_value in (None, "", [], {}):
        for key in [
            "input.value",
            "gen_ai.input.messages",
            "weather_agent.full_transcript",
            "full_transcript",
            "full_transcript_text",
        ]:
            if metadata.get(key):
                input_value = _json_if_possible(metadata.get(key))
                break

    if output_value in (None, "", [], {}):
        for key in [
            "output.value",
            "weather_agent.full_transcript",
            "weather_agent.full_transcript_text",
            "full_transcript",
            "full_transcript_text",
        ]:
            if metadata.get(key):
                output_value = _json_if_possible(metadata.get(key))
                break

    out_meta = dict(metadata)
    out_meta["_source_span_id"] = row.get("span_id")
    out_meta["_source_span_name"] = (row.get("span_attributes") or {}).get("name")
    out_meta["_source_span_type"] = (row.get("span_attributes") or {}).get("type")
    return input_value, output_value, out_meta


def _fetch_new_root_traces(
    project_name: str,
    source_experiment: str,
    since_iso: str | None,
    already_seen: set[str],
) -> list[TraceRecord]:
    exp = braintrust.init(project=project_name, experiment=source_experiment, open=True)
    rows = list(exp.fetch())
    return _rows_to_trace_records(rows=rows, since_iso=since_iso, already_seen=already_seen)


def _rows_to_trace_records(
    rows: list[dict[str, Any]],
    since_iso: str | None,
    already_seen: set[str],
) -> list[TraceRecord]:

    since_dt = _parse_created(since_iso) if since_iso else None
    by_root: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        root_id = row.get("root_span_id") or row.get("span_id")
        if isinstance(root_id, str):
            by_root.setdefault(root_id, []).append(row)

    traces: list[TraceRecord] = []
    for root_id, grouped in by_root.items():
        if root_id in already_seen:
            continue

        created_values = [r.get("created") for r in grouped if isinstance(r.get("created"), str)]
        if not created_values:
            continue
        created = min(created_values)
        created_dt = _parse_created(created)
        if since_dt and created_dt <= since_dt:
            continue

        ranked = sorted(grouped, key=_row_payload_score, reverse=True)
        best = ranked[0]
        input_value, output_value, metadata = _extract_row_payload(best)

        if input_value in (None, "", [], {}) and output_value in (None, "", [], {}):
            continue
        if not _has_conversation_payload(best, input_value, output_value):
            continue

        traces.append(
            TraceRecord(
                created=created,
                root_span_id=root_id,
                input=input_value,
                output=output_value,
                metadata=metadata,
            )
        )

    traces.sort(key=lambda t: t.created)
    return traces


def _fetch_new_project_logs_traces(
    project_name: str,
    project_id: str | None,
    since_iso: str | None,
    already_seen: set[str],
    max_rows: int = 2000,
) -> list[TraceRecord]:
    logger = braintrust.init_logger(project=project_name)
    _ = logger.project.id
    state = logger.logging_state
    pid = project_id or logger.project.id

    rows: list[dict[str, Any]] = []
    cursor = None
    while True:
        limit = min(1000, max_rows - len(rows))
        if limit <= 0:
            break
        body = {
            "query": {
                "select": [{"op": "star"}],
                "from": {
                    "op": "function",
                    "name": {"op": "ident", "name": ["project_logs"]},
                    "args": [{"op": "literal", "value": pid}],
                },
                "limit": limit,
                **({"cursor": cursor} if cursor else {}),
            },
            "use_columnstore": False,
            "brainstore_realtime": True,
            "query_source": "autotune_project_logs_fetch",
        }
        resp = state.api_conn().post("btql", json=body, headers={"Accept-Encoding": "gzip"})
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data") if isinstance(payload.get("data"), list) else []
        rows.extend([r for r in data if isinstance(r, dict)])
        cursor = payload.get("cursor")
        if not cursor:
            break

    return _rows_to_trace_records(rows=rows, since_iso=since_iso, already_seen=already_seen)


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
    turns_calm = metrics.get("judge_turns_to_calm_state", 0.0)
    turns_emergency = metrics.get("judge_turns_to_emergency_services", 0.0)
    return (calm, emergency, turns_calm, turns_emergency)


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
    project_id = os.getenv("BRAINTRUST_PROJECT_ID")
    dataset_project = args.dataset_project or os.getenv("AUTOTUNE_DATASET_PROJECT", project)
    dataset_name = args.dataset_name or os.getenv("AUTOTUNE_DATASET_NAME")
    train_dataset_name = args.train_dataset_name or os.getenv("AUTOTUNE_TRAIN_DATASET_NAME")
    test_dataset_name = args.test_dataset_name or os.getenv("AUTOTUNE_TEST_DATASET_NAME")
    dataset_version = args.dataset_version or os.getenv("AUTOTUNE_DATASET_VERSION")
    judge_model = args.judge_model or os.getenv("AUTOTUNE_JUDGE_MODEL", "gemini-3-pro-preview")
    agent_llm = args.agent_llm or os.getenv("AUTOTUNE_AGENT_LLM", "gemini-3-pro-preview")
    reasoning_effort = args.reasoning_effort or os.getenv("AUTOTUNE_AGENT_REASONING_EFFORT", "low")
    poll_seconds = args.poll_seconds
    update_live = args.update_live_prompt

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not project:
        raise ValueError("AUTOTUNE_PROJECT (or --project) is required")
    dataset_splits: list[tuple[str, str]] = []
    if train_dataset_name or test_dataset_name:
        if train_dataset_name:
            dataset_splits.append(("train", train_dataset_name))
        if test_dataset_name:
            dataset_splits.append(("test", test_dataset_name))
    elif dataset_name:
        dataset_splits.append(("all", dataset_name))
    else:
        raise ValueError(
            "Provide either AUTOTUNE_DATASET_NAME (or --dataset-name), "
            "or both split datasets via AUTOTUNE_TRAIN_DATASET_NAME / AUTOTUNE_TEST_DATASET_NAME."
        )
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY is required")

    state_path = Path(args.state_file)
    artifacts_root = Path(args.artifacts_dir)
    status_path = Path(args.status_file)
    state = _load_state(state_path)

    pending: list[TraceRecord] = []
    pending_seen: set[str] = set(state.get("last_processed_root_ids", []))

    source_label = source_experiment if source_experiment else "__all_project_logs__"
    print(f"[autotune] start poll={poll_seconds}s project={project} source={source_label}")
    _write_dashboard_status(
        status_path,
        {
            "phase": "starting",
            "project": project,
            "source_experiment": source_experiment,
            "dataset_project": dataset_project,
            "dataset_name": dataset_name,
            "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
            "last_cycle_started_at": state.get("last_cycle_started_at"),
            "pending_trace_count": len(pending),
            "new_trace_count": 0,
            "variants": [],
            "variant_runs": [],
            "winner": None,
            "promoted": None,
            "reason": "service starting",
            "last_run_prefix": state.get("last_run_prefix"),
        },
    )

    while True:
        try:
            if source_experiment:
                new_traces = _fetch_new_root_traces(
                    project_name=project,
                    source_experiment=source_experiment,
                    since_iso=state.get("last_cycle_started_at"),
                    already_seen=pending_seen,
                )
            else:
                new_traces = _fetch_new_project_logs_traces(
                    project_name=project,
                    project_id=project_id,
                    since_iso=state.get("last_cycle_started_at"),
                    already_seen=pending_seen,
                )
            for t in new_traces:
                pending.append(t)
                pending_seen.add(t.root_span_id)

            _write_dashboard_status(
                status_path,
                {
                    "phase": "waiting_for_traces",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": len(new_traces),
                    "variants": [],
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": "waiting for new traces",
                    "last_run_prefix": state.get("last_run_prefix"),
                },
            )

            if not pending:
                time.sleep(poll_seconds)
                continue

            cycle_start = _utcnow_iso()
            run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            run_prefix = f"autotune-{run_stamp}"
            run_dir = artifacts_root / run_stamp
            run_dir.mkdir(parents=True, exist_ok=True)
            _write_dashboard_status(
                status_path,
                {
                    "phase": "building_trace_snapshot",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": len(new_traces),
                    "variants": [],
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": "new traces loaded for strategy generation",
                    "last_run_prefix": run_prefix,
                    "run_dir": str(run_dir),
                },
            )

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
            _write_dashboard_status(
                status_path,
                {
                    "phase": "strategies_generated",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": len(new_traces),
                    "variants": generated.get("variants", []),
                    "findings": generated.get("findings", []),
                    "why_it_failed": generated.get("why_it_failed", []),
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": "generated two prompt variants",
                    "last_run_prefix": run_prefix,
                    "run_dir": str(run_dir),
                },
            )

            prompts = [v["prompt"] for v in generated.get("variants", [])[:2]]
            print(f"[autotune] running eval {run_prefix} with {len(prompts)} variants")
            _write_dashboard_status(
                status_path,
                {
                    "phase": "evaluating_variants",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": len(new_traces),
                    "variants": generated.get("variants", []),
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": "running Braintrust eval for both strategies",
                    "last_run_prefix": run_prefix,
                    "run_dir": str(run_dir),
                },
            )

            all_variant_runs: list[dict[str, Any]] = []
            eval_logs: list[dict[str, Any]] = []
            eval_failed = False
            eval_failure_reason = ""

            for split_name, split_dataset_name in dataset_splits:
                split_prefix = f"{run_prefix}-{split_name}" if split_name != "all" else run_prefix
                cmd = _build_eval_command(
                    run_prefix=split_prefix,
                    variant_prompts=prompts,
                    dataset_project=dataset_project,
                    dataset_name=split_dataset_name,
                    dataset_version=dataset_version,
                    agent_llm=agent_llm,
                    reasoning_effort=reasoning_effort,
                )
                eval_logs.append(
                    {
                        "split": split_name,
                        "dataset_name": split_dataset_name,
                        "command": " ".join(cmd),
                    }
                )
                proc = subprocess.run(cmd, capture_output=True, text=True)
                (run_dir / f"eval_stdout_{split_name}.log").write_text(proc.stdout or "", encoding="utf-8")
                (run_dir / f"eval_stderr_{split_name}.log").write_text(proc.stderr or "", encoding="utf-8")

                if proc.returncode != 0:
                    eval_failed = True
                    eval_failure_reason = f"eval failed split={split_name} rc={proc.returncode}"
                    break

                split_variant_runs = [
                    {
                        "split": split_name,
                        "dataset_name": split_dataset_name,
                        "name": "cli-1",
                        "experiment": f"{split_prefix}-cli-1",
                        "prompt": prompts[0] if len(prompts) > 0 else "",
                    },
                    {
                        "split": split_name,
                        "dataset_name": split_dataset_name,
                        "name": "cli-2",
                        "experiment": f"{split_prefix}-cli-2",
                        "prompt": prompts[1] if len(prompts) > 1 else "",
                    },
                ]
                for vr in split_variant_runs:
                    vr["metrics"] = _summarize_experiment(project=dataset_project, experiment_name=vr["experiment"])
                all_variant_runs.extend(split_variant_runs)

            (run_dir / "eval_commands.json").write_text(json.dumps(eval_logs, indent=2), encoding="utf-8")
            if eval_failed:
                print(f"[autotune] {eval_failure_reason}")
                _write_dashboard_status(
                    status_path,
                    {
                        "phase": "error",
                        "project": project,
                        "source_experiment": source_experiment,
                        "dataset_project": dataset_project,
                        "dataset_name": dataset_name,
                        "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                        "last_cycle_started_at": state.get("last_cycle_started_at"),
                        "pending_trace_count": len(pending),
                        "new_trace_count": len(new_traces),
                        "variants": generated.get("variants", []),
                        "variant_runs": all_variant_runs,
                        "winner": None,
                        "promoted": None,
                        "reason": eval_failure_reason,
                        "last_run_prefix": run_prefix,
                        "run_dir": str(run_dir),
                    },
                )
                state["last_cycle_started_at"] = cycle_start
                _save_state(state_path, state)
                pending = []
                time.sleep(poll_seconds)
                continue

            # Prefer winner selection on test split when present.
            winner_pool = [vr for vr in all_variant_runs if vr.get("split") == "test"]
            if not winner_pool:
                winner_pool = all_variant_runs
            winner = _pick_winner(winner_pool)

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
                "variant_runs": all_variant_runs,
                "baseline_metrics_before": baseline_metrics,
            }
            (run_dir / "promotion_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
            _write_dashboard_status(
                status_path,
                {
                    "phase": "cycle_complete",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": cycle_start,
                    "pending_trace_count": 0,
                    "new_trace_count": len(new_traces),
                    "variants": generated.get("variants", []),
                    "findings": generated.get("findings", []),
                    "why_it_failed": generated.get("why_it_failed", []),
                    "variant_runs": all_variant_runs,
                    "winner": winner,
                    "promoted": promoted,
                    "reason": reason,
                    "last_run_prefix": run_prefix,
                    "run_dir": str(run_dir),
                },
            )

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
            _write_dashboard_status(
                status_path,
                {
                    "phase": "stopped",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": 0,
                    "variants": [],
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": "service stopped",
                    "last_run_prefix": state.get("last_run_prefix"),
                },
            )
            return
        except Exception as exc:
            print(f"[autotune] loop error: {exc}")
            _write_dashboard_status(
                status_path,
                {
                    "phase": "error",
                    "project": project,
                    "source_experiment": source_experiment,
                    "dataset_project": dataset_project,
                    "dataset_name": dataset_name,
                    "dataset_splits": [{"split": s, "dataset_name": n} for s, n in dataset_splits],
                    "last_cycle_started_at": state.get("last_cycle_started_at"),
                    "pending_trace_count": len(pending),
                    "new_trace_count": 0,
                    "variants": [],
                    "variant_runs": [],
                    "winner": None,
                    "promoted": None,
                    "reason": f"loop error: {exc}",
                    "last_run_prefix": state.get("last_run_prefix"),
                },
            )

        time.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polling autotune service for Braintrust traces -> prompt variants -> eval")
    parser.add_argument("--project", default=None, help="Braintrust project to monitor")
    parser.add_argument(
        "--source-experiment",
        default=None,
        help="Optional source experiment. If omitted, monitor all project logs across experiments.",
    )
    parser.add_argument("--dataset-project", default=None, help="Braintrust project containing evaluation dataset")
    parser.add_argument("--dataset-name", default=None, help="Braintrust dataset name for eval runs")
    parser.add_argument("--train-dataset-name", default=None, help="Braintrust train dataset name for eval runs")
    parser.add_argument("--test-dataset-name", default=None, help="Braintrust test dataset name for eval runs")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--agent-llm", default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--state-file", default="artifacts/autotune/state.json")
    parser.add_argument("--artifacts-dir", default="artifacts/autotune/runs")
    parser.add_argument("--status-file", default="artifacts/autotune/dashboard_status.json")
    parser.add_argument("--update-live-prompt", action="store_true", help="If set, updates live ElevenLabs prompt when winner improves baseline")
    args = parser.parse_args()
    run_service(args)


if __name__ == "__main__":
    main()
