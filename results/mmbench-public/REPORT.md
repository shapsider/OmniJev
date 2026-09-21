# MMBench DEV EN pilot Public data evaluation

Completed 240/240 requests; fixed stratified sampling of 60 items.

Model: Nemotron 3 Nano Omni Q4_K_M; no training; seed=20260920.
Sampling protocol: 3 canonical (index < 1000000) questions per category, seed fixed; one option order only. NOT official circular evaluation.
All methods use the same image and question. OmniJev calls existing core.decide; direct uses the same prompt and 4-token limit, but does not request logprobs.
reasoning Using the same prompt, reasoning_effort=medium, temperature=0.6, top_p=0.95, total output limit 20480 tokens. In practice, Bionic can insert a forced answer prompt after about 8192 reasoning tokens; this is not an unlimited budget or full NVIDIA vLLM configuration. JSON uses existing constrained output implementation, limit 32 tokens.
Main accuracy allows explicit parsing of options from the final output line; strict accuracy requires strict adherence to the return format. The original record's correct remains strictly defined, unchanged.

| Method | Questions | Answer Accuracy | Strict Accuracy | P50 sec | P95 sec | Avg Generated Tokens | Avg Total Tokens | Strict Invalid / Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 60 | 90.00% | 90.00% | 0.611 | 1.186 | 3.0 | 366.6 | 0 / 0 |
| direct | 60 | 90.00% | 90.00% | 0.580 | 1.229 | 3.0 | 366.6 | 0 / 0 |
| json | 60 | 90.00% | 90.00% | 0.860 | 1.344 | 11.0 | 381.6 | 0 / 0 |
| reasoning | 60 | 90.00% | 90.00% | 6.109 | 36.923 | 719.5 | 1083.0 | 0 / 0 |

## Paired accuracy difference: OmniJev − Baseline

| Baseline | Paired questions | Difference in percentage points | Conservative 95% interval | Non-inferiority test |
|---|---:|---:|---|---|
| direct | 60 | 0.00 | [-7.04, 7.04] | Unconfirmed 2pp non-inferior |
| json | 60 | 0.00 | [-7.04, 7.04] | Unconfirmed 2pp non-inferior |
| reasoning | 60 | 0.00 | [-12.58, 12.58] | Unconfirmed 2pp non-inferior |

## Number of correct questions by category

| Category | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| action_recognition | 3/3 | 3/3 | 3/3 | 3/3 |
| attribute_comparison | 3/3 | 3/3 | 3/3 | 2/3 |
| attribute_recognition | 2/3 | 2/3 | 2/3 | 2/3 |
| celebrity_recognition | 3/3 | 3/3 | 3/3 | 3/3 |
| function_reasoning | 3/3 | 3/3 | 3/3 | 3/3 |
| future_prediction | 2/3 | 2/3 | 2/3 | 2/3 |
| identity_reasoning | 3/3 | 3/3 | 3/3 | 3/3 |
| image_emotion | 2/3 | 2/3 | 2/3 | 2/3 |
| image_quality | 2/3 | 2/3 | 2/3 | 2/3 |
| image_scene | 3/3 | 3/3 | 3/3 | 3/3 |
| image_style | 3/3 | 3/3 | 3/3 | 3/3 |
| image_topic | 2/3 | 2/3 | 2/3 | 3/3 |
| nature_relation | 3/3 | 3/3 | 3/3 | 3/3 |
| object_localization | 3/3 | 3/3 | 3/3 | 3/3 |
| ocr | 3/3 | 3/3 | 3/3 | 3/3 |
| physical_property_reasoning | 3/3 | 3/3 | 3/3 | 3/3 |
| physical_relation | 3/3 | 3/3 | 3/3 | 3/3 |
| social_relation | 3/3 | 3/3 | 3/3 | 3/3 |
| spatial_relationship | 2/3 | 2/3 | 2/3 | 2/3 |
| structuralized_imagetext_understanding | 3/3 | 3/3 | 3/3 | 3/3 |

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

Data source: https://github.com/open-compass/MMBench
Reproduce: python3 scripts/public_benchmark.py --out results/mmbench-public; summarize: python3 scripts/report_public_benchmark.py --out results/mmbench-public
