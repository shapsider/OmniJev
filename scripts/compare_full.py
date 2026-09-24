"""Full held-out comparison: our v4, NeoHorse-Jev-4B, and tinnel OmniJev-4B."""
import json
import os
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import CHECKPOINT, MODEL, NEOHORSE, TINNEL_BASE, TINNEL_CKPT, TINNEL_SRC

sys.path.insert(0, str(NEOHORSE / 'package' / 'src'))
sys.path.insert(0, str(TINNEL_SRC))
os.environ.setdefault('MSO_FLA', '0')

from scripts.benchmark_suite import case_image, suite

OUT = ROOT / 'results/qwen35-suite/vs-full'
IMAGE = Path('/tmp/omnijev-compare-full.png')


def build():
    datasets, cases = {}, []
    for name, builder in suite(40, 20260924).items():
        data, rows, stats = builder()
        print(json.dumps({'benchmark': name, **stats}), flush=True)
        if name == 'MMMU':
            datasets['MMMU'] = data
        elif data is not None:
            datasets[name] = data
        cases.extend(rows)
    return datasets, cases


def gold_text(case):
    return case['options'][ord(case['gold']) - 65]


def done_keys(path):
    found = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                found.add((row['benchmark'], row['category'], row['index']))
    return found


def append(path, row):
    with path.open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def score_ours(datasets, cases, path):
    from scripts.experiment_effective import load_native
    model, _, _ = load_native(
        str(MODEL), CHECKPOINT)
    model.eval()
    finished = done_keys(path)
    for offset, case in enumerate(cases):
        key = (case['benchmark'], case['category'], case['index'])
        if key in finished:
            continue
        decision = model.decide(case_image(datasets, case), case['question'], case['options'], case.get('state', ''))
        append(path, {
            'benchmark': case['benchmark'], 'category': case['category'], 'index': case['index'],
            'correct': decision['choice'] == case['gold'], 'latency': decision['latency_seconds'],
        })
        if (offset + 1) % 40 == 0:
            print(f'ours {offset + 1}/{len(cases)}', flush=True)
    del model
    torch.cuda.empty_cache()


def score_neo(datasets, cases, path):
    from neohorse_decision.vision import VisionDecisionEngine
    engine = VisionDecisionEngine(str(NEOHORSE), 'cuda')
    finished = done_keys(path)
    for offset, case in enumerate(cases):
        key = (case['benchmark'], case['category'], case['index'])
        if key in finished:
            continue
        request = {
            'model': 'NeoHorse-Jev-4B',
            'state': case.get('state') or 'Look at the supplied image.',
            'questions': {'q': {
                'type': 'choice', 'instructions': case['question'],
                'criteria': {option: '' for option in case['options']},
            }},
        }
        try:
            result = engine.predict(request, case_image(datasets, case))
            correct = result['answers']['q']['choice'] == gold_text(case)
            error = None
        except Exception as exc:
            correct = False
            error = f'{type(exc).__name__}: {exc}'
        append(path, {
            'benchmark': case['benchmark'], 'category': case['category'], 'index': case['index'],
            'correct': correct, 'error': error,
        })
        if (offset + 1) % 20 == 0:
            print(f'neo {offset + 1}/{len(cases)}', flush=True)
    del engine
    torch.cuda.empty_cache()


def score_tinnel(datasets, cases, path):
    from mso.infer import MSO1
    model = MSO1(str(TINNEL_CKPT), str(TINNEL_BASE))
    finished = done_keys(path)
    for offset, case in enumerate(cases):
        key = (case['benchmark'], case['category'], case['index'])
        if key in finished:
            continue
        case_image(datasets, case).save(IMAGE)
        try:
            answer = model.system_one(
                {'images': [str(IMAGE)]},
                {'q': {'type': 'choice', 'instructions': case['question'],
                       'criteria': {option: '' for option in case['options']}}},
            )
            correct = answer['q'].get('choice') == gold_text(case)
            error = None
        except Exception as exc:
            correct = False
            error = f'{type(exc).__name__}: {exc}'
        append(path, {
            'benchmark': case['benchmark'], 'category': case['category'], 'index': case['index'],
            'correct': correct, 'error': error,
        })
        if (offset + 1) % 20 == 0:
            print(f'tinnel {offset + 1}/{len(cases)}', flush=True)


def summarize(paths):
    from collections import defaultdict
    tables = {}
    for name, path in paths.items():
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['benchmark']].append(bool(row['correct']))
        tables[name] = {
            'n': len(rows),
            'accuracy': sum(bool(row['correct']) for row in rows) / len(rows),
            'errors': sum(row.get('error') is not None for row in rows),
            'by': {key: sum(flags) / len(flags) for key, flags in grouped.items()},
        }
    return tables


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    datasets, cases = build()
    print('cases', len(cases), flush=True)
    ours, neo, tinnel = OUT / 'ours.jsonl', OUT / 'neohorse.jsonl', OUT / 'tinnel.jsonl'
    print('scoring ours', flush=True)
    score_ours(datasets, cases, ours)
    print('scoring neohorse', flush=True)
    score_neo(datasets, cases, neo)
    print('scoring tinnel', flush=True)
    score_tinnel(datasets, cases, tinnel)
    report = summarize({'ours': ours, 'neohorse': neo, 'tinnel': tinnel})
    (OUT / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
