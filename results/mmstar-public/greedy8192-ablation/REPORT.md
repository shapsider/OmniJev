# MMStar public data evaluation

Complete 74/1200 requests; fix stratified sample 300 questions.

Model: Nemotron 3 Nano Omni Q4_K_M; no training; seed=20260920.
Sampling protocol: uniform within six top-level categories; fixed before inference
All methods use the same image and question. OmniJev calls existing core.decide; direct uses the same prompt and 4-token limit, but does not request logprobs.
reasoning Use the same prompt, enable native thinking, upper limit 8192 tokens; JSON use existing constrained output implementation, upper limit 32 tokens.

| Method | Number of Questions | Accuracy | P50 Seconds | P95 Seconds | Average Generated Tokens | Average Total Tokens | Invalid / Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 16 | 75.00% | 0.866 | 1.531 | 3.0 | 400.6 | 0 / 0 |
| direct | 16 | 87.50% | 0.842 | 1.460 | 3.0 | 393.9 | 0 / 0 |
| json | 14 | 57.14% | 1.373 | 1.973 | 10.4 | 418.6 | 0 / 0 |
| reasoning | 28 | 78.57% | 12.895 | 133.478 | 1339.3 | 1734.0 | 2 / 2 |

## Paired accuracy difference: OmniJev − Baseline

| Baseline | Paired questions | Difference in percentage points | Conservative 95% interval | Non-inferiority test |
|---|---:|---:|---|---|
| reasoning | 1 | 0.00 | [-98.75, 98.75] | Unconfirmed 2pp Non-inferior |

## Number of correct questions by category

| Category | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| coarse perception | 0/0 | 0/0 | 1/3 | 4/4 |
| fine-grained perception | 3/3 | 3/3 | 1/3 | 4/5 |
| instance reasoning | 2/2 | 3/4 | 1/2 | 5/6 |
| logical reasoning | 0/1 | 3/3 | 1/1 | 4/5 |
| math | 5/6 | 2/2 | 2/3 | 3/4 |
| science & technology | 2/4 | 3/4 | 2/2 | 2/4 |

## Explanation scope

- This is a fixed subset of public data, not the official full leaderboard score.
- Accuracy denominator includes all requests; invalid, timeout, and truncated failures are not excluded.
- Completed duration from client-side media encoding to response parsing; includes HTTP, excludes model loading; not TTFT.
- Service natural cache is enabled, requests global random ordering. Cache is not cleared, so results cannot be called cold start latency.
- completion_tokens contains the thought token of the service report; do not add reasoning_tokens again.
- Token statistics follow backend reporting conventions; they do not establish a proportional reduction in visual encoding computation or energy consumption.
- Image multiple-choice and causal video replay do not prove joint audio-visual capability, continuous streaming execution, or closed-loop task completion.
- The non-inferiority margin is set to 2 percentage points; bootstrap results are pilot analyses and cannot equate lack of significant difference with equivalence.
- The main interval uses Bonferroni + Clopper-Pearson conservative bounds for paired win/loss probability to avoid bootstrap interval degeneration to zero when there is no difference; it is used only for independent images, with stratified sampling inference limited to this balanced class mix.
- The model may have been exposed to public data; this primarily compares reasoning strategies of the same backbone and does not claim to exclude pretraining contamination.
- Original per-question records, original responses, usage, hash, and sampling lists are all saved in this directory.

Data source: https://huggingface.co/datasets/Lin-Chen/MMStar
Reproduce: python3 scripts/public_benchmark.py --out results/mmstar-public; summarize: python3 scripts/report_public_benchmark.py --out results/mmstar-public
