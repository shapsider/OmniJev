# OmniJev Public Benchmark Evaluation

Completed four fixed pilot subsets: 425 questions, 1,700 formal requests. Model is local Nemotron 3 Nano Omni Q4_K_M, weights frozen.
These are small-scale pilot experiments, not full results of the four official benchmarks. Main accuracy allows explicit option parsing from final output; strict format reported separately per case, not selected from hidden reasoning process.
This round's research judgment and task adjustment suggestions see [Evaluation Conclusions](PUBLIC_EVALUATION_FINDINGS.md).

## Accuracy

| Dataset | Questions | OmniJev | Direct Short Answer | JSON | Native Reasoning |
|---|---:|---:|---:|---:|---:|
| MMStar | 300 | 66.67% | 66.67% | 65.33% | 72.33% |
| MMBench DEV EN pilot | 60 | 90.00% | 90.00% | 90.00% | 90.00% |
| MMAD DS-MVTec zero-shot pilot | 45 | 86.67% | 86.67% | 84.44% | 86.67% |
| StreamingBench causal 8-frame pilot | 20 | 85.00% | 85.00% | 85.00% | 85.00% |

## Response Time and Token

| Dataset | OmniJev P50/P95 Seconds | Inference P50/P95 Seconds | OmniJev / Inference Average Generated Tokens | Total Token Savings |
|---|---:|---:|---:|---:|
| MMStar | 1.166 / 1.515 | 15.899 / 120.990 | 3.0 / 2419.4 | 85.79% |
| MMBench DEV EN pilot | 0.611 / 1.186 | 6.109 / 36.923 | 3.0 / 719.5 | 66.16% |
| MMAD DS-MVTec zero-shot pilot | 0.659 / 1.088 | 5.745 / 47.057 | 3.0 / 914.3 | 71.80% |
| StreamingBench causal 8-frame pilot | 2.979 / 3.583 | 20.192 / 124.272 | 3.0 / 2379.1 | 51.26% |

## Accuracy Maintenance Test

Difference defined as OmniJev - Native Reasoning; negative numbers indicate OmniJev lower. Non-inferiority preset as at most 2 percentage point drop. Answer consistency rate separately calculated, cannot replace standard answer accuracy.

| Dataset | Difference Percentage Points | Conservative 95% Interval | Answer Consistency Rate | Conclusion |
|---|---:|---:|---:|---|
| MMStar | -5.67 | [-13.87, 2.69] | 75.00% | Accuracy not confirmed non-inferior |
| MMBench DEV EN pilot | 0.00 | [-12.58, 12.58] | 93.33% | Accuracy not confirmed non-inferior |
| MMAD DS-MVTec zero-shot pilot | 0.00 | [-19.01, 19.01] | 86.67% | Accuracy not confirmed non-inferior |
| StreamingBench causal 8-frame pilot | 0.00 | [-27.87, 27.87] | 85.00% | Accuracy not confirmed non-inferior |

## Accuracy within 5-second response deadline

The denominator is all requests; incorrect, unparseable, timed out, or correct but exceeding 5 seconds are not counted as successful. A more complete time budget curve can be seen in each dataset's deadline.png.

| Dataset | OmniJev | Ordinary short answer | JSON | Native reasoning |
|---|---:|---:|---:|---:|
| MMStar | 66.67% | 66.67% | 65.33% | 9.00% |
| MMBench DEV EN pilot | 90.00% | 90.00% | 90.00% | 36.67% |
| MMAD DS-MVTec zero-shot pilot | 86.67% | 86.67% | 84.44% | 35.56% |
| StreamingBench causal 8-frame pilot | 85.00% | 85.00% | 85.00% | 5.00% |

## Ordinary short answer strong baseline

| Dataset | OmniJev / Direct P50 seconds | OmniJev / Direct average generation tokens | Answer consistency rate | Accuracy difference percentage points |
|---|---:|---:|---:|---:|
| MMStar | 1.166 / 1.170 | 3.0 / 3.0 | 99.67% | 0.00 |
| MMBench DEV EN pilot | 0.611 / 0.580 | 3.0 / 3.0 | 100.00% | 0.00 |
| MMAD DS-MVTec zero-shot pilot | 0.659 / 0.587 | 3.0 / 3.0 | 100.00% | 0.00 |
| StreamingBench causal 8-frame pilot | 2.979 / 2.986 | 3.0 / 3.0 | 100.00% | 0.00 |

The current short label path implementation uses the same model, prompt, and generation budget as ordinary short answers, with the main difference being whether logprobs are returned. Similar results should be attributed to the general model's short answer capability, not interpreted as independent advantages of a new model paradigm.

## Strict format non-compliance and truncation

Format non-compliance does not necessarily mean the final answer cannot be parsed; main accuracy uses the aforementioned semantic answer criteria. The last two columns are for reasoning groups.

| Dataset | OmniJev format violations | Direct short-answer format violations | JSON format violations | Reasoning format violations | Output truncation | Forced answer at reasoning budget |
|---|---:|---:|---:|---:|---:|---:|
| MMStar | 1 | 1 | 0 | 4 | 1 | 43 |
| MMBench DEV EN pilot | 0 | 0 | 0 | 0 | 0 | 0 |
| MMAD DS-MVTec zero-shot pilot | 0 | 0 | 0 | 0 | 0 | 1 |
| StreamingBench causal 8-frame pilot | 0 | 0 | 0 | 0 | 0 | 3 |

## Explanation boundaries

- Reasoning groups use Bionic medium: total request output limit is 20,480, but actual measured internal reasoning budget is about 8,192 tokens; when the budget is reached, a forced answer prompt can be inserted. This is not infinite budget or fully reproducing NVIDIA's official vLLM service results.
- Using service natural cache; first batch requests may reuse technology calibration cache. Data preparation and first segment of reasoning overlap, with absolute latency subject to system load noise.
- Latency from client encoding input to parsing complete answer, excluding model loading and pre-completed video download, decoding, and frame extraction.
- Generated tokens include reasoning tokens; total tokens simultaneously include multi-modal inputs. API usage does not equal FLOPs, energy consumption, or actual billing.
- MMStar consists of 50 questions for each of six categories; MMBench tests only one option order; MMAD only uses DS-MVTec, zero-reference images; StreamingBench only tests resource-constrained causal eight-frame subsets.
- Dynamic subset validation is visual question answering under temporal causal constraints, not continuous streaming reasoning, real-world task success rate, or native audio-video joint capability.
- Small samples cannot claim equivalence based on 'no significant difference'; both methods answering incorrectly together does not constitute accuracy guarantee.

## Reproducible materials

- [Complete experiment protocol](../docs/PUBLIC_EVALUATION_PROTOCOL.md)
- [Environment record](public-evaluation-environment.json)
- Dataset directory includes manifest.json, records.jsonl, summary.json, REPORT.md, model configuration, source code snapshot, input hash, and charts.

- [mmstar-public detailed report](mmstar-public/REPORT.md)
- [mmbench-public detailed report](mmbench-public/REPORT.md)
- [mmad-public detailed report](mmad-public/REPORT.md)
- [streaming-public detailed report](streaming-public/REPORT.md)
