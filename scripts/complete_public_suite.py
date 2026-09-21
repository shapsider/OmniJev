"""Finish the sequential suite after the already running MMStar job.

This is a one-off local process, not a scheduled automation. It never runs
two inference jobs concurrently and stops if the preceding job dies.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATASETS=['mmstar-public','mmbench-public','mmad-public','streaming-public']


def count_records(path):
    if not path.exists():return 0
    return sum(1 for line in path.read_text().splitlines() if line.endswith('}'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wait-pid',type=int)
    args=parser.parse_args()
    if args.wait_pid is None:
        subprocess.run([sys.executable,str(ROOT/'scripts/public_benchmark.py')],cwd=ROOT,check=True)
    expected=4*len(json.loads((ROOT/'results/mmstar-public/manifest.json').read_text())['cases'])
    while count_records(ROOT/'results/mmstar-public/records.jsonl')<expected:
        try:os.kill(args.wait_pid,0)
        except ProcessLookupError:raise SystemExit('MMStar stopped before completion; inspect records and resume explicitly.')
        time.sleep(15)
    for name in DATASETS:
        out=ROOT/'results'/name
        if not (out/'manifest.json').exists():raise SystemExit('Missing prepared manifest: '+name)
        if name!='mmstar-public':
            subprocess.run([sys.executable,str(ROOT/'scripts/public_benchmark.py'),'--out',str(out)],cwd=ROOT,check=True)
        with (out/'summary-stdout.json').open('w') as log:
            subprocess.run([sys.executable,str(ROOT/'scripts/report_public_benchmark.py'),'--out',str(out)],cwd=ROOT,stdout=log,check=True)
        subprocess.run([str(ROOT/'.venv-eval/bin/python'),str(ROOT/'scripts/plot_public_benchmark.py'),'--out',str(out)],cwd=ROOT,check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/audit_public_results.py'),'--out',str(out)],cwd=ROOT,check=True)
        print('COMPLETE',name,flush=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/summarize_public_suite.py')],cwd=ROOT,check=True)
    print('ALL FOUR PUBLIC SUBSETS COMPLETE',flush=True)


if __name__=='__main__':main()
