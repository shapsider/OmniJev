"""Regenerate the evidence report from saved real episode rows, no inference."""
import json
from pathlib import Path
from benchmark_embodied import summarize
ROOT=Path(__file__).resolve().parents[1]
NAMES={'baseline':'Rule baseline','omnijev':'OmniJev','omni_direct':'Direct short answer','omni_reasoning':'Budgeted reasoning','omni_adaptive':'Adaptive'}


def main():
    sections=['''# OmniJev Embodied evaluation report

Date: 2026-09-21.Mac M5 Pro / 48GB, Bionic Loaded Nemotron 3 Nano Omni Q4_K_M, API Alias `omnijev-nemotron`.No training, no cloud inference. Model state see `embodied/backend.json`.

This report records experiments under the above runtime environment. Component sources and licenses see `THIRD_PARTY_NOTICES.md`.

## Protocol

- Skill mode: simulated ground truth state → Model selection skill → Program control IK Trajectory. Three tasks are transfer, stacking, and barrier crossing; each seed=0, Four strategies total 12 rounds.
- Direct vision: dual camera RGB + Proprioceptive feedback → 21 Fixed incremental action; model input has no object/Target ground truth coordinates. Safety preview, contact and final state evaluation use physical simulation ground truth. Transfer seed=0, OmniJev / Direct One round each, 60 Step budget.
- Same backbone, same decision prompt and evidence format; OmniJev With Direct All thinking disabled, T=0, 4-token Upper limit. OmniJev Additional read top-10 logprobs; Not zero decoding hidden state projection. Do not fabricate scores when candidate coverage is insufficient.
- Reasoning group medium, T=0.6, top_p=0.95, Total output limit 4096.Different from existing public QA 20480 limit. No substitute answer is supplied after truncation; failures are retained.
- Fixed candidate reordering, task order random seed 20260921; Per-round serial independent processes, natural cache, model preloading, zero score threshold, physical safety preview enabled.
- Success judged by real physical final state; wall clock includes policy, preview, execution, excluding model loading/Initial scene setup. Input and output token All from backend usage; Output includes reasoning token.
- Request P50/P95 For actual API Call summary, not independent task samples; round time and token Summary according to actual execution trajectory, reasoning strategy may call more times.
''']
    for name in ['rules-smoke','skills-seed0','vision-seed0']:
        out=ROOT/'results/embodied'/name
        if not (out/'episodes.jsonl').exists():continue
        rows=[json.loads(x) for x in (out/'episodes.jsonl').read_text().splitlines()]
        protocol=json.loads((out/'manifest.json').read_text())['protocol']
        summarize(out,protocol,rows,len(protocol['providers'])*len(protocol['tasks'])*len(protocol['seeds']))
        s=json.loads((out/'summary.json').read_text())
        sections.append(f"\n## {name}\n\n{s['completed_episodes']}/{s['expected_episodes']} Round, state `{s['status']}`; Observation `{protocol['observation']}`, Control `{protocol['control']}`.\n")
        sections.append('| Strategy | Success/Total | Average seconds per round | Request P50/P95 second | API Count | Input tokens | Output tokens | Incomplete usage rounds |\n|---|---:|---:|---:|---:|---:|---:|---:|')
        for key,m in s['methods'].items():
            lat='—' if m['request_latency_ms_p50'] is None else f"{m['request_latency_ms_p50']/1000:.3f} / {m['request_latency_ms_p95']/1000:.3f}"
            sections.append(f"| {NAMES[key]} | {m['successes']}/{m['n']} | {m['wall_seconds_mean'] or 0:.2f} | {lat} | {m['model_calls']} | {m['input_tokens_known']:,} | {m['output_tokens_known']:,} | {m['usage_incomplete_episodes']} |")
        sections.append('\n| Task | Strategy | Success | Status | Round seconds | Steps |\n|---|---|---|---|---:|---:|')
        for r in rows:sections.append(f"| {r['task']} | {NAMES[r['provider']]} | {'is' if r['success'] else 'No'} | {r['status']} | {r['wall_seconds']:.2f} | {r.get('cycles','—')} |")
        sections.append(f"\n[Original per-round data](embodied/{name}/episodes.jsonl) · [Complete protocol](embodied/{name}/manifest.json) · [Statistics](embodied/{name}/summary.json).Save per-request, trajectory, and visual camera archives in the same directory; all failures are included in the denominator.")
        if name=='skills-seed0':
            a=s['methods']['omnijev'];b=s['methods']['omni_reasoning'];d=s['methods']['omni_direct']
            saving=1-(a['input_tokens_known']+a['output_tokens_known'])/(b['input_tokens_known']+b['output_tokens_known'])
            sections.append(f"\n In the skill pilot experiment, OmniJev Average round acceleration for relative reasoning {b['wall_seconds_mean']/a['wall_seconds_mean']:.2f}×, Input＋Total output token Reduce {saving:.2%}.Direct short answer also is {d['successes']}/{d['n']} Success, average {d['wall_seconds_mean']:.2f} seconds, and with OmniJev usage consistent; no additional task gains observed from candidate scores. Natural caching, execution order, and local load affect speed, and no stable multiplier can be inferred from three rounds.")
        if name=='vision-seed0':
            for r in rows:
                if not r['success']:sections.append(f"\n Visual failure: {NAMES[r['provider']]} in {r.get('cycles','Unknown')} Step end, state `{r['status']}`, Runtime cause: {r.get('message') or 'See original trajectory'}.Skill-mode results are not used as a substitute.")
    sections.append('''
## Research judgment and limitations

This evaluation validates a training-free local decision runtime, an embodied workbench, and an auditable evaluation pipeline. Small-sample skill experiments show that the system works, but do not establish open-world planning ability, statistical non-inferiority, or an independent advantage over direct short answers. Public 425 Evidence for the question can be found [Public report](PUBLIC_BENCHMARK_REPORT.md), Does not merge with embodied results for accuracy.

Define the research topic as “a low-latency closed-loop decision interface and adaptive computation for frozen multimodal models”, retaining Direct Strong baseline. Next stage independent verification of more seeds, visual perception/Control error, disturbance recovery, success rate under decision deadline, and when to upgrade reasoning. Adaptive Currently only contract testing, cannot claim improved performance.

Physical simulation pauses when the model is waiting, and this experiment has not yet verified real-time risk in continuous motion environments; 500Hz is physical step frequency, not model decision frequency. Image mode has actually sent PNG and execute the action, but audio and continuous video encoding are not yet connected. All results only cover this frozen backbone, quantization, and local runtime.

## Reproduction and verification

See details [Project integration description](../docs/EMBODIED_INTEGRATION.md).Specify a new output directory for the new experiment; existing complete results will only be verified and skipped, not automatically rerun or overwritten on failure. The source code package for the new machine does not include third-party public benchmark Image/Video or model weights, re-evaluate public data by downloading and preparing according to the original protocol, existing results can still be viewed offline. Embodied Panda Assets, Web Build artifacts and all source code are included.

See evidence for verification [validation.json](embodied/validation.json).Rule smoke Manual acceptance with browser belongs to installation/Function check, not included in formal 12 Round. Browser first non-zero score threshold triggers pause, its record kept separately; official evaluation fixed zero threshold.
''')
    target=ROOT/'results/EMBODIED_BENCHMARK_REPORT.md';target.write_text('\n'.join(sections)+'\n');print(target)


if __name__=='__main__':main()
