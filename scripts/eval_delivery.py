"""Accuracy of decisions the caller is allowed to execute."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import MODEL, V3

from scripts.benchmark_suite import case_image, suite
from scripts.experiment_effective import load_native

MARGINS = (0.05, 0.10, 0.15, 0.20, 0.30)


def main():
    output = ROOT / 'results/qwen35-suite'
    datasets, cases = {}, []
    for name, builder in suite(40, 20260924).items():
        dataset, rows, stats = builder()
        print(json.dumps({'benchmark': name, **stats}), flush=True)
        if name == 'MMMU':
            datasets['MMMU'] = dataset
        elif dataset is not None:
            datasets[name] = dataset
        cases.extend(rows)
    model, _, _ = load_native(str(MODEL), V3)
    model.eval()
    rows = []
    for case in cases:
        decision = model.decide(case_image(datasets, case), case['question'], case['options'], case.get('state', ''), margin=0.0)
        rows.append({
            'benchmark': case['benchmark'],
            'correct': decision['choice'] == case['gold'],
            'margin': decision['margin'],
            'latency_seconds': decision['latency_seconds'],
        })
        if len(rows) % 80 == 0:
            print(f'scored {len(rows)}', flush=True)
    summary = {'n': len(rows), 'always': sum(r['correct'] for r in rows) / len(rows), 'margins': {}}
    for margin in MARGINS:
        acted = [r for r in rows if r['margin'] >= margin]
        summary['margins'][str(margin)] = {
            'coverage': len(acted) / len(rows),
            'accuracy': (sum(r['correct'] for r in acted) / len(acted)) if acted else None,
        }
    (output / 'delivery.json').write_text(json.dumps({'summary': summary, 'rows': rows}))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
