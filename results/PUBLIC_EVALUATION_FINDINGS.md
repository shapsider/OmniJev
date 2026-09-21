# This round's evaluation conclusions and task adjustments

2026-09-21; covers four fixed pilot subsets, 425 questions, and 1,700 formal requests. See the [Overall Report](PUBLIC_BENCHMARK_REPORT.md) for full figures and protocol.

This round confirms that the current direct short answer strategy significantly reduces generation process, but does not confirm "universal preservation of long-chain reasoning accuracy", nor does it show independent advantage over ordinary short answers. It is recommended to retain OmniJev as a system research prototype and adjust research claims.

## Results of the three original goals

- **Fast**: Supports speed gains relative to this round's reasoning baseline. Median response time ratios for the four groups are approximately 13.6, 10.0, 8.7, and 6.8 times. Ordinary short answers have similar latency. OmniJev's median latency for eight-frame video remains 2.98 seconds, which cannot be used to claim sub-second control or high-frequency real-time decision-making.
- **Low token**: Supports. OmniJev averages 3 tokens generated, while the reasoning group uses approximately 719–2,419 tokens. Including multimodal input, total token savings across the four groups are 85.79%, 66.16%, 71.80%, and 51.26% respectively. This is API usage, not proportional FLOPs or energy consumption reduction.
- **Consistent accuracy**: Not yet confirmed. Overall accuracy is the same on MMBench, MMAD, and video subsets, but not per-question decision; effective answer consistency relative to the reasoning group is 93.33%, 86.67%, and 85.00% respectively. MMStar accuracy drops from 72.33% in the reasoning group to 66.67%, a difference of 5.67 percentage points. None of the four groups reach the conservative 2pp non-inferiority threshold in this round's conservative interval.

The mathematical subset of MMStar is a concrete counterexample: short answer correct 27/50, reasoning group correct 45/50. Category analysis is done after results, cannot directly serve as basis for designing and validating routing strategies using test set.

## Response to "General model is sufficient"

This round's results support a limited conclusion: **the fixed option short label path of the current repository can be reproduced by the same general model's direct short answer to match its accuracy and token usage.** All four groups showed no paired accuracy gain, and latency remained close. Request logprobs provided a candidate score interface, but this round did not prove these scores improve abstention, routing, or task success rates.

Therefore, the current implementation is insufficient to support the paper's claim of "independent new model paradigm." This does not negate undisclosed Jev internal mechanisms, nor does it mean dynamic multimodal decision systems lack research value.

## Suggested task positioning

Suggest adjusting to: **training-free, time-limited multimodal selective reasoning and decision system**.

1. Retain short answer fast path; study when to upgrade to long chain reasoning, when to abstain. Candidate scores need independent development set calibration, cannot directly treat softmax scores as correct probabilities.
2. For continuous inputs, study event-triggered perception, state memory, and failure detection: only re-process media when environment changes or evidence is insufficient. Corresponding gains require new continuous scenario experiments for verification.
3. Use direct short answer, fixed-frequency perception, and fixed reasoning budget as strong baselines, comparing success rate and cost under same error rate or same time limit. Thresholds, rules, and cache strategies are determined on development set, then frozen to new test set; also report worst-case scenarios and tail latency.

The accuracy within five seconds in this round shows this direction is worth exploring: MMStar 66.67% vs 9.00%, video subset 85.00% vs 5.00% (OmniJev for reasoning group). But direct short answer also achieves same fast path performance, so subsequent work must prove incremental gains from scheduling and state management over direct short answer.

## Explanation limitations

This round only tested the local Nemotron 3 Nano Omni Q4_K_M, without training the model; not a model comparison between Qwen and Nemotron. Used Bionic medium, measured approx 8k thinking budget, total output limit 20,480; 47 reasoning responses detected internal budget enforcement to answer prompt, one of which also reached total output limit. All requests retained, no interface errors.

Service uses natural caching, main experiment underwent protocol calibration, cannot be regarded as pre-registered confirmatory experiment. Video is causal-validated pre-extracted frames for QA, without native audio or closed-loop action execution. The four public subsets are not official full-list benchmarks, sample size limited, MMStar and MMBench may share sources; cannot treat them as completely independent generalization evidence.
