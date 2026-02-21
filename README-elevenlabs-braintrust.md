# ElevenLabs + Braintrust Dataset Experiments

This package runs Braintrust eval experiments using an ElevenLabs agent, with optional prompt variants.

## Install

```bash
pip install -e .
```

## Environment

Set in `.env`:

```env
BRAINTRUST_API_KEY=...
ELEVENLABS_AGENT_ID=...
ELEVENLABS_API_KEY=...
```

## Run on a Braintrust dataset

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval
```

## Prompt As Experiment Input (per test case)

You can store prompt text inside each dataset row:

```json
{
  "input": {
    "simulated_user": { "text": "No puedo acceder a mi cuenta.", "language": "spanish" },
    "prompt_override": "Reply with exactly one lowercase language label."
  },
  "expected": "spanish",
  "metadata": { "case_id": "es-001", "round": "strict" }
}
```

The runner will use `input.prompt_override` (or `metadata.prompt_override`) for that specific test case.

You can also set user attitude/persona directly in each row:

```json
{
  "input": {
    "simulated_user": {
      "text": "I have been charged twice and I am frustrated.",
      "language": "english",
      "attitude": "frustrated",
      "tone": "direct",
      "cooperativeness": "low",
      "verbosity": "short",
      "patience": "low",
      "goal": "refund now"
    }
  },
  "expected": "english",
  "metadata": { "case_id": "en-angry-001" }
}
```

Supported per-row simulated-user behavior fields:
- `simulated_user.attitude`
- `simulated_user.tone`
- `simulated_user.emotional_state`
- `simulated_user.cooperativeness`
- `simulated_user.verbosity`
- `simulated_user.patience`
- `simulated_user.goal`
- `simulated_user.prompt` or `simulated_user.persona_prompt` (full direct control)

## Run prompt variants (one experiment per prompt)

### Inline prompts

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval \
  --prompt "You are strict. Reply with one word: english|spanish|french|german|italian" \
  --prompt "Classify language only. Output lowercase language name only."
```

### Prompt file

Create `prompts.json`:

```json
[
  {
    "name": "strict-one-word",
    "prompt": "Reply with exactly one lowercase language label: english, spanish, french, german, or italian."
  },
  {
    "name": "short-just-label",
    "prompt": "Detect the user language and output only the language name in lowercase."
  }
]
```

Run:

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval \
  --prompt-file prompts.json
```

## Use Gemini as the agent LLM

You can override the model used in simulation runs:

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval-gemini \
  --llm gemini-2.5-flash \
  --prompt "Output only: english|spanish|french|german|italian"
```

Optional generation controls:
- `--temperature 0.2`
- `--max-tokens 32`

## Notes

- Each prompt variant creates a separate Braintrust experiment named `<experiment-name>-<variant-name>`.
- If no prompt is provided, the runner uses the default prompt configured on your ElevenLabs agent.
- For hosted datasets, you can pass `--dataset-version` and `--max-examples`.
- Included starter files:
  - `dataset_language_prompt_variants.jsonl` (sample test cases)
  - `prompt_rounds.json` (sample experiment prompt rounds)

## Use Braintrust evaluators (custom metrics)

The runner includes `ExactMatch` by default. You can add custom evaluator functions:

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval \
  --evaluator custom_metrics:policy_violation \
  --evaluator custom_metrics:one_word_label
```

Evaluator function signature:

```python
def my_metric(input, output, expected):
    # return float | int | bool | None
    return 1.0
```

If you want only your custom metrics:

```bash
elevenlabs-braintrust-eval ... --no-exact-match --evaluator custom_metrics:my_metric
```

For fuzzy crisis eval without `ExactMatch`:

```bash
elevenlabs-braintrust-eval \
  --jsonl dataset_language_prompt_variants.jsonl \
  --experiment-name flood-fuzzy-eval \
  --llm gemini-2.5-flash \
  --output-mode structured \
  --no-exact-match \
  --evaluator custom_metrics:fuzzy_crisis_support \
  --evaluator custom_metrics:mentions_emergency_services \
  --evaluator custom_metrics:de_escalation_language_score \
  --evaluator custom_metrics:emergency_help_turn_efficiency \
  --evaluator custom_metrics:de_escalation_turn_efficiency
```

## Binary crisis scoring (new)

Use these evaluators for your new rubric:
- `agent_eval.custom_metrics:calmer_end_state_binary` (1/0)
- `agent_eval.custom_metrics:emergency_services_when_needed_binary` (1/0)
- `agent_eval.custom_metrics:turns_to_calm_state` (integer turns, `-1` if not reached)
- `agent_eval.custom_metrics:turns_to_emergency_services` (integer turns, `-1` if not mentioned)

Recommended dataset field per row:

```json
{
  "input": {
    "simulated_user": {
      "text": "I am freaked out and need help now.",
      "language": "english"
    },
    "needs_emergency": true
  }
}
```

## Trace Analysis -> Strategy Proposals

Generate strategy recommendations from Braintrust traces:

```bash
braintrust-strategy-proposer \
  --project "ElevenLabs Dataset Agent Eval" \
  --experiment flood-fuzzy-eval-r4-cli-1 \
  --experiment flood-fuzzy-eval-r4-cli-2 \
  --output strategy_report_r4.md
```

This analyzes task/score spans and proposes:
- prompt patch candidates
- metric targets
- priority failure cases to build a regression slice

### Modulate API evaluator

`custom_metrics.py` now includes `modulate_toxicity`, which calls a Modulate-compatible endpoint and logs the returned score as a Braintrust metric.

Add to `.env`:

```env
MODULATE_API_KEY=your_modulate_key
MODULATE_API_URL=https://your-modulate-endpoint
MODULATE_TIMEOUT_SECONDS=15
```

Run:

```bash
elevenlabs-braintrust-eval \
  --project "YOUR_PROJECT" \
  --dataset-name "YOUR_DATASET" \
  --experiment-name lang-eval \
  --evaluator custom_metrics:modulate_toxicity
```

The evaluator accepts either:
- numeric score fields (e.g. `score`, `toxicity_score`, `risk_score`)
- boolean flags (e.g. `flagged`, `unsafe`, `is_toxic`) mapped to `1.0/0.0`

## Autotune Service (polling worker)

Run a separate backend worker that polls every 15s and:
1. reads new root traces from a source Braintrust experiment,
2. generates findings + 2 prompt variants with Gemini,
3. runs eval variants on your base Braintrust dataset,
4. promotes winner only if metrics improve (and optionally updates live ElevenLabs prompt).

### Required env

```env
AUTOTUNE_PROJECT=ElevenLabs Dataset Agent Eval
AUTOTUNE_SOURCE_EXPERIMENT=flood-fuzzy-eval-r5-cli-1
AUTOTUNE_DATASET_PROJECT=ElevenLabs Dataset Agent Eval
AUTOTUNE_DATASET_NAME=YOUR_BRAINTRUST_DATASET
AUTOTUNE_DATASET_VERSION=   # optional
AUTOTUNE_JUDGE_MODEL=gemini-3-pro-preview
AUTOTUNE_AGENT_LLM=gemini-3-pro-preview
AUTOTUNE_AGENT_REASONING_EFFORT=low
```

### Run

```bash
python -m agent_eval.autotune_service --poll-seconds 15
```

Or after reinstalling editable package:

```bash
autotune-service --poll-seconds 15
```

### State and artifacts

- state: `artifacts/autotune/state.json`
- per-run artifacts: `artifacts/autotune/runs/<timestamp>/`
