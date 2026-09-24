"""One forward, then the stored deep-thinking answer only when the lead is small."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import CHECKPOINT, MODEL

from scripts.benchmark_suite import case_image, suite
from scripts.experiment_effective import load_native

FLOORS = (0.3, 0.5, 0.7, 0.9, 1.01)


def thinking_table():
    found = {}
    for path in (ROOT / 'results/qwen35-suite').glob('shard-*.jsonl'):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            found[(row['benchmark'], row.get('category'), row['index'])] = row
    return found


def main():
    thought = thinking_table()
    datasets, cases = {}, []
    for name, builder in suite(40, 20260924).items():
        data, rows, stats = builder()
        print(json.dumps({'benchmark': name, **stats}), flush=True)
        if name == 'MMMU':
            datasets['MMMU'] = data
        elif data is not None:
            datasets[name] = data
        cases.extend(rows)
    model, _, _ = load_native(str(MODEL), CHECKPOINT)
    model.eval()
    rows = []
    for case in cases:
        decision = model.decide(case_image(datasets, case), case['question'], case['options'], case.get('state', ''))
        key = (case['benchmark'], case['category'], case['index'])
        prior = thought[key]
        rows.append({
            'benchmark': case['benchmark'],
            'fast_correct': decision['choice'] == case['gold'],
            'margin': decision['margin'],
            'fast_latency': decision['latency_seconds'],
            'think_correct': bool(prior['correct']),
            'think_valid': bool(prior['valid']),
            'think_choice': prior.get('choice'),
            'think_latency': prior.get('latency_seconds') or 0.0,
            'gold': case['gold'],
        })
        if len(rows) % 80 == 0:
            print(f'scored {len(rows)}', flush=True)
    fast = sum(r['fast_correct'] for r in rows) / len(rows)
    slow = sum(r['think_correct'] for r in rows) / len(rows)
    report = {'n': len(rows), 'one_forward': fast, 'always_thinking': slow, 'floors': {}}
    for floor in FLOORS:
        correct = escalated = latency = 0.0
        for row in rows:
            use_thought = row['margin'] < floor and row['think_valid']
            if use_thought:
                hit = row['think_choice'] == row['gold']
                escalated += 1
                latency += row['fast_latency'] + row['think_latency']
            else:
                hit = row['fast_correct']
                latency += row['fast_latency']
            correct += hit
        report['floors'][str(floor)] = {
            'accuracy': correct / len(rows),
            'escalated': escalated / len(rows),
            'mean_latency': latency / len(rows),
        }
    path = ROOT / 'results/qwen35-suite/cascade.json'
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
