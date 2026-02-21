#!/usr/bin/env python3
import csv
import json
import os
import re
import shlex
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
META = ROOT / "data/kaggle_911/911_first6sec/911_metadata.csv"
ALL_TRANSCRIPTS = ROOT / "data/kaggle_911/disaster_weather_transcripts_all_elevenlabs.csv"
WEATHER_ONLY = ROOT / "data/kaggle_911/disaster_weather_transcripts_weather_only.csv"
JSON_DIR = ROOT / "data/kaggle_911/elevenlabs_transcripts_json_expanded"

API_URL = "https://api.elevenlabs.io/v1/speech-to-text"
MODEL_ID = "scribe_v1"
TARGET = 20
MAX_NEW_TRANSCRIBES = 120


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        if not key:
            continue
        try:
            parts = shlex.split(v, comments=True)
            val = parts[0] if parts else ""
        except ValueError:
            val = v.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)
    if not os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELLEVENLABS_API_KEY"):
        os.environ["ELEVENLABS_API_KEY"] = os.environ["ELLEVENLABS_API_KEY"]


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


def classify_weatherish(transcript: str) -> bool:
    t = (transcript or "").lower()
    weather_terms = [
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
        "drowning",
        "drown",
        "boat",
        "capsized",
        "pond",
        "creek",
        "river",
        "swept",
        "trapped",
    ]
    return any(term in t for term in weather_terms)


def candidate_score(title: str, desc: str) -> int:
    text = f"{title} {desc}".lower()
    positive = {
        "tornado": 10,
        "funnel cloud": 10,
        "flood": 10,
        "flooded": 10,
        "snowstorm": 9,
        "wildfire": 9,
        "forest fire": 8,
        "storm": 7,
        "car in water": 8,
        "swept": 8,
        "drowning in car": 8,
        "boat rescue": 8,
        "capsized": 8,
        "pond": 6,
        "creek": 6,
        "river": 5,
        "ice": 5,
        "icy": 5,
        "freezing": 5,
        "water": 4,
        "trapped": 3,
    }
    negative = [
        "murder",
        "stabbing",
        "shooting",
        "intruder",
        "bear attack",
        "alligator",
        "taser",
        "mall shooting",
    ]
    if any(n in text for n in negative):
        return -100
    score = 0
    for k, v in positive.items():
        if k in text:
            score += v
    return score


def extract_text(payload: dict) -> str:
    for key in ("text", "transcript"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    words = payload.get("words")
    if isinstance(words, list):
        out = []
        for w in words:
            if isinstance(w, dict):
                t = w.get("text")
                if isinstance(t, str) and t:
                    out.append(t)
        if out:
            return " ".join(out).strip()
    return ""


def main() -> int:
    load_env(ENV)
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        print("Missing ELEVENLABS_API_KEY")
        return 1

    all_rows = read_csv(ALL_TRANSCRIPTS)
    if not all_rows:
        all_rows = read_csv(ROOT / "data/kaggle_911/disaster_weather_transcripts_elevenlabs.csv")
    weather_rows = [r for r in all_rows if classify_weatherish(r.get("transcript", ""))]

    if len(weather_rows) >= TARGET:
        write_csv(WEATHER_ONLY, weather_rows, ["filename", "status", "transcript"])
        print(f"already_at_target weather={len(weather_rows)}")
        return 0

    transcribed = {r["filename"] for r in all_rows if r.get("filename")}
    meta_rows = read_csv(META)
    candidates = []
    for r in meta_rows:
        fn = r.get("filename", "")
        if not fn or fn in transcribed:
            continue
        score = candidate_score(r.get("title", ""), r.get("description", ""))
        if score > 0:
            candidates.append((score, fn))
    candidates.sort(reverse=True)

    JSON_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    headers = {"xi-api-key": api_key}
    new_calls = 0

    for _, rel in candidates:
        if len(weather_rows) >= TARGET or new_calls >= MAX_NEW_TRANSCRIBES:
            break
        wav = ROOT / "data/kaggle_911" / rel
        if not wav.exists():
            continue
        with wav.open("rb") as fh:
            files = {"file": (wav.name, fh, "audio/wav")}
            data = {"model_id": MODEL_ID}
            try:
                resp = session.post(API_URL, headers=headers, files=files, data=data, timeout=180)
            except Exception as e:
                all_rows.append({"filename": rel, "status": f"request_error:{e}", "transcript": ""})
                new_calls += 1
                continue
        payload = {}
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text}
        (JSON_DIR / f"{wav.stem}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        transcript = extract_text(payload) if resp.ok else ""
        status = "ok" if (resp.ok and transcript) else (f"http_{resp.status_code}" if not resp.ok else "ok_no_text")
        row = {"filename": rel, "status": status, "transcript": transcript}
        all_rows.append(row)
        if status == "ok" and classify_weatherish(transcript):
            weather_rows.append(row)
            print(f"WEATHER {len(weather_rows)}/{TARGET}: {rel}")
        else:
            print(f"NONWEATHER: {rel} ({status})")
        new_calls += 1

    # dedupe keep last occurrence
    latest = {}
    for r in all_rows:
        latest[r["filename"]] = r
    dedup_all = list(latest.values())
    dedup_weather = [r for r in dedup_all if r.get("status") == "ok" and classify_weatherish(r.get("transcript", ""))]
    dedup_weather.sort(key=lambda x: x["filename"])
    dedup_all.sort(key=lambda x: x["filename"])

    write_csv(ALL_TRANSCRIPTS, dedup_all, ["filename", "status", "transcript"])
    write_csv(WEATHER_ONLY, dedup_weather, ["filename", "status", "transcript"])
    print(f"done weather={len(dedup_weather)} total_transcribed={sum(1 for r in dedup_all if r.get('status') == 'ok')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

