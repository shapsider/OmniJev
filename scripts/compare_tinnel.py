"""Same 40-per-benchmark slice used for NeoHorse, scored with tinnel OmniJev-4B."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev.paths import TINNEL_BASE, TINNEL_CKPT, TINNEL_SRC

sys.path.insert(0, str(TINNEL_SRC))
os.environ.setdefault('MSO_FLA', '0')

from scripts.benchmark_suite import case_image, suite


def main():
    datasets, cases = {}, []
    for name, builder in suite(40, 20260924).items():
        data, rows, _ = builder()
        if name == 'MMMU':
            datasets['MMMU'] = data
        elif data is not None:
            datasets[name] = data
        cases.extend(rows)
    kept, seen = [], {}
    for case in cases:
        seen[case['benchmark']] = seen.get(case['benchmark'], 0) + 1
        if seen[case['benchmark']] <= 40:
            kept.append(case)
    from mso.infer import MSO1
    model = MSO1(str(TINNEL_CKPT), str(TINNEL_BASE))
    image_path = '/tmp/omnijev-compare.png'
    rows = []
    for case in kept:
        image = case_image(datasets, case)
        image.save(image_path)
        gold = case['options'][ord(case['gold']) - 65]
        try:
            answer = model.system_one(
                {'images': [image_path]},
                {'q': {'type': 'choice', 'instructions': case['question'],
                       'criteria': {option: '' for option in case['options']}}},
            )
            choice = answer['q'].get('choice')
            ok = choice == gold
            error = None
        except Exception as exc:
            ok = False
            error = f'{type(exc).__name__}: {exc}'
        rows.append({'benchmark': case['benchmark'], 'tinnel': ok, 'error': error})
        if len(rows) % 10 == 0:
            print(len(rows), sum(r['tinnel'] for r in rows) / len(rows), flush=True)
    summary = {
        'n': len(rows),
        'tinnel': sum(r['tinnel'] for r in rows) / len(rows),
        'errors': sum(r['error'] is not None for r in rows),
    }
    path = ROOT / 'results/qwen35-suite/vs-tinnel.json'
    path.write_text(json.dumps({'summary': summary, 'rows': rows}, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
