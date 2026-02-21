#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSCRIPTS = ROOT / "data/kaggle_911/disaster_weather_transcripts_all_combined.csv"
DEFAULT_FILELIST = ROOT / "data/kaggle_911/selected_transcript_files.txt"
DEFAULT_TRAIN = ROOT / "datasets/dataset_train.jsonl"
DEFAULT_TEST = ROOT / "datasets/dataset_test.jsonl"

ATTITUDES = [
    {
        "emotional_state": "panicked",
        "attitude": "urgent",
        "tone": "shaky",
        "cooperativeness": "high",
        "verbosity": "medium",
        "patience": "low",
    },
    {
        "emotional_state": "terrified",
        "attitude": "desperate",
        "tone": "pleading",
        "cooperativeness": "high",
        "verbosity": "high",
        "patience": "low",
    },
    {
        "emotional_state": "anxious",
        "attitude": "confused",
        "tone": "worried",
        "cooperativeness": "medium",
        "verbosity": "medium",
        "patience": "medium",
    },
    {
        "emotional_state": "overwhelmed",
        "attitude": "disoriented",
        "tone": "scattered",
        "cooperativeness": "medium",
        "verbosity": "short",
        "patience": "low",
    },
    {
        "emotional_state": "fearful",
        "attitude": "impatient",
        "tone": "direct",
        "cooperativeness": "low",
        "verbosity": "short",
        "patience": "very low",
    },
    {
        "emotional_state": "frantic",
        "attitude": "help-seeking",
        "tone": "rapid",
        "cooperativeness": "high",
        "verbosity": "medium",
        "patience": "low",
    },
]


def _read_filelist(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def _read_transcripts(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fn = (row.get("filename") or "").strip()
            txt = (row.get("transcript") or "").strip()
            if fn:
                out[fn] = txt
    return out


def _needs_emergency(text: str) -> bool:
    lowered = text.lower()
    danger_terms = [
        "fire",
        "flood",
        "underwater",
        "not breathing",
        "bleeding",
        "ambulance",
        "crashed",
        "shot",
        "police",
        "emergency",
    ]
    return any(term in lowered for term in danger_terms)


def _build_rows(file_names: list[str], transcripts: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    for idx, file_name in enumerate(file_names, start=1):
        text = transcripts.get(file_name, "").strip()
        if not text:
            text = f"Emergency caller audio from {file_name}."

        attitude = ATTITUDES[(idx - 1) % len(ATTITUDES)]
        needs_emergency = _needs_emergency(text)

        row = {
            "input": {
                "simulated_user": {
                    "text": text,
                    "language": "english",
                    "goal": "get immediate safety guidance and next actions",
                    **attitude,
                },
                "needs_emergency": needs_emergency,
            },
            "expected": "english",
            "metadata": {
                "case_id": f"selected-{idx:03d}",
                "scenario": "911_weather_emergency_transcript",
                "source_filename": file_name,
                "needs_emergency": needs_emergency,
            },
        }
        rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build train/test JSONL datasets from selected transcript filenames")
    parser.add_argument("--transcripts-csv", default=str(DEFAULT_TRANSCRIPTS))
    parser.add_argument("--filelist", default=str(DEFAULT_FILELIST))
    parser.add_argument("--train-out", default=str(DEFAULT_TRAIN))
    parser.add_argument("--test-out", default=str(DEFAULT_TEST))
    parser.add_argument("--train-ratio", type=float, default=0.75)
    args = parser.parse_args()

    filelist = _read_filelist(Path(args.filelist))
    transcripts = _read_transcripts(Path(args.transcripts_csv))
    rows = _build_rows(filelist, transcripts)

    train_count = max(1, min(len(rows) - 1, int(len(rows) * args.train_ratio))) if len(rows) > 1 else len(rows)
    train_rows = rows[:train_count]
    test_rows = rows[train_count:]

    for row in train_rows:
        row["metadata"]["split"] = "train"
    for row in test_rows:
        row["metadata"]["split"] = "test"

    _write_jsonl(Path(args.train_out), train_rows)
    _write_jsonl(Path(args.test_out), test_rows)

    print(f"Wrote train={len(train_rows)} to {args.train_out}")
    print(f"Wrote test={len(test_rows)} to {args.test_out}")
    missing = [fn for fn in filelist if not transcripts.get(fn)]
    print(f"Missing transcript rows={len(missing)}")
    if missing:
        for fn in missing:
            print(f"  - {fn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
