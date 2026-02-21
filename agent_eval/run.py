import argparse
import importlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from autoevals import ExactMatch
from braintrust import Eval, init_dataset
from dotenv import load_dotenv
from elevenlabs import AgentConfig, ConversationSimulationSpecification, ElevenLabs
from elevenlabs.types.prompt_agent_api_model_output import PromptAgentApiModelOutput

LANGUAGES = ["english", "spanish", "french", "german", "italian"]
LANGUAGE_TO_CODE = {
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "german": "de",
    "italian": "it",
}
VALID_LANGUAGE_CODES = set(LANGUAGE_TO_CODE.values())


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


def _extract_text_fragments(value: Any) -> list[str]:
    value = _to_plain(value)
    found: list[str] = []

    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()
            if isinstance(item, str) and any(
                token in key_lower
                for token in ["text", "message", "response", "content", "transcript"]
            ):
                found.append(item)
            found.extend(_extract_text_fragments(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_extract_text_fragments(item))

    return found


def _extract_turn_count(value: Any) -> int | None:
    value = _to_plain(value)

    if isinstance(value, dict):
        for key in ["turn_count", "conversation_turns", "new_turns_count", "num_turns"]:
            v = value.get(key)
            if isinstance(v, int):
                return v

        for key in ["transcript", "messages", "conversation", "turns", "history"]:
            v = value.get(key)
            if isinstance(v, list):
                return len(v)

        for child in value.values():
            nested = _extract_turn_count(child)
            if nested is not None:
                return nested

    if isinstance(value, list):
        return len(value)

    return None


def _normalize_language(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    lowered = value.lower()
    for lang in LANGUAGES:
        if re.search(rf"\b{lang}\b", lowered):
            return lang
    return "unknown"


def _to_sim_language(value: Any) -> str:
    if not isinstance(value, str):
        return "en"
    lowered = value.strip().lower()
    if lowered in VALID_LANGUAGE_CODES:
        return lowered
    normalized = _normalize_language(lowered)
    return LANGUAGE_TO_CODE.get(normalized, "en")


def _expected_language(raw_expected: Any) -> str:
    if isinstance(raw_expected, str):
        return _normalize_language(raw_expected)
    if isinstance(raw_expected, dict):
        for key in ["language", "label", "expected_language"]:
            if key in raw_expected:
                return _normalize_language(raw_expected[key])
    return "unknown"


def _extract_user_input(
    raw_input: Any, metadata: dict[str, Any]
) -> tuple[str, str, str | None]:
    def _build_attitude_prompt(sim_user: dict[str, Any]) -> str | None:
        explicit = sim_user.get("prompt") or sim_user.get("persona_prompt")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()

        keys = [
            "attitude",
            "tone",
            "emotional_state",
            "cooperativeness",
            "verbosity",
            "patience",
            "goal",
        ]
        parts: list[str] = []
        for key in keys:
            value = sim_user.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{key}={value.strip()}")

        if not parts:
            return None

        return (
            "Simulated user behavior profile. "
            "Stay in character for the conversation. "
            + "; ".join(parts)
            + "."
        )

    if isinstance(raw_input, str):
        return (
            raw_input,
            _normalize_language(metadata.get("expected_language", "english")),
            metadata.get("prompt_override"),
        )

    if isinstance(raw_input, dict):
        prompt_override = raw_input.get("prompt_override")
        if not isinstance(prompt_override, str):
            prompt_override = metadata.get("prompt_override")
        if not isinstance(prompt_override, str):
            prompt_override = None

        sim_user = raw_input.get("simulated_user", {})
        if isinstance(sim_user, dict):
            text = sim_user.get("text", "")
            language = _to_sim_language(sim_user.get("language", "english"))
            attitude_prompt = _build_attitude_prompt(sim_user)
            if attitude_prompt:
                prompt_override = (
                    f"{prompt_override}\n\n{attitude_prompt}"
                    if prompt_override
                    else attitude_prompt
                )
            if text:
                return text, language, prompt_override

        text = raw_input.get("text", "") if isinstance(raw_input.get("text"), str) else ""
        if text:
            language = _to_sim_language(raw_input.get("language", "english"))
            return text, language, prompt_override

    return "", "english", None


def _load_jsonl(path: Path, max_examples: int | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows.append(
                {
                    "input": row.get("input", ""),
                    "expected": _expected_language(row.get("expected")),
                    "metadata": row.get("metadata", {}),
                }
            )
            if max_examples is not None and len(rows) >= max_examples:
                break

    return rows


def _load_braintrust_dataset(
    project: str,
    dataset_name: str,
    version: str | None,
    max_examples: int | None,
) -> list[dict[str, Any]]:
    dataset = init_dataset(project=project, name=dataset_name, version=version)
    rows: list[dict[str, Any]] = []
    for row in dataset.fetch():
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        rows.append(
            {
                "input": row.get("input", ""),
                "expected": _expected_language(row.get("expected")),
                "metadata": metadata,
            }
        )
        if max_examples is not None and len(rows) >= max_examples:
            break
    return rows


def _run_simulation(
    client: ElevenLabs,
    agent_id: str,
    user_text: str,
    user_language: str,
    turn_limit: int,
    prompt_text: str | None = None,
    llm: str | None = None,
    reasoning_effort: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    prompt_override = None
    if prompt_text or llm or temperature is not None or max_tokens is not None:
        prompt_kwargs: dict[str, Any] = {}
        if prompt_text:
            prompt_kwargs["prompt"] = prompt_text
        if llm:
            prompt_kwargs["llm"] = llm
        if reasoning_effort:
            prompt_kwargs["reasoning_effort"] = reasoning_effort
        if temperature is not None:
            prompt_kwargs["temperature"] = temperature
        if max_tokens is not None:
            prompt_kwargs["max_tokens"] = max_tokens
        prompt_override = PromptAgentApiModelOutput(**prompt_kwargs)
    spec = ConversationSimulationSpecification(
        simulated_user_config=AgentConfig(
            first_message=user_text,
            language=user_language,
            disable_first_message_interruptions=False,
            prompt=prompt_override,
        )
    )
    return client.conversational_ai.agents.simulate_conversation(
        agent_id=agent_id,
        simulation_specification=spec,
        new_turns_limit=turn_limit,
    )


def _build_task(
    client: ElevenLabs,
    agent_id: str,
    turn_limit: int,
    prompt_text: str | None,
    llm: str | None,
    reasoning_effort: str | None,
    temperature: float | None,
    max_tokens: int | None,
    output_mode: str,
):
    def task(example: Any) -> str:
        raw_input = example
        metadata: dict[str, Any] = {}
        if isinstance(example, dict) and (
            "input" in example or "metadata" in example or "expected" in example
        ):
            raw_input = example.get("input", example)
            if isinstance(example.get("metadata"), dict):
                metadata = example["metadata"]

        user_text, user_language, example_prompt_override = _extract_user_input(
            raw_input, metadata
        )
        if not user_text:
            return "error"

        effective_prompt = example_prompt_override or prompt_text

        try:
            result = _run_simulation(
                client,
                agent_id,
                user_text,
                user_language,
                turn_limit,
                effective_prompt,
                llm,
                reasoning_effort,
                temperature,
                max_tokens,
            )
            merged_text = "\n".join(_extract_text_fragments(result))
            turn_count = _extract_turn_count(result)
            if output_mode == "raw":
                return merged_text
            if output_mode == "structured":
                return {
                    "text": merged_text,
                    "turn_count": turn_count,
                    "result": _to_plain(result),
                }
            return _normalize_language(merged_text)
        except Exception:
            return "error"

    return task


def _load_prompt_variants(
    prompt_values: list[str] | None, prompt_file: str | None
) -> list[tuple[str, str | None]]:
    variants: list[tuple[str, str | None]] = []

    if prompt_file:
        with Path(prompt_file).open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise ValueError("--prompt-file must contain a JSON array")
        for idx, row in enumerate(raw):
            if not isinstance(row, dict):
                raise ValueError("--prompt-file entries must be objects")
            name = str(row.get("name", f"file-{idx + 1}"))
            prompt = row.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("Each prompt variant needs a non-empty 'prompt' field")
            variants.append((name, prompt))

    if prompt_values:
        for idx, prompt in enumerate(prompt_values):
            if prompt.strip():
                variants.append((f"cli-{idx + 1}", prompt))

    if not variants:
        variants.append(("default-agent-prompt", None))

    return variants


def _load_custom_evaluators(specs: list[str] | None) -> list[Any]:
    evaluators: list[Any] = []
    if not specs:
        return evaluators

    for spec in specs:
        if ":" not in spec:
            raise ValueError(
                f"Invalid evaluator '{spec}'. Use module_path:function_name format."
            )
        module_name, fn_name = spec.split(":", 1)
        module = importlib.import_module(module_name)
        fn = getattr(module, fn_name, None)
        if fn is None or not callable(fn):
            raise ValueError(f"Evaluator function not found or not callable: {spec}")
        evaluators.append(fn)
    return evaluators


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run ElevenLabs Agent experiments against Braintrust datasets"
    )
    parser.add_argument("--project", help="Braintrust project name for dataset lookup")
    parser.add_argument("--dataset-name", help="Braintrust dataset name")
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--jsonl", help="Local JSONL dataset path")
    parser.add_argument("--max-examples", type=int, default=None)
    parser.add_argument("--turn-limit", type=int, default=6)
    parser.add_argument(
        "--llm",
        default=None,
        help="Override agent LLM for simulation (e.g. gemini-2.5-flash, gpt-4.1-mini).",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default=None,
        help="Optional reasoning effort override for supported models.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional LLM temperature override.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Optional LLM max tokens override.",
    )
    parser.add_argument(
        "--output-mode",
        choices=["language", "raw", "structured"],
        default="language",
        help="Return normalized label, raw text, or structured output to scorers.",
    )
    parser.add_argument(
        "--prompt",
        action="append",
        help="Prompt override value. Provide multiple times to run multiple experiments.",
    )
    parser.add_argument(
        "--prompt-file",
        help="JSON file with prompt variants: [{\"name\":\"v1\",\"prompt\":\"...\"}]",
    )
    parser.add_argument(
        "--evaluator",
        action="append",
        help="Custom evaluator in module:function format (can repeat).",
    )
    parser.add_argument(
        "--no-exact-match",
        action="store_true",
        help="Disable built-in ExactMatch scorer.",
    )
    parser.add_argument("--eval-name", default="ElevenLabs Dataset Agent Eval")
    parser.add_argument(
        "--experiment-name",
        default=f"elevenlabs-dataset-eval-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
    )
    args = parser.parse_args()

    if bool(args.dataset_name) == bool(args.jsonl):
        raise ValueError("Provide exactly one of --dataset-name or --jsonl")

    if args.dataset_name and not args.project:
        raise ValueError("--project is required when using --dataset-name")

    load_dotenv()
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")
    api_key = os.environ.get("ELEVENLABS_API_KEY")

    if not os.environ.get("BRAINTRUST_API_KEY"):
        raise ValueError("BRAINTRUST_API_KEY is required")
    if not agent_id:
        raise ValueError("ELEVENLABS_AGENT_ID is required")

    if args.jsonl:
        data = _load_jsonl(Path(args.jsonl), args.max_examples)
        dataset_source = {"type": "jsonl", "path": args.jsonl}
    else:
        data = _load_braintrust_dataset(
            project=args.project,
            dataset_name=args.dataset_name,
            version=args.dataset_version,
            max_examples=args.max_examples,
        )
        dataset_source = {
            "type": "braintrust",
            "project": args.project,
            "dataset_name": args.dataset_name,
            "dataset_version": args.dataset_version,
        }

    if not data:
        raise ValueError("No examples found in dataset")

    client = ElevenLabs(api_key=api_key)
    prompt_variants = _load_prompt_variants(args.prompt, args.prompt_file)
    custom_evaluators = _load_custom_evaluators(args.evaluator)
    scores: list[Any] = []
    if not args.no_exact_match:
        scores.append(ExactMatch)
    scores.extend(custom_evaluators)

    if not scores:
        raise ValueError("At least one evaluator is required")

    for variant_name, prompt_text in prompt_variants:
        task = _build_task(
            client=client,
            agent_id=agent_id,
            turn_limit=args.turn_limit,
            prompt_text=prompt_text,
            llm=args.llm,
            reasoning_effort=args.reasoning_effort,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            output_mode=args.output_mode,
        )
        experiment_name = f"{args.experiment_name}-{variant_name}"

        Eval(
            args.eval_name,
            data=data,
            task=task,
            scores=scores,
            experiment_name=experiment_name,
            metadata={
                "provider": "elevenlabs",
                "agent_id": agent_id,
                "dataset_source": dataset_source,
                "turn_limit": args.turn_limit,
                "prompt_variant": variant_name,
                "prompt_override": prompt_text,
                "llm_override": args.llm,
                "reasoning_effort_override": args.reasoning_effort,
                "temperature_override": args.temperature,
                "max_tokens_override": args.max_tokens,
                "output_mode": args.output_mode,
            },
        )


if __name__ == "__main__":
    main()
