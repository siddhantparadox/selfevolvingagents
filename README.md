# Self-Evolving Crisis Voice Agent

This project builds and continuously improves an ElevenLabs crisis-support voice agent using Braintrust traces and experiments.

## What We Built

- Pulled 911 call audio/transcript data and identified weather-related emergency cases.
- Processed weather-focused transcript slices into train/test datasets for evaluation experiments.
- Built an ElevenLabs agent flow that can query real-time data APIs (for example weather/flood context) to assess whether the caller is in immediate risk.
- Wired a Braintrust-driven autotune loop that proposes, tests, validates, and promotes better prompts.

## Data Pipeline (911 + Weather)

- Source data lives under `data/kaggle_911/` (including `911_first6sec` metadata/audio references).
- Weather-focused extraction and expansion scripts:
  - `scripts/expand_weather_transcripts_to_target.py`
  - `scripts/expand_weather_transcripts_with_whisper.py`
- Generated datasets used for experimentation:
  - `datasets/dataset_train.jsonl`
  - `datasets/dataset_test.jsonl`
  - `datasets/dataset_language_prompt_variants.jsonl`

Build train/test directly from the selected transcript file list:

```bash
python scripts/build_selected_transcript_datasets.py
```

Selected list file:
- `data/kaggle_911/selected_transcript_files.txt`

## Agent + Eval Loop

1. New logs/traces are ingested into Braintrust.
2. The autotune service polls for new traces and analyzes strengths/weaknesses.
3. It generates **2 candidate prompt variants**.
4. It runs a **test-dataset experiment** for baseline vs candidates.
5. If scores improve, it runs a **validation experiment**.
6. If both stages pass, it updates the candidate prompt in ElevenLabs.

Autotune worker:
- `agent_eval/autotune_service.py`

Eval runner and metrics:
- `agent_eval/run.py`
- `agent_eval/run_train_test.py`
- `agent_eval/custom_metrics.py`

Strategy/report generation:
- `agent_eval/strategy_proposer.py`
- `agent_eval/gemini_trace_strategy.py`

## Run the Autotune Service

The autotune server is a long-running polling worker. It must be running continuously for new Braintrust logs to trigger analysis, prompt generation, and experiment cycles.

Use environment variables in `.env` (Braintrust, ElevenLabs, judge/model keys), then run:

```bash
python -m agent_eval.autotune_service --poll-seconds 15
```

Optional (allow live prompt updates in ElevenLabs when gates pass):

```bash
python -m agent_eval.autotune_service --poll-seconds 15 --update-live-prompt
```

Run in background (example):

```bash
nohup python -m agent_eval.autotune_service --poll-seconds 15 > autotune.log 2>&1 &
```

## Run 2 Experiments (Train + Test)

Run train and test experiments back-to-back and print score summaries for both:

```bash
python -m agent_eval.run_train_test \
  --project "ElevenLabs Dataset Agent Eval" \
  --train-jsonl datasets/dataset_train.jsonl \
  --test-jsonl datasets/dataset_test.jsonl \
  --experiment-prefix selected-transcripts-r1 \
  --turn-limit 20 \
  --output-mode structured \
  --no-exact-match \
  --evaluator agent_eval.custom_metrics:judge_emergency_services_when_needed_binary \
  --evaluator agent_eval.custom_metrics:judge_calmer_end_state_binary \
  --evaluator agent_eval.custom_metrics:judge_turns_to_emergency_services \
  --evaluator agent_eval.custom_metrics:judge_turns_to_calm_state \
  --prompt "PROMPT_VARIANT_A" \
  --prompt "PROMPT_VARIANT_B"
```

## Core Goal

Continuously optimize de-escalation and safety behavior for weather-related crisis calls with a controlled, experiment-gated promotion pipeline.
