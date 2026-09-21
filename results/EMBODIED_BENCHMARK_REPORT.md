# OmniJev Embodied evaluation report

Date: 2026-09-21. Mac M5 Pro / 48 GB, with Nemotron 3 Nano Omni Q4_K_M loaded in Bionic under the API alias `omnijev-nemotron`. No training or cloud inference was used. See `embodied/backend.json` for model state.

This report records experiments under the above runtime environment. Component sources and licenses see `THIRD_PARTY_NOTICES.md`.

## Protocol

- Skill mode: simulated ground truth state → Model selection skill → Program control IK Trajectory. The three tasks are transfer, stacking, and barrier crossing; each uses seed=0, for four strategies and 12 rounds in total.
- Direct vision: dual-camera RGB plus proprioceptive feedback → 21 fixed incremental actions; model input contains no ground-truth object or target coordinates. Safety preview, contact, and final-state evaluation use physical-simulation ground truth. Transfer uses seed=0, one round for OmniJev and one for Direct, with a 60-step budget.
- Same backbone, same decision prompt and evidence format; Thinking is disabled for both OmniJev and Direct, with T=0 and a 4-token output limit. OmniJev additionally reads top-10 logprobs; this is not a zero-decoding hidden-state projection. Do not fabricate scores when candidate coverage is insufficient.
- The reasoning group uses medium reasoning, T=0.6, top_p=0.95, and a total output limit of 4096. This differs from existing public QA 20480 limit. No substitute answer is supplied after truncation; failures are retained.
- Fixed candidate reordering, task order random seed 20260921; Per-round serial independent processes, natural cache, model preloading, zero score threshold, physical safety preview enabled.
- Success judged by real physical final state; wall-clock time includes policy, preview, and execution, excluding model loading and initial scene setup. Input and output token counts come from backend usage; output includes reasoning tokens.
- Request P50/P95 summarize actual API calls, not independent task samples; round time and token Summary according to actual execution trajectory, reasoning strategy may call more times.


## rules-smoke

3/3 rounds, with state `complete`; Observation `privileged`, Control `skills`.

| Strategy | Success/Total | Average seconds per round | Request P50/P95 second | API Count | Input tokens | Output tokens | Incomplete usage rounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rule baseline | 3/3 | 1.11 | — | 0 | 0 | 0 | 0 |

| Task | Strategy | Success | Status | Round seconds | Steps |
|---|---|---|---|---:|---:|
| stack | Rule baseline | yes | completed | 1.11 | 8 |
| barrier | Rule baseline | yes | completed | 1.10 | 8 |
| transfer | Rule baseline | yes | completed | 1.12 | 8 |

[Original per-round data](embodied/rules-smoke/episodes.jsonl) · [Complete protocol](embodied/rules-smoke/manifest.json) · [Statistics](embodied/rules-smoke/summary.json).The same directory stores per-request records, trajectories, and visual-camera archives; all failures are included in the denominator.

## skills-seed0

12/12 rounds, with state `complete`; Observation `privileged`, Control `skills`.

| Strategy | Success/Total | Average seconds per round | Request P50/P95 second | API Count | Input tokens | Output tokens | Incomplete usage rounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rule baseline | 3/3 | 1.10 | — | 0 | 0 | 0 | 0 |
| OmniJev | 3/3 | 10.58 | 0.699 / 1.390 | 39 | 26,476 | 117 | 0 |
| Direct short answer | 3/3 | 6.84 | 0.442 / 0.539 | 39 | 26,476 | 117 | 0 |
| Budgeted reasoning | 3/3 | 204.86 | 13.283 / 28.914 | 43 | 29,218 | 30,573 | 0 |

| Task | Strategy | Success | Status | Round seconds | Steps |
|---|---|---|---|---:|---:|
| transfer | Direct short answer | yes | completed | 7.87 | 8 |
| stack | Budgeted reasoning | yes | completed | 155.56 | 8 |
| stack | Rule baseline | yes | completed | 1.11 | 8 |
| barrier | OmniJev | yes | completed | 14.39 | 8 |
| barrier | Rule baseline | yes | completed | 1.10 | 8 |
| stack | OmniJev | yes | completed | 10.90 | 8 |
| stack | Direct short answer | yes | completed | 6.21 | 8 |
| barrier | Direct short answer | yes | completed | 6.44 | 8 |
| transfer | OmniJev | yes | completed | 6.44 | 8 |
| barrier | Budgeted reasoning | yes | completed | 268.21 | 10 |
| transfer | Rule baseline | yes | completed | 1.08 | 8 |
| transfer | Budgeted reasoning | yes | completed | 190.82 | 8 |

[Original per-round data](embodied/skills-seed0/episodes.jsonl) · [Complete protocol](embodied/skills-seed0/manifest.json) · [Statistics](embodied/skills-seed0/summary.json).The same directory stores per-request records, trajectories, and visual-camera archives; all failures are included in the denominator.

In the skill pilot, OmniJev was 19.37×, and reduced total input plus output tokens by 55.52%.Direct short answer also achieved 3/3 success, average 6.84 seconds, and with OmniJev usage consistent; no additional task gains observed from candidate scores. Natural caching, execution order, and local load affect speed, and no stable multiplier can be inferred from three rounds.

## vision-seed0

2/2 rounds, with state `complete`; Observation `vision`, Control `incremental`.

| Strategy | Success/Total | Average seconds per round | Request P50/P95 second | API Count | Input tokens | Output tokens | Incomplete usage rounds |
|---|---:|---:|---:|---:|---:|---:|---:|
| OmniJev | 0/1 | 286.00 | 4.765 / 4.960 | 60 | 228,408 | 180 | 0 |
| Direct short answer | 0/1 | 285.55 | 4.622 / 4.866 | 60 | 228,408 | 180 | 0 |

| Task | Strategy | Success | Status | Round seconds | Steps |
|---|---|---|---|---:|---:|
| transfer | Direct short answer | No | exhausted | 285.55 | 60 |
| transfer | OmniJev | No | exhausted | 286.00 | 60 |

[Original per-round data](embodied/vision-seed0/episodes.jsonl) · [Complete protocol](embodied/vision-seed0/manifest.json) · [Statistics](embodied/vision-seed0/summary.json).The same directory stores per-request records, trajectories, and visual-camera archives; all failures are included in the denominator.

Visual failure: Direct short answer ended after 60 steps, with state `exhausted`, Runtime cause: action budget reached. Skill-mode results are not used as a substitute.

Visual failure: OmniJev ended after 60 steps, with state `exhausted`, Runtime cause: action budget reached. Skill-mode results are not used as a substitute.

## Research judgment and limitations

This evaluation validates a training-free local decision runtime, an embodied workbench, and an auditable evaluation pipeline. Small-sample skill experiments show that the system works, but do not establish open-world planning ability, statistical non-inferiority, or an independent advantage over direct short answers. Public 425 Evidence for the question can be found [Public report](PUBLIC_BENCHMARK_REPORT.md), Does not merge with embodied results for accuracy.

Define the research topic as “a low-latency closed-loop decision interface and adaptive computation for frozen multimodal models”, retaining Direct Strong baseline. Next stage independent verification of more seeds, visual perception/Control error, disturbance recovery, success rate under decision deadline, and when to upgrade reasoning. Adaptive Currently only contract testing, cannot claim improved performance.

Physical simulation pauses when the model is waiting, and this experiment has not yet verified real-time risk in continuous motion environments; 500Hz is physical step frequency, not model decision frequency. Image mode has actually sent PNG and execute the action, but audio and continuous video encoding are not yet connected. All results only cover this frozen backbone, quantization, and local runtime.

## Reproduction and verification

See details [Project integration description](../docs/EMBODIED_INTEGRATION.md).Specify a new output directory for the new experiment; existing complete results will only be verified and skipped, not automatically rerun or overwritten on failure. The source code package for the new machine does not include third-party public benchmark Image/Video or model weights, re-evaluate public data by downloading and preparing according to the original protocol, existing results can still be viewed offline. Embodied Panda Assets, Web Build artifacts and all source code are included.

See evidence for verification [validation.json](embodied/validation.json).Rule smoke Manual acceptance with browser belongs to installation/Function check, not included in formal 12 Round. Browser first non-zero score threshold triggers pause, its record kept separately; official evaluation fixed zero threshold.

