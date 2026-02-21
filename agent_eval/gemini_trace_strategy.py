import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import braintrust
import requests
from dotenv import load_dotenv


@dataclass
class CaseResult:
    root_span_id: str
    input_text: str
    output_text: str
    turn_count: int | None
    metadata: dict[str, Any]
    scores: dict[str, float]


@dataclass
class CaseReview:
    case_id: str
    overall: float
    worked: list[str]
    failed: list[str]
    fix_snippet: str


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and isinstance(value.get("score"), (int, float)):
        return float(value["score"])
    return None


def _extract_input_text(input_value: Any) -> str:
    if isinstance(input_value, str):
        return input_value
    if isinstance(input_value, dict):
        sim = input_value.get("simulated_user")
        if isinstance(sim, dict) and isinstance(sim.get("text"), str):
            return sim["text"]
        if isinstance(input_value.get("text"), str):
            return input_value["text"]
    return str(input_value)


def _extract_output(output_value: Any) -> tuple[str, int | None]:
    if isinstance(output_value, dict):
        text = output_value.get("text")
        if not isinstance(text, str):
            text = json.dumps(output_value)
        turns = output_value.get("turn_count")
        if not isinstance(turns, int):
            turns = None
        return text, turns
    return str(output_value), None


def _case_id(case: CaseResult) -> str:
    cid = case.metadata.get("case_id")
    if isinstance(cid, str) and cid:
        return cid
    return case.root_span_id


def _fetch_cases(project: str, experiment: str) -> list[CaseResult]:
    exp = braintrust.init(project=project, experiment=experiment, open=True)
    rows = list(exp.fetch())

    task_rows: dict[str, dict[str, Any]] = {}
    score_rows: dict[str, dict[str, float]] = {}

    for row in rows:
        root = row.get("root_span_id") or row.get("span_id")
        if not isinstance(root, str):
            continue

        span_type = (row.get("span_attributes") or {}).get("type")
        if span_type == "task":
            task_rows[root] = row
        elif span_type == "score":
            slot = score_rows.setdefault(root, {})
            for metric, raw in (row.get("scores") or {}).items():
                num = _to_number(raw)
                if num is not None:
                    slot[metric] = num

    cases: list[CaseResult] = []
    for root, task in task_rows.items():
        output_text, turn_count = _extract_output(task.get("output"))
        cases.append(
            CaseResult(
                root_span_id=root,
                input_text=_extract_input_text(task.get("input")),
                output_text=output_text,
                turn_count=turn_count,
                metadata=task.get("metadata") if isinstance(task.get("metadata"), dict) else {},
                scores=score_rows.get(root, {}),
            )
        )
    return cases


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        parts = text.split("\n", 1)
        if len(parts) == 2:
            text = parts[1]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _call_gemini(prompt: str, api_key: str, model: str, retries: int = 4) -> tuple[str, str]:
    models = [model, "gemini-2.5-pro", "gemini-2.5-flash"]
    seen: set[str] = set()
    last_error: Exception | None = None

    for m in models:
        if m in seen:
            continue
        seen.add(m)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        for attempt in range(retries + 1):
            try:
                resp = requests.post(
                    url,
                    params={"key": api_key},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=60,
                )
                if resp.status_code == 429 and attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    raise ValueError(f"No candidates returned: {data}")
                parts = candidates[0].get("content", {}).get("parts", [])
                text_parts = [p.get("text", "") for p in parts if isinstance(p, dict)]
                return "\n".join(text_parts).strip(), m
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                break

    raise RuntimeError(f"All Gemini model attempts failed: {last_error}")


def _review_case(case: CaseResult, model: str, api_key: str) -> CaseReview:
    prompt = f"""
You are evaluating a crisis-response voice-agent transcript.
Return JSON only with this schema:
{{
  "overall": number,  // 0..1
  "worked": [string, string],
  "failed": [string, string],
  "fix_snippet": "string"
}}

Context:
- Input scenario: {case.input_text}
- Output transcript (truncated): {case.output_text[:2200]}
- turn_count: {case.turn_count}
- existing metric scores: {json.dumps(case.scores)}

Rules:
- Align with emergency-response quality: escalation, de-escalation, concrete safety steps, timing.
- "fix_snippet" must be a short instruction you can paste into prompt policy.
- Keep arrays concise (2-4 items each).
""".strip()

    text, _ = _call_gemini(prompt, api_key=api_key, model=model)
    obj = _extract_json(text)

    overall = float(obj.get("overall", 0.0))
    worked = [str(x) for x in obj.get("worked", [])][:4]
    failed = [str(x) for x in obj.get("failed", [])][:4]
    fix_snippet = str(obj.get("fix_snippet", "")).strip()

    return CaseReview(
        case_id=_case_id(case),
        overall=max(0.0, min(1.0, overall)),
        worked=worked,
        failed=failed,
        fix_snippet=fix_snippet,
    )


def _consensus_strategy(
    case_reviews: list[CaseReview],
    model: str,
    api_key: str,
) -> tuple[dict[str, Any], str]:
    review_payload = [
        {
            "case_id": r.case_id,
            "overall": r.overall,
            "worked": r.worked,
            "failed": r.failed,
            "fix_snippet": r.fix_snippet,
        }
        for r in case_reviews
    ]

    prompt = f"""
Given per-case review data for a crisis-response agent, produce a consensus next-round strategy.
Return JSON only with schema:
{{
  "consensus": "string",
  "why_worked": ["..."],
  "why_failed": ["..."],
  "next_prompt_variants": [
    {{"name":"variant_a","prompt":"..."}},
    {{"name":"variant_b","prompt":"..."}},
    {{"name":"variant_c","prompt":"..."}}
  ]
}}

Requirements:
- Exactly 3 prompt variants.
- Prompts must explicitly handle emergency escalation + de-escalation + concrete safety actions.
- Keep prompts practical for immediate eval rerun.

Per-case reviews:
{json.dumps(review_payload)}
""".strip()

    text, used_model = _call_gemini(prompt, api_key=api_key, model=model)
    return _extract_json(text), used_model


def _format_report(
    project: str,
    experiment: str,
    requested_model: str,
    used_model: str,
    cases: list[CaseResult],
    reviews: list[CaseReview],
    consensus: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Gemini Trace Strategy Report")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}")
    lines.append(f"Project: {project}")
    lines.append(f"Experiment: {experiment}")
    lines.append(f"Judge model requested: {requested_model}")
    lines.append(f"Judge model used: {used_model}")
    lines.append("")

    metric_avgs: dict[str, float] = {}
    for case in cases:
        for k, v in case.scores.items():
            metric_avgs.setdefault(k, 0.0)
            metric_avgs[k] += v
    if cases:
        for k in list(metric_avgs.keys()):
            metric_avgs[k] /= len(cases)

    lines.append("## Aggregate Metrics")
    for k, v in sorted(metric_avgs.items()):
        lines.append(f"- {k}: {v:.4f}")
    if cases:
        turns = [c.turn_count for c in cases if isinstance(c.turn_count, int)]
        if turns:
            lines.append(f"- avg_turn_count: {mean(turns):.2f}")
    lines.append("")

    lines.append("## Per-Case Reviews (Gemini)")
    for case, review in zip(cases, reviews):
        lines.append(f"- {review.case_id} | overall={review.overall:.3f} | turns={case.turn_count}")
        lines.append(f"  input: {case.input_text[:180].replace(chr(10), ' ')}")
        lines.append(f"  worked: {', '.join(review.worked) if review.worked else 'none'}")
        lines.append(f"  failed: {', '.join(review.failed) if review.failed else 'none'}")
        lines.append(f"  fix_snippet: {review.fix_snippet}")
    lines.append("")

    lines.append("## Consensus Strategy")
    lines.append(f"- consensus: {consensus.get('consensus', '')}")
    lines.append(f"- why_worked: {', '.join(consensus.get('why_worked', []))}")
    lines.append(f"- why_failed: {', '.join(consensus.get('why_failed', []))}")
    lines.append("")

    lines.append("## Next 3 Prompt Variants")
    for item in consensus.get("next_prompt_variants", []):
        name = item.get("name", "variant")
        prompt = item.get("prompt", "")
        lines.append(f"- {name}: {prompt}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini-based Braintrust trace evaluator + strategy generator")
    parser.add_argument("--project", required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--gemini-model", default="gemini-3-pro-preview")
    parser.add_argument("--max-cases", type=int, default=6, help="0 means all cases")
    parser.add_argument("--output", default=f"gemini_strategy_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.md")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required")

    cases = _fetch_cases(args.project, args.experiment)
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    if not cases:
        raise ValueError("No cases found")

    reviews: list[CaseReview] = []
    for case in cases:
        reviews.append(_review_case(case, model=args.gemini_model, api_key=api_key))

    consensus, used_model = _consensus_strategy(reviews, model=args.gemini_model, api_key=api_key)
    report = _format_report(
        project=args.project,
        experiment=args.experiment,
        requested_model=args.gemini_model,
        used_model=used_model,
        cases=cases,
        reviews=reviews,
        consensus=consensus,
    )

    path = Path(args.output)
    path.write_text(report, encoding="utf-8")
    print(f"Wrote report: {path}")


if __name__ == "__main__":
    main()
