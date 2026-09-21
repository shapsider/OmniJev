"""Summarize paired public benchmark records without dropping failures."""
import collections
import argparse
import json
import math
import random
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/mmstar-public'
METHODS = ['omnijev', 'direct', 'json', 'reasoning']


def semantic_choice(record, labels):
    """Normalize explicit final answers only; never inspect hidden reasoning."""
    if record.get('choice') in labels:return record['choice']
    raw=record.get('raw_text') or ''
    if record.get('method')=='json':
        try:
            obj=json.loads(raw)
            if isinstance(obj,dict) and obj.get('choice') in labels:return obj['choice']
        except (ValueError,TypeError):pass
    lines=[line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:return None
    last=lines[-1].replace('**','').replace('`','').strip()
    patterns=[r'\(?([A-Z])\)?[.]?',
        r'(?:Final\s+answer|Answer|The\s+correct\s+(?:answer|option)|Option)(?:\s+is)?\s*[:=]?\s*\(?([A-Z])\)?[.]?',
        r'\$?\\boxed\{([A-Z])\}\$?']
    for pattern in patterns:
        match=re.fullmatch(pattern,last,flags=re.IGNORECASE)
        if match and match[1].upper() in labels:return match[1].upper()
    return None


def budget_forced(record):
    response=record.get('response') or {}
    choices=response.get('choices') or []
    reasoning=(choices[0].get('message',{}).get('reasoning_content') or '') if choices else ''
    tokens=(record.get('usage') or {}).get('completion_tokens_details',{}).get('reasoning_tokens',0) or 0
    return tokens>=8000 and 'I have to answer now.' in reasoning


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    pos = (len(values)-1)*q
    lo = int(pos)
    return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(pos-lo)


def paired_interval(pairs):
    clusters = collections.defaultdict(list)
    for a, b in pairs:
        clusters[a['image_sha256']].append(int(a['correct'])-int(b['correct']))
    groups = list(clusters.values())
    if not groups:
        return None
    rng = random.Random(20260920)
    means = []
    for _ in range(10000):
        sample = [groups[rng.randrange(len(groups))] for _ in groups]
        means.append(100*sum(map(sum,sample))/sum(map(len,sample)))
    return [quantile(means,.025), quantile(means,.975)]


def conservative_paired_interval(pairs):
    """Bonferroni Clopper-Pearson bounds on win/loss probabilities.

    Valid for independent images; avoids degenerate bootstrap intervals when
    all observed paired outcomes agree. Four tails each use alpha/4.
    """
    n = len(pairs)
    if len({a['image_sha256'] for a,b in pairs}) != n:
        return None
    def solve(k, target):
        lo, hi = 0., 1.
        for _ in range(60):
            p = (lo+hi)/2
            cdf = sum(math.comb(n,j)*p**j*(1-p)**(n-j) for j in range(k+1))
            if cdf > target:
                lo = p
            else:
                hi = p
        return (lo+hi)/2
    def bounds(k):
        return (0. if k==0 else solve(k-1, .9875),
                1. if k==n else solve(k, .0125))
    wl,wu = bounds(sum(a['correct'] and not b['correct'] for a,b in pairs))
    ll,lu = bounds(sum(b['correct'] and not a['correct'] for a,b in pairs))
    return [100*(wl-lu),100*(wu-ll)]


def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='results/mmstar-public')
    args=parser.parse_args()
    OUT=ROOT/args.out
    manifest = json.loads((OUT/'manifest.json').read_text())
    rows = [json.loads(s) for s in (OUT/'records.jsonl').read_text().splitlines()]
    case_map={c['id']:c for c in manifest['cases']}
    for r in rows:
        labels=[chr(65+i) for i in range(len(case_map[r['case_id']]['options']))]
        r['contract_correct']=r['correct']
        r['choice']=semantic_choice(r,labels)
        r['correct']=r['choice']==r['gold']
    keys = [(r['case_id'],r['method']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate case/method record')
    summary = dict(dataset=manifest['dataset'], expected_cases=len(manifest['cases']), expected_requests=len(manifest['cases'])*4,
                   completed_requests=len(rows), methods={}, comparisons={})
    for method in METHODS:
        rs = [r for r in rows if r['method']==method]
        if not rs:
            continue
        usage = [r['usage'] for r in rs if r.get('usage')]
        d = dict(n=len(rs), accuracy=100*sum(r['correct'] for r in rs)/len(rs),
            strict_accuracy=100*sum(r['contract_correct'] for r in rs)/len(rs),
            invalid=sum(not r['valid'] for r in rs), errors=sum('error' in r for r in rs),
            truncated=sum(r.get('finish_reason')=='length' for r in rs),
            reasoning_budget_forced=sum(budget_forced(r) for r in rs),
            reasoning_detected=sum(r.get('reasoning_detected',False) for r in rs),
            latency_p50=quantile([r['wall_seconds'] for r in rs],.5),
            latency_p95=quantile([r['wall_seconds'] for r in rs],.95),
            latency_mean=statistics.mean(r['wall_seconds'] for r in rs),
            usage_coverage=len(usage), categories={}, timely_accuracy={})
        for key in ('prompt_tokens','completion_tokens','total_tokens'):
            vals=[u[key] for u in usage if key in u]
            d[key+'_mean']=statistics.mean(vals) if vals else None
        for category in sorted(set(r['category'] for r in rs)):
            subset=[r for r in rs if r['category']==category]
            d['categories'][category]=dict(n=len(subset),correct=sum(r['correct'] for r in subset))
        for deadline in (.5,1,2,5,10,30):
            d['timely_accuracy'][str(deadline)]=100*sum(r['correct'] and r['wall_seconds']<=deadline for r in rs)/len(rs)
        summary['methods'][method]=d
    indexed={(r['case_id'],r['method']):r for r in rows}
    for baseline in METHODS[1:]:
        pairs=[(indexed[c['id'],'omnijev'], indexed[c['id'],baseline]) for c in manifest['cases']
               if (c['id'],'omnijev') in indexed and (c['id'],baseline) in indexed]
        if not pairs:
            continue
        ci=paired_interval(pairs)
        exact_ci=conservative_paired_interval(pairs)
        summary['comparisons'][baseline]=dict(n=len(pairs),
            accuracy_difference_pp=100*statistics.mean(int(a['correct'])-int(b['correct']) for a,b in pairs),
            cluster_bootstrap_95_ci_pp=ci,
            conservative_95_ci_pp=exact_ci,
            noninferior_at_2pp=exact_ci is not None and exact_ci[0]>-2,
            agreement=100*sum(a.get('choice') is not None and a.get('choice')==b.get('choice') for a,b in pairs)/len(pairs),
            wins=sum(a['correct'] and not b['correct'] for a,b in pairs),
            losses=sum(b['correct'] and not a['correct'] for a,b in pairs))
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    lines=['# '+manifest['dataset']+' Public data evaluation','',f'Complete {len(rows)}/{summary["expected_requests"]} requests; fixed stratified sample {len(manifest["cases"])} Question.',
        '', 'Model: Nemotron 3 Nano Omni Q4_K_M; No training; seed=20260920.',
        'Sampling protocol:'+manifest['protocol']['sampling'],
        'All methods use the same image and question. OmniJev Call existing core.decide; direct Use the same prompt and 4-token Upper limit, but do not request logprobs.',
        'reasoning Using the same prompt, reasoning_effort=medium, temperature=0.6, top_p=0.95, Total output limit 20480 tokens.Measured Bionic about 8192 Thinking token After can insert forced answer prompt; this is not infinite budget or complete NVIDIA vLLM Configuration. JSON Implement using existing constrained output, upper bound 32 tokens.',
        'Accuracy is allowed to be explicitly parsed from the last line of the final output; strict accuracy requires full compliance with the return format. Original record of correct retains strict scoring and has not been rewritten.',
        '', '| Method | Number of questions | Answer accuracy | Strict accuracy | P50 second | P95 second | Average generation tokens | Average total tokens | Strictly invalid / Truncate |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m,d in summary['methods'].items():
        lines.append(f'| {m} | {d["n"]} | {d["accuracy"]:.2f}% | {d["strict_accuracy"]:.2f}% | {d["latency_p50"]:.3f} | {d["latency_p95"]:.3f} | {d["completion_tokens_mean"]:.1f} | {d["total_tokens_mean"]:.1f} | {d["invalid"]} / {d["truncated"]} |')
    lines += ['', '## Pairing accuracy difference: OmniJev − Baseline', '', '| Baseline | Matched question count | percentage points difference | Conservative 95% Interval | Non-inferiority test |', '|---|---:|---:|---|---|']
    for m,d in summary['comparisons'].items():
        lo,hi=d['conservative_95_ci_pp'] or d['cluster_bootstrap_95_ci_pp']
        lines.append(f'| {m} | {d["n"]} | {d["accuracy_difference_pp"]:.2f} | [{lo:.2f}, {hi:.2f}] | '+('Meet preset 2pp Non-inferior boundary' if d['noninferior_at_2pp'] else 'Not confirmed 2pp Not inferior')+' |')
    lines += ['', '## Correct answer count per category', '', '| Category | OmniJev | Direct | JSON | Reasoning |', '|---|---:|---:|---:|---:|']
    for category in sorted(set(c['category'] for c in manifest['cases'])):
        cells=[]
        for m in METHODS:
            d=summary['methods'].get(m,{}).get('categories',{}).get(category,{'correct':0,'n':0})
            cells.append(f'{d["correct"]}/{d["n"]}')
        lines.append('| '+category+' | '+' | '.join(cells)+' |')
    lines += ['', '## Scope explanation', '',
        '- This is a fixed subset of public data, not the official full leaderboard score.',
        '- Accuracy denominator includes all requests; parsing failures, timeouts, and truncated cases without final answers are not removed. Strict format non-compliance and answer errors are reported separately.',
        '- Complete time from client start encoding media to parsing answer; includes HTTP, Exclude model loading; not TTFT.',
        '- Service natural cache enabled, request global random sort. Cache not cleared, so results cannot be called cold start latency.',
        '- completion_tokens includes service-reported reasoning token; Must not again reasoning_tokens Add.',
        '- token statistics follow backend reporting conventions; they do not establish a proportional reduction in visual encoding computation or energy consumption.',
        '- summary.json of usage_coverage Record usage report coverage. Interface errors not reported token Cost unknown, will not fabricate as zero.',
        '- reasoning_budget_forced Count separately the number of backend insertion forced answer prompts; it and finish_reason=length The truncation differs, even finish_reason=stop May have also triggered internal reasoning budget.',
        '- Image multiple choice and causal video replay do not prove joint audio-visual capability, continuous streaming execution, or closed-loop task completion rate.',
        '- The non-inferiority margin is preset to 2 percentage points; bootstrap results are pilot analyses; absence of a significant difference cannot be equated with equivalence.',
        '- main interval pairing win/loss probability uses Bonferroni + Clopper-Pearson conservative boundary, avoiding zero difference when bootstrap interval degenerates to zero; only for independent images. Hierarchical sampling inference is only for this balanced class mixture.',
        '- Inference group uses recommended temperature 0.6, single seed single sampling; no repeated sampling to estimate the impact of decoding randomness.',
        '- The model may have encountered public data; here mainly comparing inference strategies of the same backbone, not claiming to exclude pretraining contamination.',
        '- Original per-question records, original responses, usage, hash, and sampling list are all saved in this directory.',
        '', 'Data source:'+manifest['source'],
        'Reproduction: python3 scripts/public_benchmark.py --out '+args.out+'; Summary: python3 scripts/report_public_benchmark.py --out '+args.out, '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
