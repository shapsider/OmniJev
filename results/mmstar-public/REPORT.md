# MMStar public data evaluation

Complete 1200/1200 requests; fixed stratified sample 300 questions.

Model: Nemotron 3 Nano Omni Q4_K_M; no training; seed=20260920.
Sampling protocol: uniform within six top-level categories; fixed before inference
All methods use the same image and question. OmniJev calls existing core.decide; direct uses the same prompt and 4-token limit, but does not request logprobs.
reasoning Using the same prompt, reasoning_effort=medium, temperature=0.6, top_p=0.95, total output limit 20480 tokens. In practice, Bionic can insert a forced answer prompt after about 8192 reasoning tokens; this is not an unlimited budget or full NVIDIA vLLM configuration. JSON uses existing constrained output implementation, limit 32 tokens.
Main accuracy allows explicit parsing of options from the final output line; strict accuracy requires strict adherence to the return format. The original record's correct remains strictly defined, unchanged.

| Method | Questions | Answer Accuracy | Strict Accuracy | P50 sec | P95 sec | Avg Generated Tokens | Avg Total Tokens | Strict Invalid / Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 300 | 66.67% | 66.67% | 1.166 | 1.515 | 3.0 | 400.4 | 1 / 0 |
| direct | 300 | 66.67% | 66.67% | 1.170 | 1.553 | 3.0 | 400.4 | 1 / 0 |
| json | 300 | 65.33% | 65.33% | 1.286 | 1.760 | 10.7 | 415.0 | 0 / 0 |
| reasoning | 300 | 72.33% | 71.67% | 15.899 | 120.990 | 2419.4 | 2816.8 | 4 / 1 |

## Paired accuracy difference: OmniJev − Baseline

| Baseline | Paired questions | Difference in percentage points | Conservative 95% interval | Non-inferiority test |
|---|---:|---:|---|---|
| direct | 300 | 0.00 | [-1.45, 1.45] | Meets preset 2pp non-inferior limit |
| json | 300 | 1.33 | [-2.98, 5.58] | Unconfirmed 2pp non-inferior |
| reasoning | 300 | -5.67 | [-13.87, 2.69] | Unconfirmed 2pp non-inferior |

## Number of correct questions by category

| Category | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| coarse perception | 34/50 | 34/50 | 34/50 | 31/50 |
| fine-grained perception | 28/50 | 28/50 | 27/50 | 30/50 |
| instance reasoning | 42/50 | 42/50 | 42/50 | 39/50 |
| logical reasoning | 37/50 | 37/50 | 34/50 | 35/50 |
| math | 27/50 | 27/50 | 25/50 | 45/50 |
| science & technology | 32/50 | 32/50 | 34/50 | 37/50 |

## Explanation scope

- This is a fixed subset of public data, not the official full leaderboard score.
- The denominator of accuracy includes all requests; failures to parse, timeouts, and truncated cases without a final answer are not removed. Strict format non-compliance and answer errors are reported separately.
- Completed duration from client-side media encoding to response parsing; includes HTTP, excludes model loading; not TTFT.
- Service natural cache is enabled, requests global random ordering. Cache is not cleared, so results cannot be called cold start latency.
- completion_tokens contains the thought token of the service report; do not add reasoning_tokens again.
- Token statistics follow backend reporting conventions; they do not establish a proportional reduction in visual encoding computation or energy consumption.
- summary.json's usage_coverage records the number of usage reports covered. The cost of tokens not reported as interface errors is unknown and will not be fabricated as zero.
- reasoning_budget_forced separately counts the number of times the backend is forced to answer a prompt; it differs from finish_reason=length truncation, as even finish_reason=stop may have triggered internal reasoning budget.
- Image multiple-choice and causal video replay do not prove joint audio-visual capability, continuous streaming execution, or closed-loop task completion.
- The non-inferiority margin is set to 2 percentage points; bootstrap results are pilot analyses and cannot equate lack of significant difference with equivalence.
- The main interval uses Bonferroni + Clopper-Pearson conservative bounds for paired win/loss probability to avoid bootstrap interval degeneration to zero when there is no difference; it is used only for independent images, with stratified sampling inference limited to this balanced class mix.
- The reasoning group uses recommended temperature 0.6, single-seed single-sample; no repeated sampling to estimate the impact of decoding randomness.
- The model may have been exposed to public data; this primarily compares reasoning strategies of the same backbone and does not claim to exclude pretraining contamination.
- Original per-question records, original responses, usage, hash, and sampling lists are all saved in this directory.

Data source: https://huggingface.co/datasets/Lin-Chen/MMStar
Reproduce: python3 scripts/public_benchmark.py --out results/mmstar-public; summarize: python3 scripts/report_public_benchmark.py --out results/mmstar-public
