import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import braintrust
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
class ExperimentAnalysis:
    name: str
    cases: list[CaseResult]
    metric_averages: dict[str, float]
    case_count: int
    avg_turn_count: float | None
    weak_cases_by_metric: dict[str, list[CaseResult]]


def _case_overall_score(case: CaseResult) -> float:
    if not case.scores:
        return 0.0
    return mean(case.scores.values())


def _case_label(case: CaseResult) -> str:
    cid = case.metadata.get("case_id")
    if isinstance(cid, str) and cid:
        return cid
    if isinstance(case.input_text, str) and case.input_text.strip():
        snippet = case.input_text.strip().replace("\n", " ")[:60]
        return f"input:{snippet}"
    return f"span:{case.root_span_id}"


def _case_strengths(case: CaseResult) -> list[str]:
    strengths: list[str] = []
    if case.scores.get("mentions_emergency_services", 0.0) >= 1.0:
        strengths.append("explicit emergency escalation present")
    if case.scores.get("fuzzy_crisis_support", 0.0) >= 0.25:
        strengths.append("contains concrete crisis-action language")
    if case.scores.get("de_escalation_language_score", 0.0) >= 0.10:
        strengths.append("includes de-escalation language")
    if case.scores.get("emergency_help_turn_efficiency", 0.0) >= 0.4:
        strengths.append("emergency guidance delivered with acceptable timing")
    if case.scores.get("de_escalation_turn_efficiency", 0.0) >= 0.10:
        strengths.append("calming language appears relatively early")
    return strengths


def _case_failures(case: CaseResult) -> list[str]:
    failures: list[str] = []
    if case.scores.get("mentions_emergency_services", 0.0) < 1.0:
        failures.append("no explicit emergency-services escalation")
    if case.scores.get("fuzzy_crisis_support", 0.0) < 0.20:
        failures.append("insufficient actionable crisis instructions")
    if case.scores.get("de_escalation_language_score", 0.0) < 0.10:
        failures.append("weak or missing calming/de-escalation language")
    if case.scores.get("emergency_help_turn_efficiency", 0.0) < 0.4:
        failures.append("emergency guidance likely too slow")
    if case.scores.get("de_escalation_turn_efficiency", 0.0) < 0.10:
        failures.append("de-escalation appears too late or too weak")
    if case.turn_count is not None and case.turn_count >= 18:
        failures.append("conversation runs very long before resolution")
    return failures


def _case_fix_snippet(case: CaseResult) -> str:
    failures = _case_failures(case)
    if not failures:
        return "Keep this behavior as a positive exemplar for future prompt tuning."
    fixes: list[str] = []
    if "no explicit emergency-services escalation" in failures:
        fixes.append("Add: 'If danger is immediate, call 911/local emergency services now.'")
    if "insufficient actionable crisis instructions" in failures:
        fixes.append("Add exactly 3 concrete safety steps.")
    if "weak or missing calming/de-escalation language" in failures:
        fixes.append("Begin with validation + one grounding step ('take a slow breath').")
    if "emergency guidance likely too slow" in failures or "de-escalation appears too late or too weak" in failures:
        fixes.append("Deliver safety + escalation in the first response before follow-up questions.")
    if "conversation runs very long before resolution" in failures:
        fixes.append("Use concise responses and a single follow-up question.")
    return " ".join(fixes)


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        if isinstance(value.get("score"), (int, float)):
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
        turn_count = output_value.get("turn_count")
        if not isinstance(turn_count, int):
            turn_count = None
        return text, turn_count
    return str(output_value), None


def _fetch_cases(project: str, experiment: str) -> list[CaseResult]:
    exp = braintrust.init(project=project, experiment=experiment, open=True)
    rows = list(exp.fetch())

    task_rows: dict[str, dict[str, Any]] = {}
    score_rows: dict[str, dict[str, float]] = defaultdict(dict)

    for row in rows:
        root = row.get("root_span_id") or row.get("span_id")
        if not isinstance(root, str):
            continue

        span_type = (row.get("span_attributes") or {}).get("type")
        if span_type == "task":
            task_rows[root] = row
        elif span_type == "score":
            for metric, raw_val in (row.get("scores") or {}).items():
                val = _to_number(raw_val)
                if val is not None:
                    score_rows[root][metric] = val

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


def _analyze_experiment(name: str, cases: list[CaseResult], weak_threshold: float = 0.4) -> ExperimentAnalysis:
    metric_values: dict[str, list[float]] = defaultdict(list)
    for case in cases:
        for metric, value in case.scores.items():
            metric_values[metric].append(value)

    metric_averages = {
        metric: mean(values) for metric, values in metric_values.items() if len(values) > 0
    }

    weak_cases_by_metric: dict[str, list[CaseResult]] = {}
    for metric in metric_averages:
        weak = [c for c in cases if c.scores.get(metric, 0.0) <= weak_threshold]
        weak_cases_by_metric[metric] = weak

    turns = [c.turn_count for c in cases if isinstance(c.turn_count, int)]
    avg_turn_count = mean(turns) if turns else None

    return ExperimentAnalysis(
        name=name,
        cases=cases,
        metric_averages=metric_averages,
        case_count=len(cases),
        avg_turn_count=avg_turn_count,
        weak_cases_by_metric=weak_cases_by_metric,
    )


def _propose_strategies(analysis: ExperimentAnalysis, top_k_cases: int) -> list[dict[str, Any]]:
    strategies: list[dict[str, Any]] = []
    avgs = analysis.metric_averages

    def score(metric: str) -> float:
        return avgs.get(metric, 0.0)

    if score("mentions_emergency_services") < 0.8:
        strategies.append(
            {
                "title": "Hard-Code Emergency Escalation Trigger",
                "because": "Emergency routing is not consistent enough in danger scenarios.",
                "prompt_patch": (
                    "If user describes immediate physical danger (flood, fire, trapped, life risk), "
                    "your first response must include contacting emergency services (e.g. call 911) "
                    "before any additional guidance."
                ),
                "metric_target": "mentions_emergency_services >= 0.85",
            }
        )

    if score("de_escalation_language_score") < 0.5:
        strategies.append(
            {
                "title": "Force Two-Step De-Escalation Lead",
                "because": "Calming language is weak or inconsistent.",
                "prompt_patch": (
                    "First sentence: emotional validation. Second sentence: calming instruction "
                    "(one breathing or grounding step). Then provide actions."
                ),
                "metric_target": "de_escalation_language_score >= 0.55",
            }
        )

    if score("emergency_help_turn_efficiency") < 0.6 or score("de_escalation_turn_efficiency") < 0.5:
        strategies.append(
            {
                "title": "Reduce To Immediate Action Template",
                "because": "Helpful behaviors are arriving too late in the conversation.",
                "prompt_patch": (
                    "Within first response include: (1) safety reassurance, (2) emergency escalation if risk, "
                    "(3) exactly 3 immediate steps, (4) one confirmation question."
                ),
                "metric_target": "turn-efficiency metrics improve by >= 0.10",
            }
        )

    if score("fuzzy_crisis_support") < 0.45:
        strategies.append(
            {
                "title": "Improve Crisis Action Specificity",
                "because": "Responses lack concrete high-utility crisis instructions.",
                "prompt_patch": (
                    "Prioritize location-based actionable guidance: move to higher ground, avoid floodwater, "
                    "cut electricity if safe, and state nearest safe shelter action."
                ),
                "metric_target": "fuzzy_crisis_support >= 0.45",
            }
        )

    weak_case_counter: Counter[str] = Counter()
    for metric, weak_cases in analysis.weak_cases_by_metric.items():
        for case in weak_cases[:top_k_cases]:
            weak_case_counter[_case_label(case)] += 1

    top_failures = [cid for cid, _ in weak_case_counter.most_common(top_k_cases)]
    if top_failures:
        strategies.append(
            {
                "title": "Create Targeted Regression Slice",
                "because": "A subset of cases repeatedly fails across multiple metrics.",
                "action": "Create a focused eval subset and require pass before full-run promotion.",
                "priority_cases": top_failures,
            }
        )

    return strategies


def _format_report(
    project: str,
    analyses: list[ExperimentAnalysis],
    strategies_by_experiment: dict[str, list[dict[str, Any]]],
) -> str:
    lines: list[str] = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    lines.append(f"# Braintrust Strategy Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append(f"Project: {project}")
    lines.append("")

    if len(analyses) > 1:
        lines.append("## Variant Ranking")
        ranked = sorted(
            analyses,
            key=lambda a: mean(a.metric_averages.values()) if a.metric_averages else 0.0,
            reverse=True,
        )
        for idx, a in enumerate(ranked, start=1):
            overall = mean(a.metric_averages.values()) if a.metric_averages else 0.0
            lines.append(f"{idx}. {a.name} | overall={overall:.4f} | cases={a.case_count}")
        lines.append("")

    for analysis in analyses:
        lines.append(f"## Experiment: {analysis.name}")
        lines.append("")
        lines.append("### Metrics")
        for metric, value in sorted(analysis.metric_averages.items()):
            lines.append(f"- {metric}: {value:.4f}")
        if analysis.avg_turn_count is not None:
            lines.append(f"- avg_turn_count: {analysis.avg_turn_count:.2f}")
        lines.append("")

        lines.append("### Per-Task Breakdown")
        for idx, case in enumerate(sorted(analysis.cases, key=_case_overall_score, reverse=True), start=1):
            case_scores = ", ".join(
                f"{k}={v:.3f}" for k, v in sorted(case.scores.items())
            ) or "no scores"
            strengths = _case_strengths(case)
            failures = _case_failures(case)
            lines.append(
                f"- Task {idx} ({_case_label(case)}) | overall={_case_overall_score(case):.3f} "
                f"| turns={case.turn_count if case.turn_count is not None else 'n/a'}"
            )
            lines.append(f"  input: {case.input_text[:180].replace(chr(10), ' ')}")
            lines.append(f"  scores: {case_scores}")
            lines.append(
                f"  worked: {', '.join(strengths) if strengths else 'none observed'}"
            )
            lines.append(
                f"  did_not_work: {', '.join(failures) if failures else 'none observed'}"
            )
            lines.append(f"  fix_snippet: {_case_fix_snippet(case)}")
        lines.append("")

        lines.append("### Proposed Strategies")
        strategies = strategies_by_experiment.get(analysis.name, [])
        if not strategies:
            lines.append("- No urgent strategy changes detected from current thresholds.")
        else:
            for s in strategies:
                lines.append(f"- {s['title']}: {s['because']}")
                if "prompt_patch" in s:
                    lines.append(f"  prompt_patch: {s['prompt_patch']}")
                if "metric_target" in s:
                    lines.append(f"  target: {s['metric_target']}")
                if "action" in s:
                    lines.append(f"  action: {s['action']}")
                if "priority_cases" in s:
                    lines.append(f"  priority_cases: {', '.join(s['priority_cases'])}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Braintrust experiment traces and propose prompt/agent strategy updates"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--experiment",
        action="append",
        required=True,
        help="Experiment name. Repeat to compare variants.",
    )
    parser.add_argument("--top-cases", type=int, default=5)
    parser.add_argument(
        "--output",
        default=f"strategy_report_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.md",
    )
    args = parser.parse_args()

    load_dotenv()

    analyses: list[ExperimentAnalysis] = []
    strategies_by_experiment: dict[str, list[dict[str, Any]]] = {}

    for experiment_name in args.experiment:
        cases = _fetch_cases(args.project, experiment_name)
        analysis = _analyze_experiment(experiment_name, cases)
        analyses.append(analysis)
        strategies_by_experiment[experiment_name] = _propose_strategies(
            analysis, top_k_cases=args.top_cases
        )

    report = _format_report(args.project, analyses, strategies_by_experiment)
    output_path = Path(args.output)
    output_path.write_text(report, encoding="utf-8")

    print(f"Wrote strategy report: {output_path}")


if __name__ == "__main__":
    main()
