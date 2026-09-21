"""Reproducible MMStar pilot; paired frozen-model comparisons, no training."""
import argparse
import base64
import collections
import csv
import datetime
import hashlib
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.core import decide, messages, post

SEED = 20260920
METHODS = ['omnijev', 'direct', 'json', 'reasoning']


def prepare(source, per_category, out):
    csv.field_size_limit(100000000)
    with source.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row['category']].append(row)
    rng = random.Random(SEED)
    selected = []
    media = out / 'images'
    media.mkdir(parents=True, exist_ok=True)
    for category in sorted(groups):
        for row in rng.sample(groups[category], per_category):
            blob = base64.b64decode(row['image'], validate=True)
            extension = '.png' if blob.startswith(b'\x89PNG') else '.jpg'
            path = media / (row['index'] + extension)
            path.write_bytes(blob)
            selected.append(dict(id='mmstar-' + row['index'], category=category,
                subcategory=row['l2_category'], origin=row['bench'],
                question=row['question'], options=['Option ' + x + ' in the question' for x in 'ABCD'],
                images=[str(path.resolve())], gold=row['answer'],
                image_sha256=hashlib.sha256(blob).hexdigest()))
    manifest = dict(dataset='MMStar', source='https://huggingface.co/datasets/Lin-Chen/MMStar',
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), seed=SEED,
        per_category=per_category, cases=selected,
        protocol=dict(methods=METHODS, model='omnijev-nemotron', temperature=0,
            thinking_max_tokens=8192, direct_max_tokens=4, json_max_tokens=32,
            sampling='uniform within six top-level categories; fixed before inference',
            cache='natural server cache, globally shuffled requests; not a controlled cold-cache benchmark',
            noninferiority_margin_pp=2, bootstrap_cluster='image_sha256',
            timing='client wall time including media encoding, HTTP and output parsing; model load excluded'))
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def run_case(case, method):
    start = time.perf_counter()
    if method in ('omnijev', 'json'):
        record = decide(case, 'omnijev-nemotron', mode='letter' if method == 'omnijev' else 'json', timeout=240)
    else:
        payload = dict(model='omnijev-nemotron', messages=messages(case, 'letter'),
            temperature=0, seed=20260919, reasoning_effort='medium' if method == 'reasoning' else 'none',
            max_tokens=8192 if method == 'reasoning' else 4)
        response = post('http://127.0.0.1:1234', payload, timeout=240)
        choice = response['choices'][0]
        msg = choice['message']
        raw = msg.get('content') or ''
        selected = raw.strip() if raw.strip() in 'ABCD' and len(raw.strip()) == 1 else None
        reasoning = msg.get('reasoning_content') or msg.get('reasoning') or ''
        if method == 'direct' and reasoning:
            selected = None
        record = dict(choice=selected, valid=selected is not None, raw_text=raw,
            reasoning_detected=bool(reasoning), response=response, usage=response.get('usage'),
            request_config={k:v for k,v in payload.items() if k != 'messages'},
            messages_sha256=hashlib.sha256(json.dumps(payload['messages'],sort_keys=True).encode()).hexdigest())
    record['wall_seconds'] = time.perf_counter() - start
    record['finish_reason'] = record['response']['choices'][0].get('finish_reason')
    record['correct'] = record.get('choice') == case['gold']
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--per-category', type=int, default=50)
    p.add_argument('--out', default='results/mmstar-public')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--limit', type=int)
    args = p.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else prepare(ROOT/'data/MMStar.tsv', args.per_category, out)
    if args.prepare_only:
        print(f'Prepared {len(manifest["cases"])} cases', flush=True)
        return
    with urllib.request.urlopen('http://127.0.0.1:1234/api/v1/models') as f:
        (out/'backend.json').write_bytes(f.read())
    (out/'runner.sha256').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    tasks = [(case, method) for case in manifest['cases'] for method in METHODS]
    random.Random(SEED).shuffle(tasks)
    output = out/'records.jsonl'
    done = set()
    if output.exists():
        for line in output.read_text().splitlines():
            row = json.loads(line)
            done.add((row['case_id'], row['method']))
    count = 0
    with output.open('a') as f:
        for case, method in tasks:
            if (case['id'], method) in done:
                continue
            start = time.perf_counter()
            try:
                record = run_case(case, method)
            except Exception as e:
                record = dict(correct=False, valid=False, error=str(e), wall_seconds=time.perf_counter()-start)
            record.update(case_id=case['id'], method=method, category=case['category'], gold=case['gold'],
                image_sha256=case['image_sha256'], timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
            f.write(json.dumps(record, ensure_ascii=False)+'\n')
            f.flush()
            count += 1
            print(f'{len(done)+count}/{len(tasks)} {case["id"]} {method}: {record.get("choice")} gold={case["gold"]} {record["wall_seconds"]:.2f}s {record.get("error", "")}', flush=True)
            if record.get('error'):
                raise SystemExit('Stopped on transport/backend error; inspect before resuming.')
            if args.limit and count >= args.limit:
                break


if __name__ == '__main__':
    main()
