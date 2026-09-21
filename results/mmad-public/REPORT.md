# MMAD DS-MVTec zero-shot pilot public data evaluation

Completed 180/180 requests; fixed stratified sample of 45 questions.

Model: Nemotron 3 Nano Omni Q4_K_M; no training; seed=20260920.
Sampling protocol: 5 questions per annotation type, distinct images, DS-MVTec partition only; no reference images or domain knowledge; no previous QA answers.
All methods use the same image and question. OmniJev calls existing core.decide; direct uses the same prompt and 4-token limit, but does not request logprobs.
reasoning Using the same prompt, reasoning_effort=medium, temperature=0.6, top_p=0.95, total output limit 20480 tokens. In practice, Bionic can insert a forced answer prompt after about 8192 reasoning tokens; this is not an unlimited budget or full NVIDIA vLLM configuration. JSON uses existing constrained output implementation, limit 32 tokens.
Main accuracy allows explicit parsing of options from the final output line; strict accuracy requires strict adherence to the return format. The original record's correct remains strictly defined, unchanged.

| Method | Questions | Answer Accuracy | Strict Accuracy | P50 sec | P95 sec | Avg Generated Tokens | Avg Total Tokens | Strict Invalid / Truncated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| omnijev | 45 | 86.67% | 86.67% | 0.659 | 1.088 | 3.0 | 357.9 | 0 / 0 |
| direct | 45 | 86.67% | 86.67% | 0.587 | 1.134 | 3.0 | 357.9 | 0 / 0 |
| json | 45 | 84.44% | 84.44% | 0.828 | 1.220 | 11.0 | 372.9 | 0 / 0 |
| reasoning | 45 | 86.67% | 86.67% | 5.745 | 47.057 | 914.3 | 1269.2 | 0 / 0 |

## Paired accuracy difference: OmniJev − Baseline

| Baseline | Paired questions | Difference in percentage points | Conservative 95% interval | Non-inferiority test |
|---|---:|---:|---|---|
| direct | 45 | 0.00 | [-9.28, 9.28] | 2pp non-inferiority not established |
| json | 45 | 2.22 | [-9.25, 13.36] | 2pp non-inferiority not established |
| reasoning | 45 | 0.00 | [-19.01, 19.01] | 2pp non-inferiority not established |

## Number of correct questions by category

| Category | OmniJev | Direct | JSON | Reasoning |
|---|---:|---:|---:|---:|
| Anomaly Detection | 4/5 | 4/5 | 4/5 | 4/5 |
| Defect Analysis | 5/5 | 5/5 | 5/5 | 5/5 |
| Defect Classification | 4/5 | 4/5 | 4/5 | 4/5 |
| Defect Description | 5/5 | 5/5 | 5/5 | 5/5 |
| Defect Localization | 5/5 | 5/5 | 4/5 | 4/5 |
| Object Analysis | 4/5 | 4/5 | 4/5 | 4/5 |
| Object Classification | 5/5 | 5/5 | 5/5 | 5/5 |
| Object Details | 3/5 | 3/5 | 3/5 | 4/5 |
| Object Structure | 4/5 | 4/5 | 4/5 | 4/5 |

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

Data source: https://huggingface.co/datasets/jiang-cc/MMAD
Reproduce: python3 scripts/public_benchmark.py --out results/mmad-public; summarize: python3 scripts/report_public_benchmark.py --out results/mmad-public
