"""Real-model acceptance suite. Uses SDK contracts and retains every response."""
import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omnijev import OmniJev

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',default='omnijev-nemotron')
    p.add_argument('--base-url',default='http://127.0.0.1:1234')
    p.add_argument('--output',default='results/acceptance-v02.jsonl');args=p.parse_args()
    out=Path(args.output)
    if out.exists():raise SystemExit('Output exists; choose a new --output')
    client=OmniJev(args.model,args.base_url)
    cases=[]
    for name in ['fixture','stress']:
        cases.extend(c for c in json.loads(Path(f'data/{name}.json').read_text()) if not c.get('audio'))
    route=json.loads(Path('examples/request.json').read_text())
    extra=[('退款申请：收到的杯子破损了，希望退货退款。','refund'),
           ('包裹显示已发货，但我不知道预计什么时候送达。','delivery'),
           ('软件启动时出现错误代码，无法进入主界面。','technical'),
           ('你好，祝你周末愉快。','unknown')]
    jobs=[]
    for c in cases:
        opts=[dict(id=f'option_{i}',description=d,abstain=d=='insufficient evidence') for i,d in enumerate(c['options'])]
        gold=opts[ord(c['gold'])-65]
        jobs.append((dict(question=c['question'],options=opts,images=c.get('images',[]),state=c.get('state',''),request_id=c['id']),gold['id'],gold['abstain']))
    for i,(state,gold) in enumerate(extra):
        jobs.append((dict(question=route['question'],options=route['options'],state=state,request_id=f'route-{i}'),gold,gold=='unknown'))
    rows=[]
    with out.open('w') as f:
        for request,gold,abstain in jobs:
            try:
                r=client.decide(**request)
                passed=r['selected']==gold and r['status']==('abstained' if abstain else 'decided')
            except Exception as e:r={'request_id':request['request_id'],'error':str(e)};passed=False
            row=dict(result=r,passed=passed,expected=gold,expected_abstention=abstain,
                     request=request,timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat())
            rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
            print(f'{request["request_id"]}: {"PASS" if passed else "FAIL"} {r.get("selected",r.get("error"))}',flush=True)
    latencies=[r['result']['elapsed_ms'] for r in rows if 'elapsed_ms' in r['result']]
    summary=dict(total=len(rows),passed=sum(r['passed'] for r in rows),
                 median_ms=statistics.median(latencies) if latencies else None,
                 note='Synthetic diagnostics plus four authored text messages; not broad real-world accuracy.')
    out.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
    if not all(r['passed'] for r in rows):raise SystemExit(1)

if __name__=='__main__':main()
