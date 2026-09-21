"""Accounting contract for incomplete and failed evaluation episodes."""
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('omni_benchmark',Path(__file__).resolve().parents[2]/'scripts/benchmark_embodied.py')
benchmark=importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_failed_process_retains_known_usage(tmp_path):
    p=tmp_path/'requests.jsonl'
    p.write_text(json.dumps({'usage':{'prompt_tokens':123,'completion_tokens':9},'latency_ms':42})+'\n{"interrupted":')
    cost=benchmark.partial_usage(p)
    assert cost['input_tokens']==123 and cost['output_tokens']==9
    assert cost['model_calls']==1 and not cost['usage_complete']


def test_summary_keeps_failure_denominator_and_missing_usage(tmp_path):
    rows=[{'provider':'omnijev','success':True,'status':'completed','wall_seconds':1,
           'model_calls':1,'input_tokens':100,'output_tokens':3,'usage_complete':True,'model_latency_ms':[100]},
          {'provider':'omnijev','success':False,'status':'process_timeout','wall_seconds':10,
           'model_calls':1,'input_tokens':200,'output_tokens':8,'usage_complete':False,'model_latency_ms':[300]}]
    benchmark.summarize(tmp_path,{'providers':['omnijev']},rows,2)
    s=json.loads((tmp_path/'summary.json').read_text());m=s['methods']['omnijev']
    assert s['status']=='complete' and m['successes']==1 and m['n']==2
    assert m['input_tokens_known']==300 and m['usage_incomplete_episodes']==1
    assert m['request_latency_ms_p50']==200 and m['failures']=={'process_timeout':1}
