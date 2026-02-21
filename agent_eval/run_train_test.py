import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Any

import braintrust
from dotenv import load_dotenv

from agent_eval.run import _load_prompt_variants


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        v = value.get("score")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _summarize_experiment(project: str, experiment_name: str) -> dict[str, Any]:
    exp = braintrust.init(project=project, experiment=experiment_name, open=True)
    rows = list(exp.fetch())
    metric_values: dict[str, list[float]] = defaultdict(list)
    task_roots: set[str] = set()

    for row in rows:
        root = row.get("root_span_id") or row.get("span_id")
        if not isinstance(root, str):
            continue
        span_type = (row.get("span_attributes") or {}).get("type")
        if span_type == "task":
            task_roots.add(root)
            continue
        if span_type != "score":
            continue
        for metric, raw in (row.get("scores") or {}).items():
            val = _to_number(raw)
            if val is not None:
                metric_values[metric].append(val)

    return {
        "experiment": experiment_name,
        "case_count": len(task_roots),
        "metric_averages": {
            metric: round(mean(values), 4)
            for metric, values in sorted(metric_values.items())
            if values
        },
    }


def _build_run_cmd(
    *,
    jsonl: str,
    experiment_name: str,
    eval_name: str,
    turn_limit: int,
    llm: str | None,
    reasoning_effort: str | None,
    temperature: float | None,
    max_tokens: int | None,
    output_mode: str,
    prompts: list[str] | None,
    prompt_file: str | None,
    evaluators: list[str] | None,
    no_exact_match: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "agent_eval.run",
        "--jsonl",
        jsonl,
        "--eval-name",
        eval_name,
        "--experiment-name",
        experiment_name,
        "--turn-limit",
        str(turn_limit),
        "--output-mode",
        output_mode,
    ]
    if llm:
        cmd.extend(["--llm", llm])
    if reasoning_effort:
        cmd.extend(["--reasoning-effort", reasoning_effort])
    if temperature is not None:
        cmd.extend(["--temperature", str(temperature)])
    if max_tokens is not None:
        cmd.extend(["--max-tokens", str(max_tokens)])
    if prompt_file:
        cmd.extend(["--prompt-file", prompt_file])
    if prompts:
        for p in prompts:
            cmd.extend(["--prompt", p])
    if evaluators:
        for spec in evaluators:
            cmd.extend(["--evaluator", spec])
    if no_exact_match:
        cmd.append("--no-exact-match")
    return cmd


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run train/test JSONL experiments and print Braintrust score summaries for both."
    )
    parser.add_argument("--project", required=True, help="Braintrust project containing experiments")
    parser.add_argument("--eval-name", default="ElevenLabs Dataset Agent Eval")
    parser.add_argument("--train-jsonl", default="datasets/dataset_train.jsonl")
    parser.add_argument("--test-jsonl", default="datasets/dataset_test.jsonl")
    parser.add_argument(
        "--experiment-prefix",
        default=f"dataset-train-test-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
    )
    parser.add_argument("--turn-limit", type=int, default=20)
    parser.add_argument("--llm", default=None)
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default=None,
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument(
        "--output-mode",
        choices=["language", "raw", "structured"],
        default="structured",
    )
    parser.add_argument("--prompt", action="append", help="Repeat for multiple prompt variants")
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument(
        "--evaluator",
        action="append",
        help="Custom evaluator in module:function format (repeatable)",
    )
    parser.add_argument("--no-exact-match", action="store_true")
    parser.add_argument("--out-json", default=None, help="Optional path to write combined summary JSON")
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("BRAINTRUST_API_KEY"):
        raise ValueError("BRAINTRUST_API_KEY is required")

    variants = _load_prompt_variants(args.prompt, args.prompt_file)
    variant_names = [name for name, _ in variants]

    run_specs = [
        ("train", args.train_jsonl, f"{args.experiment_prefix}-train"),
        ("test", args.test_jsonl, f"{args.experiment_prefix}-test"),
    ]

    for split, jsonl, exp_base in run_specs:
        cmd = _build_run_cmd(
            jsonl=jsonl,
            experiment_name=exp_base,
            eval_name=args.eval_name,
            turn_limit=args.turn_limit,
            llm=args.llm,
            reasoning_effort=args.reasoning_effort,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            output_mode=args.output_mode,
            prompts=args.prompt,
            prompt_file=args.prompt_file,
            evaluators=args.evaluator,
            no_exact_match=args.no_exact_match,
        )
        print(f"[run-train-test] running {split}: {' '.join(cmd)}")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout)
        if proc.returncode != 0:
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            raise SystemExit(proc.returncode)

    summary: dict[str, Any] = {"project": args.project, "experiment_prefix": args.experiment_prefix, "splits": {}}
    for split, _, exp_base in run_specs:
        split_results: list[dict[str, Any]] = []
        for variant_name in variant_names:
            exp_name = f"{exp_base}-{variant_name}"
            split_results.append(_summarize_experiment(args.project, exp_name))
        summary["splits"][split] = split_results

    print("[run-train-test] score summary")
    print(json.dumps(summary, indent=2))

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"[run-train-test] wrote {args.out_json}")


if __name__ == "__main__":
    main()
