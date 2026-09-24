"""Held-out mainstream multimodal decisions versus deep thinking."""
import argparse
import ast
import json
import random
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import MODEL, V3
from omnijev.tasks import select_scienceqa
from scripts.benchmark_public import image_of, mmstar_cases, realworldqa_cases, record, take_stratified
from scripts.benchmark_thinking import think
from scripts.experiment_effective import load_native

MMMU_SUBJECTS = [
    'Art', 'Art_Theory', 'Biology', 'Chemistry', 'Geography', 'Math', 'Physics', 'Psychology',
]


def ai2d_cases(limit, seed):
    from datasets import load_dataset
    dataset = load_dataset('lmms-lab/ai2d', split='test')
    rows, skipped = [], 0
    for index, row in enumerate(dataset):
        options = [str(item).strip() for item in row['options']]
        try:
            gold_index = int(row['answer'])
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not (2 <= len(options) <= 8) or len(set(options)) != len(options) or not 0 <= gold_index < len(options):
            skipped += 1
            continue
        rows.append({
            'benchmark': 'AI2D', 'index': index, 'category': 'diagram',
            'question': str(row['question']).strip(), 'options': options,
            'gold': chr(65 + gold_index), 'state': '', 'source': 'ai2d',
        })
    selected = take_stratified(rows, limit, seed) if limit else rows
    return dataset, selected, {'parsed': len(rows), 'skipped': skipped, 'selected': len(selected)}


def mmmu_cases(limit, seed):
    from datasets import load_dataset
    rows, skipped = [], 0
    datasets = {}
    for subject in MMMU_SUBJECTS:
        data = load_dataset('MMMU/MMMU', subject, split='validation')
        datasets[subject] = data
        for index, row in enumerate(data):
            images = [row.get(f'image_{i}') for i in range(1, 8)]
            images = [image for image in images if image is not None]
            raw = row['options']
            options = ast.literal_eval(raw) if isinstance(raw, str) else list(raw)
            options = [str(item).strip() for item in options]
            gold = str(row['answer']).strip().upper()
            if len(images) != 1 or not (2 <= len(options) <= 8) or len(set(options)) != len(options):
                skipped += 1
                continue
            if gold not in {chr(65 + i) for i in range(len(options))}:
                skipped += 1
                continue
            rows.append({
                'benchmark': 'MMMU', 'index': index, 'category': subject,
                'question': str(row['question']).replace('<image 1>', '').strip(),
                'options': options, 'gold': gold, 'state': '', 'source': subject,
                'subject': subject,
            })
    selected = take_stratified(rows, limit, seed)
    return datasets, selected, {'parsed': len(rows), 'skipped': skipped, 'selected': len(selected)}


def science_cases(limit, seed):
    rows = select_scienceqa('test', limit, seed)
    cases = []
    for index, row in enumerate(rows):
        cases.append({
            'benchmark': 'ScienceQA', 'index': index, 'category': 'science',
            'question': row['question'], 'options': row['options'],
            'gold': chr(65 + row['gold']), 'state': row.get('state', ''),
            'source': 'scienceqa-test', 'image': row['image'],
        })
    return None, cases, {'parsed': len(cases), 'skipped': 0, 'selected': len(cases)}


def suite(limit, seed):
    builders = {
        'MMStar': lambda: mmstar_cases(limit, seed),
        'RealWorldQA': lambda: realworldqa_sample(max(limit * 4, 160), seed),
        'AI2D': lambda: ai2d_cases(max(limit * 4, 160), seed),
        'MMMU': lambda: mmmu_cases(limit, seed),
        'ScienceQA': lambda: science_cases(max(limit * 4, 160), seed),
    }
    return builders


def realworldqa_sample(limit, seed):
    dataset, rows, stats = realworldqa_cases(0, seed)
    rng = random.Random(seed)
    rng.shuffle(rows)
    chosen = rows[:limit] if limit else rows
    stats = dict(stats, selected=len(chosen))
    return dataset, chosen, stats


def case_image(datasets, case):
    if case.get('image') is not None:
        image = case['image']
        return image.convert('RGB') if image.mode != 'RGB' else image
    if case['benchmark'] == 'MMMU':
        row = datasets['MMMU'][case['source']][case['index']]
        image = row['image_1']
        return image.convert('RGB') if image.mode != 'RGB' else image.copy()
    return image_of(datasets, case)


def prior_mmstar():
    found = {}
    directory = ROOT / 'results/qwen35-thinking'
    if not directory.exists():
        return found
    for path in directory.glob('shard-*.jsonl'):
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                found[row['index']] = row
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results/qwen35-suite')
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--seed', type=int, default=20260924)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=1)
    parser.add_argument('--max-new-tokens', type=int, default=3072)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--score-omnijev', action='store_true')
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    datasets, cases, coverage = {}, [], {}
    for name, builder in suite(args.limit, args.seed).items():
        dataset, rows, stats = builder()
        coverage[name] = stats
        if name == 'MMMU':
            datasets['MMMU'] = dataset
        elif dataset is not None:
            datasets[name] = dataset
        cases.extend(rows)
        print(json.dumps({'benchmark': name, **stats}), flush=True)
    mine = [case for index, case in enumerate(cases) if index % args.shards == args.shard]
    if args.prepare_only:
        return
    if args.score_omnijev:
        score(datasets, cases, output)
        return
    from omnijev.native import load_backbone
    backbone, processor = load_backbone(str(MODEL), 'cuda')
    backbone.eval()
    path = output / f'shard-{args.shard}.jsonl'
    done = set()
    if path.exists():
        done = {(json.loads(line)['benchmark'], json.loads(line)['index']) for line in path.read_text().splitlines() if line.strip()}
    reused = prior_mmstar()
    for offset, case in enumerate(mine):
        key = (case['benchmark'], case['index'])
        if key in done:
            continue
        if case['benchmark'] == 'MMStar' and case['index'] in reused:
            row = dict(reused[case['index']])
            with path.open('a') as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            done.add(key)
            continue
        decision = think(
            backbone, processor, case_image(datasets, case), case['question'], case['options'],
            case.get('state', ''), args.max_new_tokens)
        row = record(case, 'thinking', decision)
        with path.open('a') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(f'shard {args.shard} {offset + 1}/{len(mine)} {case["benchmark"]} correct {row["correct"]}', flush=True)


def score(datasets, cases, output):
    model, _, _ = load_native(str(MODEL), V3)
    model.eval()
    rows = []
    for path in output.glob('shard-*.jsonl'):
        rows.extend(json.loads(line) for line in path.read_text().splitlines() if line.strip())
    thought = {(row['benchmark'], row['index']): row for row in rows}
    hits = []
    for offset, case in enumerate(cases):
        key = (case['benchmark'], case['index'])
        if key not in thought:
            continue
        decision = model.decide(case_image(datasets, case), case['question'], case['options'], case.get('state', ''))
        hit = decision['choice'] == case['gold']
        hits.append({
            'benchmark': case['benchmark'], 'index': case['index'], 'category': case['category'],
            'correct': hit, 'choice': decision['choice'], 'gold': case['gold'],
            'thinking_correct': thought[key]['correct'], 'thinking_valid': thought[key]['valid'],
            'latency_seconds': decision['latency_seconds'],
        })
        if (offset + 1) % 40 == 0:
            print(f'scored {len(hits)}', flush=True)
    (output / 'omnijev.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in hits))
    print(json.dumps(summarize(hits)), flush=True)


def summarize(rows):
    from collections import defaultdict
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['benchmark']].append(row)
    report = {}
    for name, items in grouped.items():
        report[name] = {
            'n': len(items),
            'omnijev': sum(item['correct'] for item in items) / len(items),
            'thinking': sum(item['thinking_correct'] for item in items) / len(items),
            'thinking_valid': sum(item['thinking_valid'] for item in items) / len(items),
        }
    return report


if __name__ == '__main__':
    main()
