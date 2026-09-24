"""Same held-out questions for our decision head and NeoHorse-Jev-4B."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import CHECKPOINT, MODEL, NEOHORSE

sys.path.insert(0, str(NEOHORSE / 'package' / 'src'))

from scripts.benchmark_suite import case_image, suite
from scripts.experiment_effective import load_native


def neo_request(case):
    return {
        'model': 'NeoHorse-Jev-4B',
        'state': case.get('state') or 'Look at the supplied image.',
        'questions': {
            'q': {
                'type': 'choice',
                'instructions': case['question'],
                'criteria': {option: '' for option in case['options']},
            }
        },
    }


def main():
    limit = int(os.environ.get('COMPARE_LIMIT', '40'))
    datasets, cases = {}, []
    for name, builder in suite(limit, 20260924).items():
        # suite() uses fixed sizes for some benchmarks; slice after build.
        data, rows, stats = builder()
        print(json.dumps({'benchmark': name, 'available': stats['selected']}), flush=True)
        if name == 'MMMU':
            datasets['MMMU'] = data
        elif data is not None:
            datasets[name] = data
        cases.extend(rows)
    # Keep the comparison inside one sitting: at most 40 items from each benchmark.
    kept = []
    seen = {}
    for case in cases:
        seen[case['benchmark']] = seen.get(case['benchmark'], 0) + 1
        if seen[case['benchmark']] <= 40:
            kept.append(case)
    cases = kept
    print('comparing', len(cases), flush=True)
    model, _, _ = load_native(str(MODEL), CHECKPOINT)
    model.eval()
    from neohorse_decision.vision import VisionDecisionEngine
    neo = VisionDecisionEngine(str(NEOHORSE), 'cuda')
    rows = []
    for case in cases:
        image = case_image(datasets, case)
        ours = model.decide(image, case['question'], case['options'], case.get('state', ''))
        gold = case['options'][ord(case['gold']) - 65]
        try:
            result = neo.predict(neo_request(case), image)
            choice = result['answers']['q']['choice']
            neo_ok = choice == gold
            error = None
        except Exception as exc:
            neo_ok = False
            error = f'{type(exc).__name__}: {exc}'
        rows.append({
            'benchmark': case['benchmark'],
            'ours': ours['choice'] == case['gold'],
            'neo': neo_ok,
            'error': error,
        })
        if len(rows) % 10 == 0:
            print(len(rows), 'ours', sum(r['ours'] for r in rows) / len(rows),
                  'neo', sum(r['neo'] for r in rows) / len(rows), flush=True)
    summary = {
        'n': len(rows),
        'ours': sum(r['ours'] for r in rows) / len(rows),
        'neohorse': sum(r['neo'] for r in rows) / len(rows),
        'neo_errors': sum(r['error'] is not None for r in rows),
    }
    out = ROOT / 'results/qwen35-suite/vs-neohorse.json'
    out.write_text(json.dumps({'summary': summary, 'rows': rows}, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
