import argparse
import json
from pathlib import Path
from .core import decide

p=argparse.ArgumentParser(description='OmniJev: frozen local model, finite-choice decisions')
p.add_argument('--model',default='omnijev-nemotron')
p.add_argument('--base-url',default='http://127.0.0.1:1234')
p.add_argument('--question')
p.add_argument('--options',nargs='+')
p.add_argument('--image',action='append',default=[])
p.add_argument('--audio',action='append',default=[])
p.add_argument('--state',default='')
p.add_argument('--case',help='JSON file containing one case')
p.add_argument('--mode',choices=['letter','json'],default='letter')
p.add_argument('--output')
args=p.parse_args()
if args.case:
    case=json.loads(Path(args.case).read_text())
else:
    if not args.question or not args.options:p.error('--question and --options are required')
    case=dict(question=args.question,options=args.options,images=args.image,audio=args.audio,state=args.state)
result=decide(case,args.model,args.base_url,args.mode)
display={k:v for k,v in result.items() if k!='response'}
print(json.dumps(display,ensure_ascii=False,indent=2))
if args.output:Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
