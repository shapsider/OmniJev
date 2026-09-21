"""Static research plots from the saved summary (matplotlib optional)."""
import json
import os
import argparse
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', '/tmp/omnijev-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--out',default='results/mmstar-public')
args=parser.parse_args()
OUT=ROOT/args.out
s=json.loads((OUT/'summary.json').read_text())
if s['completed_requests']!=s['expected_requests']:
    raise SystemExit('Refusing to plot incomplete, unmatched method samples. Finish all requests first.')
methods=['omnijev','direct','json','reasoning']
names=['OmniJev','Direct label','JSON','Reasoning (medium)']
colors=['#087f8c','#6096ba','#9ba7b3','#df8e36']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,4,figsize=(16,4.5))
for ax,key,title,unit in zip(axes,
        ['accuracy','latency_p50','completion_tokens_mean','total_tokens_mean'],
        ['Answer accuracy','End-to-end median latency','Mean generated tokens','Mean total tokens'],
        ['Percent','Seconds','Tokens (including reasoning)','Input + generated tokens']):
    vals=[s['methods'][m][key] for m in methods]
    bars=ax.bar(names,vals,color=colors,width=.65)
    ax.set_title(title)
    ax.set_ylabel(unit)
    ax.tick_params(axis='x',rotation=20)
    ax.bar_label(bars,labels=[f'{v:.2f}' for v in vals],padding=4)
    if key=='accuracy':ax.set_ylim(0,105)
    else:ax.set_ylim(0,max(vals)*1.22)
fig.suptitle(f'{s["dataset"]} | {s["expected_cases"]} cases | Nemotron 3 Nano Omni Q4_K_M')
fig.text(.5,.015,'Local sequential requests; natural cache; loading excluded. Bionic medium: observed ~8k reasoning budget; T=0.6, top_p=0.95.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.04,1,.93))
fig.savefig(OUT/'comparison.png',dpi=180)
fig.savefig(OUT/'comparison.pdf')
plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4.5))
for m,name,color in zip(methods,names,colors):
    d=s['methods'][m]['timely_accuracy']
    xs=sorted(map(float,d))
    ax.plot(xs,[d[str(x) if str(x) in d else str(int(x))] for x in xs],marker='o',label=name,color=color)
ax.set_xscale('log')
ax.set_xlabel('Response deadline (seconds, log scale)')
ax.set_ylabel('Correct and on-time / all requests (%)')
ax.set_ylim(0,100)
ax.set_title(f'{s["dataset"]} | {s["expected_cases"]} cases\nResponse deadline sensitivity (prepared media)')
ax.legend()
fig.tight_layout()
fig.savefig(OUT/'deadline.png',dpi=180)
fig.savefig(OUT/'deadline.pdf')
