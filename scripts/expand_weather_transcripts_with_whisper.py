#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import whisper

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data/kaggle_911/911_first6sec/911_metadata.csv"
ALL_IN = ROOT / "data/kaggle_911/disaster_weather_transcripts_all_elevenlabs.csv"
BASE_IN = ROOT / "data/kaggle_911/disaster_weather_transcripts_elevenlabs.csv"
ALL_OUT = ROOT / "data/kaggle_911/disaster_weather_transcripts_all_combined.csv"
WEATHER_OUT = ROOT / "data/kaggle_911/disaster_weather_transcripts_weather_only.csv"

TARGET = 20
MAX_NEW_TRANSCRIBES = 180


def read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def is_weatherish(text: str) -> bool:
    t = (text or "").lower()
    terms = [
        "tornado",
        "funnel cloud",
        "rotation",
        "flood",
        "flooded",
        "snow",
        "snowstorm",
        "blizzard",
        "storm",
        "hurricane",
        "wildfire",
        "forest fire",
        "fire",
        "ice",
        "icy",
        "freezing",
        "water",
        "drown",
        "drowning",
        "boat",
        "capsized",
        "pond",
        "creek",
        "river",
        "swept",
        "trapped",
    ]
    return any(term in t for term in terms)


def score_candidate(title: str, desc: str) -> int:
    txt = f"{title} {desc}".lower()
    negatives = [
        "murder",
        "shooting",
        "stabbing",
        "intruder",
        "alligator",
        "bear attack",
        "taser",
    ]
    if any(n in txt for n in negatives):
        return -100
    score = 0
    for kw, w in {
        "tornado": 12,
        "funnel cloud": 12,
        "flood": 11,
        "flooded": 11,
        "wildfire": 10,
        "forest fire": 10,
        "snowstorm": 9,
        "storm": 8,
        "drowning in car": 8,
        "car in water": 8,
        "swept": 8,
        "boat rescue": 7,
        "capsized": 7,
        "ice": 6,
        "icy": 6,
        "freezing": 6,
        "pond": 5,
        "creek": 5,
        "river": 4,
        "water": 4,
        "trapped": 3,
        "fire": 3,
    }.items():
        if kw in txt:
            score += w
    return score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=TARGET)
    parser.add_argument("--max-new", type=int, default=MAX_NEW_TRANSCRIBES)
    args = parser.parse_args()

    all_rows = read_csv(ALL_IN)
    if not all_rows:
        all_rows = read_csv(BASE_IN)

    # latest row per filename
    by_file = {r["filename"]: r for r in all_rows if r.get("filename")}
    weather_rows = [r for r in by_file.values() if r.get("status", "").startswith("ok") and is_weatherish(r.get("transcript", ""))]
    print(f"starting weather={len(weather_rows)}")

    if len(weather_rows) >= args.target:
        write_csv(WEATHER_OUT, sorted(weather_rows, key=lambda r: r["filename"]), ["filename", "status", "transcript"])
        write_csv(ALL_OUT, sorted(by_file.values(), key=lambda r: r["filename"]), ["filename", "status", "transcript"])
        print("already at target")
        return 0

    meta = read_csv(META)
    candidates = []
    for r in meta:
        fn = r.get("filename", "")
        if not fn:
            continue
        # skip files already transcribed successfully
        prev = by_file.get(fn)
        if prev and prev.get("status", "").startswith("ok"):
            continue
        s = score_candidate(r.get("title", ""), r.get("description", ""))
        if s > 0:
            candidates.append((s, fn))
    candidates.sort(reverse=True)

    model = whisper.load_model("tiny")

    transcribed_new = 0
    for _, rel in candidates:
        if len(weather_rows) >= args.target or transcribed_new >= args.max_new:
            break
        wav = ROOT / "data/kaggle_911" / rel
        if not wav.exists():
            by_file[rel] = {"filename": rel, "status": "missing_file", "transcript": ""}
            continue
        try:
            res = model.transcribe(str(wav), language="en", fp16=False, verbose=False, task="transcribe")
            txt = (res.get("text") or "").strip()
            status = "ok_whisper" if txt else "ok_no_text_whisper"
        except Exception as e:
            txt = ""
            status = f"error_whisper:{type(e).__name__}"

        row = {"filename": rel, "status": status, "transcript": txt}
        by_file[rel] = row
        transcribed_new += 1
        if status.startswith("ok") and is_weatherish(txt):
            weather_rows = [r for r in by_file.values() if r.get("status", "").startswith("ok") and is_weatherish(r.get("transcript", ""))]
            print(f"WEATHER {len(weather_rows)}/{args.target}: {rel}")
        else:
            print(f"NONWEATHER: {rel} ({status})")

    all_dedup = sorted(by_file.values(), key=lambda r: r["filename"])
    weather_dedup = sorted(
        [r for r in by_file.values() if r.get("status", "").startswith("ok") and is_weatherish(r.get("transcript", ""))],
        key=lambda r: r["filename"],
    )

    write_csv(ALL_OUT, all_dedup, ["filename", "status", "transcript"])
    write_csv(WEATHER_OUT, weather_dedup, ["filename", "status", "transcript"])
    print(f"done weather={len(weather_dedup)} transcribed_new={transcribed_new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
