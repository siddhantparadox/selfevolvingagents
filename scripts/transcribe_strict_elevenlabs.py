#!/usr/bin/env python3
import csv
import json
import os
import sys
import argparse
import shlex
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / '.env'
FILES_LIST = ROOT / 'data/kaggle_911/disaster_weather_filenames.txt'
OUT_CSV = ROOT / 'data/kaggle_911/disaster_weather_transcripts_elevenlabs.csv'
OUT_JSON_DIR = ROOT / 'data/kaggle_911/elevenlabs_transcripts_json'
API_URL = 'https://api.elevenlabs.io/v1/speech-to-text'
MODEL_ID = 'scribe_v1'


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[len('export '):].strip()
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        key = k.strip()
        if not key:
            continue
        # Strip inline comments and quotes: FOO="bar # baz" stays intact.
        try:
            value = shlex.split(v, comments=True)
            parsed = value[0] if value else ''
        except ValueError:
            parsed = v.strip().strip('"').strip("'")
        os.environ.setdefault(key, parsed)

    # Normalize local typo'd key names to expected ones.
    if not os.environ.get('ELEVENLABS_API_KEY') and os.environ.get('ELLEVENLABS_API_KEY'):
        os.environ['ELEVENLABS_API_KEY'] = os.environ['ELLEVENLABS_API_KEY']
    if not os.environ.get('ELEVENLABS_AGENT_ID') and os.environ.get('ELLEVENLABS_AGENT_ID'):
        os.environ['ELEVENLABS_AGENT_ID'] = os.environ['ELLEVENLABS_AGENT_ID']


def get_text(payload: dict) -> str:
    for key in ('text', 'transcript'):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    words = payload.get('words')
    if isinstance(words, list):
        tokens = []
        for w in words:
            if isinstance(w, dict):
                t = w.get('text')
                if isinstance(t, str) and t:
                    tokens.append(t)
        if tokens:
            return ' '.join(tokens).strip()
    return ''


def main() -> int:
    parser = argparse.ArgumentParser(description='Transcribe a list of audio files with ElevenLabs STT.')
    parser.add_argument('--files-list', default=str(FILES_LIST), help='Path to newline-separated relative file list')
    parser.add_argument('--out-csv', default=str(OUT_CSV), help='Output CSV path')
    parser.add_argument('--json-dir', default=str(OUT_JSON_DIR), help='Directory for raw response JSON files')
    args = parser.parse_args()

    files_list = Path(args.files_list)
    out_csv = Path(args.out_csv)
    out_json_dir = Path(args.json_dir)

    load_env(ENV)
    api_key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not api_key:
        print('Missing ELEVENLABS_API_KEY in environment/.env', file=sys.stderr)
        return 1

    if not files_list.exists():
        print(f'Missing input list: {files_list}', file=sys.stderr)
        return 1

    out_json_dir.mkdir(parents=True, exist_ok=True)

    rel_files = [ln.strip() for ln in files_list.read_text(encoding='utf-8').splitlines() if ln.strip()]

    rows = []
    session = requests.Session()
    headers = {'xi-api-key': api_key}

    for idx, rel in enumerate(rel_files, start=1):
        wav_path = ROOT / 'data/kaggle_911' / rel
        if not wav_path.exists():
            rows.append({'filename': rel, 'status': 'missing_file', 'transcript': ''})
            continue

        with wav_path.open('rb') as fh:
            files = {'file': (wav_path.name, fh, 'audio/wav')}
            data = {'model_id': MODEL_ID}
            try:
                resp = session.post(API_URL, headers=headers, files=files, data=data, timeout=180)
            except Exception as e:
                rows.append({'filename': rel, 'status': f'request_error:{e}', 'transcript': ''})
                continue

        status = f'http_{resp.status_code}'
        payload = {}
        try:
            payload = resp.json()
        except Exception:
            payload = {'raw': resp.text}

        json_path = out_json_dir / f"{wav_path.stem}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        transcript = get_text(payload) if resp.ok else ''
        if resp.ok and transcript:
            status = 'ok'
        elif resp.ok:
            status = 'ok_no_text'

        rows.append({'filename': rel, 'status': status, 'transcript': transcript})
        print(f"[{idx}/{len(rel_files)}] {rel} -> {status}")

    with out_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'status', 'transcript'])
        writer.writeheader()
        writer.writerows(rows)

    ok = sum(1 for r in rows if r['status'] == 'ok')
    print(f'Wrote: {out_csv} (ok={ok}/{len(rows)})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
