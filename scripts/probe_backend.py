"""Real backend checks; records actual responses, never substitutes a mock model."""
import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnijev import OmniJev


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:1234')
    parser.add_argument('--model', default='omnijev-nemotron')
    parser.add_argument('--http-url', help='Optional OmniJev HTTP service, e.g. http://127.0.0.1:8765')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; use a new path')
    client = OmniJev(model=args.model, base_url=args.base_url, timeout=180)
    options = [{'id': 'red', 'description': 'Red'}, {'id': 'blue', 'description': 'Blue'},
               {'id': 'unknown', 'description': 'Insufficient evidence', 'abstain': True}]
    request = dict(question='What color is the visible shape?', options=options,
                   images=[str(ROOT/'data/assets/red.png')])
    rows = []
    for mode in ('letter', 'json'):
        try:
            result = client.decide(**request, mode=mode)
            rows.append(dict(check='sdk_'+mode, passed=result['action']=='red' and result['status']=='decided', result=result))
        except Exception as exc:
            rows.append(dict(check='sdk_'+mode, passed=False, error=str(exc)))
    if args.http_url:
        media = base64.b64encode((ROOT/'data/assets/red.png').read_bytes()).decode()
        payload = dict(request, images=['data:image/png;base64,'+media])
        try:
            req = urllib.request.Request(args.http_url.rstrip('/')+'/decide',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.load(response)
            rows.append(dict(check='http_image', passed=result['action']=='red' and result['status']=='decided', result=result))
        except Exception as exc:
            rows.append(dict(check='http_image', passed=False, error=str(exc)))
    report = dict(model=args.model, base_url=args.base_url, checks=rows,
                  note='Small connectivity and output-contract checks, not an accuracy benchmark.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    for row in rows:
        print(row['check'], 'PASS' if row['passed'] else 'FAIL', row.get('result', row.get('error')))
    if not all(row['passed'] for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
