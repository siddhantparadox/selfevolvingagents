#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent_eval.autotune_service import _fetch_new_root_traces, _load_state


def _first_user_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and str(item.get("role", "")).lower() == "user":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    if isinstance(value, dict):
        sim = value.get("simulated_user")
        if isinstance(sim, dict):
            text = sim.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _needs_emergency(text: str) -> bool:
    t = text.lower()
    return any(
        k in t
        for k in [
            "flood",
            "fire",
            "underwater",
            "not breathing",
            "bleeding",
            "crash",
            "shot",
            "stranded",
            "trapped",
            "evacuate",
            "emergency",
        ]
    )


def _row_from_trace(idx: int, trace: Any) -> dict[str, Any] | None:
    user_text = _first_user_text(trace.input)
    if not user_text and isinstance(trace.metadata, dict):
        raw = trace.metadata.get("weather_agent.full_transcript_text")
        if isinstance(raw, str):
            for line in raw.splitlines():
                if "User:" in line:
                    user_text = line.split("User:", 1)[1].strip()
                    break
    if not user_text:
        return None

    emergency = _needs_emergency(user_text)
    return {
        "input": {
            "simulated_user": {
                "text": user_text,
                "language": "english",
                "goal": "get immediate safety guidance and next actions",
                "emotional_state": "anxious",
                "attitude": "urgent",
                "tone": "worried",
                "cooperativeness": "high",
                "verbosity": "medium",
                "patience": "low",
            },
            "needs_emergency": emergency,
        },
        "expected": "english",
        "metadata": {
            "case_id": f"trace-{idx:03d}",
            "scenario": "project_logs_trace_case",
            "source_root_span_id": trace.root_span_id,
            "source_created": trace.created,
            "source_span_name": trace.metadata.get("_source_span_name") if isinstance(trace.metadata, dict) else None,
            "needs_emergency": emergency,
        },
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate train/test dataset from new Braintrust traces since last cycle")
    parser.add_argument("--project", required=True)
    parser.add_argument("--source-experiment", required=True)
    parser.add_argument("--state-file", default="artifacts/autotune/state.json")
    parser.add_argument("--from-json", default=None, help="Optional local JSON file of raw Braintrust rows")
    parser.add_argument("--train-out", default="datasets/dataset_train_from_traces.jsonl")
    parser.add_argument("--test-out", default="datasets/dataset_test_from_traces.jsonl")
    parser.add_argument("--train-ratio", type=float, default=0.75)
    args = parser.parse_args()

    load_dotenv()
    state = _load_state(Path(args.state_file))
    since_iso = state.get("last_cycle_started_at")

    if args.from_json:
        raw_rows = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        # Reuse production parser path by monkey-patching a tiny in-memory fetch shape.
        # This keeps behavior aligned with live Braintrust parsing logic.
        class _MemExp:
            def __init__(self, rows: list[dict[str, Any]]) -> None:
                self._rows = rows

            def fetch(self):
                return self._rows

        import agent_eval.autotune_service as autosvc

        original_init = autosvc.braintrust.init

        def _fake_init(project: str, experiment: str, open: bool = True):  # type: ignore[override]
            return _MemExp(raw_rows)

        autosvc.braintrust.init = _fake_init  # type: ignore[assignment]
        try:
            traces = _fetch_new_root_traces(
                project_name=args.project,
                source_experiment=args.source_experiment,
                since_iso=since_iso,
                already_seen=set(),
            )
        finally:
            autosvc.braintrust.init = original_init  # type: ignore[assignment]
    else:
        traces = _fetch_new_root_traces(
            project_name=args.project,
            source_experiment=args.source_experiment,
            since_iso=since_iso,
            already_seen=set(),
        )

    rows: list[dict[str, Any]] = []
    for i, t in enumerate(traces, start=1):
        row = _row_from_trace(i, t)
        if row is not None:
            rows.append(row)

    if not rows:
        print("No new non-empty traces found since last cycle.")
        return

    train_count = max(1, min(len(rows) - 1, int(len(rows) * args.train_ratio))) if len(rows) > 1 else len(rows)
    train_rows = rows[:train_count]
    test_rows = rows[train_count:]
    for r in train_rows:
        r["metadata"]["split"] = "train"
    for r in test_rows:
        r["metadata"]["split"] = "test"

    _write_jsonl(Path(args.train_out), train_rows)
    _write_jsonl(Path(args.test_out), test_rows)
    print(f"since={since_iso}")
    print(f"new_traces={len(traces)} dataset_rows={len(rows)}")
    print(f"wrote train={len(train_rows)} -> {args.train_out}")
    print(f"wrote test={len(test_rows)} -> {args.test_out}")


if __name__ == "__main__":
    main()
