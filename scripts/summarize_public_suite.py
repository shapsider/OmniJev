"""Produce the final suite report only after every fixed request completes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NAMES=['mmstar-public','mmbench-public','mmad-public','streaming-public']


def main():
    summaries={}
    for name in NAMES:
        s=json.loads((ROOT/'results'/name/'summary.json').read_text())
        if s['completed_requests']!=s['expected_requests']:
            raise SystemExit('Incomplete: '+name)
        summaries[name]=s
    lines=['# OmniJev Public Benchmark Evaluation','',
        'Completed four fixed pilot subsets: 425 questions, 1,700 formal requests. The model is local Nemotron 3 Nano Omni Q4_K_M, weights are frozen.',
        'These are local pilot experiments, not four official benchmark of the full scores. Main accuracy allows explicit parsing of options from the final output; strict format is reported separately by case and not selected from the hidden reasoning process.',
        'See the research judgment and project adjustment suggestions for this round [Evaluation conclusion](PUBLIC_EVALUATION_FINDINGS.md).',
        '', '## Accuracy', '', '| Dataset | Number of questions | OmniJev | Direct short answer | JSON | Native reasoning |', '|---|---:|---:|---:|---:|---:|']
    for name,s in summaries.items():
        m=s['methods']
        lines.append('| '+s['dataset']+f' | {s["expected_cases"]} | '+' | '.join(f'{m[x]["accuracy"]:.2f}%' for x in ('omnijev','direct','json','reasoning'))+' |')
    lines+=['', '## Response time and token', '', '| Dataset | OmniJev P50/P95 second | Inference P50/P95 second | OmniJev / Inference average generation tokens | Total token Save |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        o=s['methods']['omnijev'];r=s['methods']['reasoning']
        saved=100*(1-o['total_tokens_mean']/r['total_tokens_mean'])
        lines.append(f'| {s["dataset"]} | {o["latency_p50"]:.3f} / {o["latency_p95"]:.3f} | {r["latency_p50"]:.3f} / {r["latency_p95"]:.3f} | {o["completion_tokens_mean"]:.1f} / {r["completion_tokens_mean"]:.1f} | {saved:.2f}% |')
    lines+=['', '## Accuracy maintained test', '', 'Difference is defined as OmniJev − Native reasoning; negative numbers indicate OmniJev Lower. Non-inferior baseline preset for maximum descent 2 percentage points. Answer consistency is calculated separately and cannot replace the accuracy against the standard answer.', '', '| Dataset | percentage points difference | Conservative 95% Interval | Answer agreement | Conclusion |', '|---|---:|---:|---:|---|']
    for name,s in summaries.items():
        d=s['comparisons']['reasoning']
        ci=d['conservative_95_ci_pp']
        interval=f'[{ci[0]:.2f}, {ci[1]:.2f}]' if ci else 'See clustering bootstrap'
        lines.append(f'| {s["dataset"]} | {d["accuracy_difference_pp"]:.2f} | {interval} | {d["agreement"]:.2f}% | '+('Meet the pioneer non-inferior standard' if d['noninferior_at_2pp'] else 'Accuracy non-inferiority not established')+' |')
    lines+=['', '## 5 Correctness within the response time limit', '', 'denominator is all requests; incorrect, unable to parse clearly, timeout, or correct but exceeding 5 seconds do not count as successful. A more complete time budget curve can be found in each dataset deadline.png.', '', '| Dataset | OmniJev | Direct short answer | JSON | Native reasoning |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        lines.append('| '+s['dataset']+' | '+' | '.join(f'{s["methods"][m]["timely_accuracy"]["5"]:.2f}%' for m in ('omnijev','direct','json','reasoning'))+' |')
    lines+=['', '## Direct short answer strong baseline', '', '| Dataset | OmniJev / Direct P50 second | OmniJev / Direct Average generation tokens | Answer agreement | Accuracy difference in percentage points |', '|---|---:|---:|---:|---:|']
    for name,s in summaries.items():
        d=s['comparisons']['direct']
        o=s['methods']['omnijev'];b=s['methods']['direct']
        lines.append(f'| {s["dataset"]} | {o["latency_p50"]:.3f} / {b["latency_p50"]:.3f} | {o["completion_tokens_mean"]:.1f} / {b["completion_tokens_mean"]:.1f} | {d["agreement"]:.2f}% | {d["accuracy_difference_pp"]:.2f} |')
    lines+=['', 'The current short tag path uses the same model, prompt, and generation budget as the direct short answer, with the main difference being whether it returns logprobs.Similar results should be attributed to the direct short answer capability of the general model, not interpreted as an independent advantage of the new model paradigm.',
        '', '## Strict format non-compliance and truncation', '', 'Format non-compliance does not necessarily mean the final answer cannot be parsed; main accuracy uses the aforementioned semantic answer scope. The last two columns are statistics for the reasoning group.', '', '| Dataset | OmniJev Format non-compliant | Direct short answer format is non-compliant | JSON Format non-compliant | Inference format non-compliant | Output truncated | Budgeted reasoning forced answer |', '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in summaries.items():
        m=s['methods']
        lines.append('| '+s['dataset']+' | '+' | '.join(str(m[x]['invalid']) for x in ('omnijev','direct','json','reasoning'))+f' | {m["reasoning"]["truncated"]} | {m["reasoning"]["reasoning_budget_forced"]} |')
    lines+=['', '## Limits of interpretation', '',
        '- Reasoning group uses Bionic medium: Request total output limit 20,480, But actual internal reasoning budget is about 8,192 tokens, When the budget is reached, you can insert a forced answer prompt. This is not an unlimited budget or a complete reproduction. NVIDIA Official vLLM service result.',
        '- Use service natural cache; first batch requests may reuse technology cache calibration. Data preparation overlaps with initial reasoning, absolute latency exists system load noise.',
        '- Delay from client encoding input to parsing the complete answer, excluding model loading and pre‑completed video download, decoding, and frame extraction.',
        '- Generate token Including thinking token; Total token Include multiple modal inputs simultaneously. API quantity is not equal to FLOPs, Energy consumption or actual bill.',
        '- MMStar For six categories each 50 questions; MMBench Only test one option order; MMAD Only DS-MVTec, Zero reference image; StreamingBench Only test the resource-constrained causal eight-frame subset.',
        '- Dynamic subset verification is visual question answering under temporal causal constraints, not continuous stream reasoning, real-world task success rate, or native audio-video joint capability.',
        '- Small samples cannot establish equivalence from a statistically insignificant difference; both methods giving the same wrong answer is not an accuracy guarantee.',
        '', '## Reproducible material', '',
        '- [Complete experimental protocol](../docs/PUBLIC_EVALUATION_PROTOCOL.md)',
        '- [Environment recording](public-evaluation-environment.json)',
        '- Dataset directory contains manifest.json, records.jsonl, summary.json, REPORT.md, Model configuration, source code snapshot, input hash, and charts.', '']
    for name in NAMES:
        lines.append(f'- [{name} Detailed report]({name}/REPORT.md)')
    (ROOT/'results/PUBLIC_BENCHMARK_REPORT.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'results/public-suite-summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
    print('Wrote results/PUBLIC_BENCHMARK_REPORT.md')


if __name__=='__main__':main()
