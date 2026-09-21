"""Audit complete public runs against frozen inputs and API accounting."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omnijev.core import messages


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True)
    args=p.parse_args()
    out=ROOT/args.out
    manifest=json.loads((out/'manifest.json').read_text())
    cases={c['id']:c for c in manifest['cases']}
    rows=[json.loads(s) for s in (out/'records.jsonl').read_text().splitlines()]
    expected={(key,m) for key in cases for m in ('omnijev','direct','json','reasoning')}
    actual=[(r['case_id'],r['method']) for r in rows]
    assert len(actual)==len(set(actual)), 'Duplicate requests'
    assert set(actual)==expected, 'Missing or unexpected requests'
    hashes={}
    for c in cases.values():
        for mode in ('letter','json'):
            hashes[c['id'],mode]=hashlib.sha256(json.dumps(messages(c,mode),sort_keys=True).encode()).hexdigest()
    for r in rows:
        c=cases[r['case_id']]
        assert r['gold']==c['gold']
        assert r['correct']==(r.get('choice')==c['gold'])
        assert r['wall_seconds']>=0
        if 'error' in r:continue
        mode='json' if r['method']=='json' else 'letter'
        assert r['messages_sha256']==hashes[c['id'],mode], 'Prompt changed'
        usage=r['usage']
        assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
        assert usage.get('completion_tokens_details',{}).get('reasoning_tokens',0)<=usage['completion_tokens']
        assert r['request_config']['temperature']==(0.6 if r['method']=='reasoning' else 0)
        if r['method']=='reasoning':assert r['request_config']['top_p']==0.95
        assert r['request_config']['seed']==20260919
        expected_cap={'omnijev':4,'direct':4,'json':32,'reasoning':20480}[r['method']]
        assert r['request_config']['max_tokens']==expected_cap
        assert usage['completion_tokens']<=expected_cap
    result=dict(dataset=manifest['dataset'],requests=len(rows),cases=len(cases),
        duplicate_requests=False,all_expected_requests_present=True,
        prompt_hashes_verified=True,token_accounting_verified=True,
        errors=sum('error' in r for r in rows))
    (out/'audit.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
