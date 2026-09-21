import argparse
import datetime
import hashlib
import json
import random
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omnijev.core import decide


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',required=True)
    p.add_argument('--base-url',default='http://127.0.0.1:1234')
    p.add_argument('--fixture',default='data/fixture.json')
    p.add_argument('--output',required=True)
    p.add_argument('--repeats',type=int,default=2)
    p.add_argument('--groups',default='')
    args=p.parse_args()
    source=Path(args.fixture).read_bytes()
    source_code_sha256=hashlib.sha256(Path(__file__).resolve().parents[1].joinpath('omnijev/core.py').read_bytes()).hexdigest()
    cases=json.loads(source)
    if args.groups:cases=[c for c in cases if c['group'] in args.groups.split(',')]
    tasks=[(r,c,m) for r in range(args.repeats) for c in cases for m in ['letter','json']]
    random.Random(20260919).shuffle(tasks)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise SystemExit('Refusing to overwrite run: '+str(out))
    # Explicit unscored warmup; no guarantee of a cold prefix after this.
    warmup=dict(id='warmup',question='What is 1+1?',options=['2','3','unknown'])
    for mode in ['letter','json']:
        decide(warmup,args.model,args.base_url,mode)
    with out.open('w') as f:
        for index,(repeat,case,mode) in enumerate(tasks):
            start=time.perf_counter()
            try:
                record=decide(case,args.model,args.base_url,mode)
                record['correct']=record['choice']==case['gold']
            except Exception as e:
                record=dict(case_id=case['id'],mode=mode,model=args.model,valid=False,correct=False,
                            error=str(e),latency_seconds=time.perf_counter()-start)
            record.update(repeat=repeat,case=case,fixture_sha256=hashlib.sha256(source).hexdigest(),
                          core_sha256=source_code_sha256,
                          timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
            f.write(json.dumps(record)+'\n');f.flush()
            print(f'{index+1}/{len(tasks)} {case["id"]} {mode}: '+str(record.get('choice',record.get('error')))+f' [{record["latency_seconds"]:.2f}s]',flush=True)


if __name__=='__main__':main()
