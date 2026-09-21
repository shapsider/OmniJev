"""Run from repo root: python3 examples/sdk_demo.py"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omnijev import OmniJev, Policy

client=OmniJev()
result=client.decide(
    question='Is the red circle to the left of the blue square?',
    images=['data/assets/spatial0.png'],
    options=[{'id':'left','description':'Yes, the red circle is on the left'},
             {'id':'right','description':'No, the red circle is on the right'},
             {'id':'unknown','description':'Insufficient evidence','abstain':True}],
    policy=Policy(max_latency_ms=5000),request_id='spatial-demo')
print(json.dumps(result,ensure_ascii=False,indent=2))
