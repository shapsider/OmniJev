import collections
import json
import statistics
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omnijev.core import candidate_scores

rows=[]
for filename in sys.argv[1:]:
    for line in Path(filename).read_text().splitlines():
        r=json.loads(line);r['source']=filename
        if r.get('response') and r['mode']=='letter':
            labels=[chr(65+i) for i in range(len(r['case']['options']))]
            r['scores']=candidate_scores(r['response']['choices'][0].get('logprobs'),labels)
        rows.append(r)
groups=collections.defaultdict(list)
for r in rows:groups[(r['source'],r['mode'],r['case']['group'])].append(r)
summary=[]
for (source,mode,group),rs in sorted(groups.items()):
    succeeded=[r for r in rs if not r.get('error')]
    entry=dict(source=source,mode=mode,group=group,requests=len(rs),
               unique_cases=len({r['case_id'] for r in rs}),api_errors=len(rs)-len(succeeded),
               valid=sum(r.get('valid',False) for r in rs),correct=sum(r.get('correct',False) for r in rs),
               median_seconds=statistics.median(r['latency_seconds'] for r in succeeded) if succeeded else None,
               complete_scores=sum(r.get('scores',{}).get('status')=='complete_candidate_set' for r in rs))
    summary.append(entry)
Path('results/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
Path('results/scored-records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
print(json.dumps(summary,indent=2))
