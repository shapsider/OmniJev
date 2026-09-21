"""Seeded, resumable real-physics benchmark. Each episode has its own process.

No oracle replaces failed model decisions. Skills, RGB-D and direct vision are
different protocols; never pool their success rates. The UI reads summary.json.
"""
import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import sys
import time
import platform

ROOT = Path(__file__).resolve().parents[1]


def git_revision():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def write(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    tmp.replace(path)


def summarize(out, protocol, rows, expected):
    methods = {}
    for provider in protocol['providers']:
        rs = [r for r in rows if r['provider'] == provider]
        latencies = sorted(x for r in rs for x in r.get('model_latency_ms', []))
        def percentile(p):
            if not latencies:return None
            rank=(len(latencies)-1)*p;lo=int(rank);hi=min(lo+1,len(latencies)-1)
            return latencies[lo]+(latencies[hi]-latencies[lo])*(rank-lo)
        methods[provider] = {'n':len(rs),'successes':sum(r['success'] for r in rs),
            'wall_seconds_mean':statistics.mean(r['wall_seconds'] for r in rs) if rs else None,
            'model_calls':sum(r.get('model_calls',0) for r in rs),
            'request_latency_ms_p50':percentile(.5),
            'request_latency_ms_p95':percentile(.95),
            'input_tokens_known':sum(r.get('input_tokens',0) for r in rs),
            'output_tokens_known':sum(r.get('output_tokens',0) for r in rs),
            'usage_incomplete_episodes':sum(not r.get('usage_complete',False) for r in rs),
            'forbidden_contact_steps':sum(r.get('forbidden_contact_steps',0) for r in rs),
            'failures':dict(collections.Counter(r['status'] for r in rs if not r['success']))}
    write(out/'summary.json', {'status':'complete' if len(rows)==expected else 'partial',
        'completed_episodes':len(rows),'expected_episodes':expected,'protocol':protocol,'methods':methods,
        'note':'固定仿真先导实验；技能模式含程序轨迹，非端到端视觉控制。失败保留；tokens 为已知用量，usage_incomplete_episodes 标记用量不完整回合。回合耗时包含物理执行与模型等待，不含进程启动和初始建场。'})


def partial_usage(path):
    """Retain known cost even when a child dies before exporting its episode."""
    attempts=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try:attempts.append(json.loads(line))
            except json.JSONDecodeError:continue  # An interrupted final write.
    return {'model_calls':len(attempts),
        'input_tokens':sum((r.get('usage') or {}).get('prompt_tokens',0) for r in attempts),
        'output_tokens':sum((r.get('usage') or {}).get('completion_tokens',0) for r in attempts),
        'model_latency_ms':[r['latency_ms'] for r in attempts if 'latency_ms' in r],
        'usage_complete':False, 'cost_note':'Known lower bound; an interrupted in-flight request may be unrecorded.'}


def episode(config, out):
    from embodied_jev.runtime import run_headless
    cameras = ['external','wrist'] if config['observation'] == 'vision' else ['external'] if config['observation']=='rgbd' else []
    session = run_headless(config['task'], config['seed'], provider=config['provider'],
        threshold=0, max_cycles=config['max_cycles'], timeout=config['timeout'],
        observation_mode=config['observation'], control_mode=config['control'],
        camera_views=cameras, intervention=config['intervention'], shuffle_candidates=True)
    exported = session.export()
    write(out, exported)
    if cameras:(out.with_suffix('.cameras.zip')).write_bytes(session.camera_archive())
    attempts = exported.get('omnijev_requests', [])
    row = {k:config[k] for k in ('task','seed','provider')}
    row.update(status=session.status, success=session.status=='completed' and exported['success'],
        wall_seconds=exported['wall_seconds'], model_calls=exported['model_calls'],
        input_tokens=exported['input_tokens'], output_tokens=exported['output_tokens'],
        usage_complete=(config['provider']=='baseline' or bool(attempts) and all(r.get('usage_complete',False) for r in attempts)),
        cycles=session.cycles, forbidden_contact_steps=session.world.unsafe_contacts,
        model=exported['model'],scene_hash=exported['scene_hash'],message=exported['message'],
        model_latency_ms=exported['model_latency_ms'], episode_file=out.name)
    write(out.with_suffix('.row.json'), row)
    if session.worker.is_alive():raise TimeoutError('Worker still active; stop benchmark before another episode')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--providers',nargs='+',choices=['baseline','omnijev','omni_direct','omni_reasoning','omni_adaptive'],default=['baseline','omnijev','omni_direct','omni_reasoning'])
    p.add_argument('--tasks',nargs='+',choices=['transfer','stack','barrier'],default=['transfer','stack','barrier'])
    p.add_argument('--seeds',nargs='+',type=int,default=[0,1,2])
    p.add_argument('--observation',choices=['privileged','rgbd','vision'],default='privileged')
    p.add_argument('--control',choices=['skills','incremental'],default='skills')
    p.add_argument('--max-cycles',type=int,default=20)
    p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--reasoning-tokens',type=int,default=4096)
    p.add_argument('--intervention',type=json.loads,default=None)
    p.add_argument('--output',type=Path,default=ROOT/'results/embodied/local-pilot')
    p.add_argument('--episode-config',type=Path,help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.episode_config:
        episode(json.loads(args.episode_config.read_text()), args.output)
        return
    if args.observation=='vision' and (args.control!='incremental' or 'baseline' in args.providers):
        p.error('Vision requires --control incremental and model providers (baseline uses privileged state).')
    if args.max_cycles<1 or args.reasoning_tokens<4 or args.timeout<=0:p.error('Budgets must be positive')
    if any(not 0<=s<=99999 for s in args.seeds):p.error('Seeds must be 0–99999')
    for items in (args.providers,args.tasks,args.seeds):
        if len(set(items))!=len(items):p.error('Duplicate provider, task or seed')
    from embodied_jev.runtime import validate_intervention
    args.intervention = validate_intervention(args.intervention)
    from omnijev.embodied_policy import connection
    cfg = connection()
    protocol = {k:getattr(args,k) for k in ('providers','tasks','seeds','observation','control','max_cycles','timeout','reasoning_tokens','intervention')}
    protocol.update(model=cfg['model'], endpoint=cfg['url'], threshold=0, shuffle_candidates=True,
        project_revision=git_revision(),
        python_version=platform.python_version(), platform=platform.platform(),
        adapter_sha256=hashlib.sha256((ROOT/'omnijev/embodied_policy.py').read_bytes()).hexdigest(),
        timing='session wall time; includes policy, previews and physics; no model loading; natural backend cache')
    out = args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest = out/'manifest.json'
    if manifest.exists() and json.loads(manifest.read_text())['protocol']!=protocol:
        p.error('Existing run uses another protocol. Use a new output directory.')
    if not manifest.exists():write(manifest,{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol':protocol})
    rows = [json.loads(s) for s in (out/'episodes.jsonl').read_text().splitlines()] if (out/'episodes.jsonl').exists() else []
    done={(r['task'],r['seed'],r['provider']) for r in rows}
    if len(done)!=len(rows):raise ValueError('Duplicate saved episode')
    jobs=[(t,s,m) for t in args.tasks for s in args.seeds for m in args.providers]
    random.Random(20260921).shuffle(jobs)
    summarize(out,protocol,rows,len(jobs))
    for task,seed,provider in jobs:
        if (task,seed,provider) in done:continue
        stem=f'{task}-{seed}-{provider}'
        config=out/(stem+'.config.json');target=out/(stem+'.json')
        write(config,{**protocol,'task':task,'seed':seed,'provider':provider})
        env={**os.environ,'OMNIJEV_REASONING_TOKENS':str(args.reasoning_tokens),'OMNIJEV_REQUEST_LOG':str(out/(stem+'.requests.jsonl'))}
        start=time.perf_counter();failure=None
        with (out/(stem+'.log')).open('w') as log:
            try:
                result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--episode-config',str(config),'--output',str(target)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=args.timeout+30)
                if result.returncode:failure='process_error'
            except subprocess.TimeoutExpired:failure='process_timeout'
        row_path=target.with_suffix('.row.json')
        if row_path.exists():row=json.loads(row_path.read_text())
        else:
            row=dict(task=task,seed=seed,provider=provider,status=failure or 'missing_result',success=False,
                wall_seconds=time.perf_counter()-start,usage_complete=False,episode_file=None)
            row.update(partial_usage(out/(stem+'.requests.jsonl')))
        if failure:row.update(status=failure,success=False)
        rows.append(row)
        with (out/'episodes.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        summarize(out,protocol,rows,len(jobs))
        print(f'{len(rows)}/{len(jobs)} {stem}: {row["status"]}, success={row["success"]}, {row["wall_seconds"]:.2f}s',flush=True)
        if failure:raise SystemExit('Infrastructure failure retained; inspect log before resuming.')
    print('Completed '+str(out/'summary.json'),flush=True)


if __name__=='__main__':main()
