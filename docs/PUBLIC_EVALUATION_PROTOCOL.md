# Public Evaluation Protocol

Date: 2026-09-20. Model remains frozen, no training, no weight changes. This protocol uses Nemotron 3 Nano Omni Q4_K_M.

## Fixed subset

| Data | Samples | Sampling and restrictions |
|---|---:|---|
| MMStar | 300 | Six categories, 50 questions each, 300 independent images |
| MMBench DEV EN | 60 | 20 categories, 3 original questions each, only one option order tested, not circular score |
| MMAD DS-MVTec | 45 | Nine labeled types, 5 questions each, independent images, no reference images, no domain knowledge |
| StreamingBench real-time vision part | 20 | Ten categories, 2 questions each, independent videos; only videos with compression size not exceeding 100 MB are selected |

Total 425 questions, 4 methods, 1,700 official requests. All are fixed by seed=20260920 before inference; sampling list and input file hash are saved in manifest.json of each result directory. Subsets are for pilot assessment and cannot be used for official leaderboards or broad equivalence claims.

Videos use up to 60 seconds of eight ordered frames; sampling window ends 0.1 seconds before the question time (earliest target frame can be 60.1 seconds before the question), longest side not exceeding 512 pixels. FFmpeg actual frame timestamps are verified one by one not later than the question time; future frames are not provided. Only one question is selected per video to avoid misinterpreting related questions as independent samples. This evaluates causal QA after frame extraction, not continuous video input, action execution, or joint audio-video understanding. Final audit precisely refined the previous "first 60 seconds" description without changing frame extraction, questions, or model input.

## Four method groups

1. OmniJev: Existing core.decide short label mode, disabled reasoning, max_tokens=4, returns top-10 logprobs.
2. Direct: Same message, temperature, seed, and 4-token budget as OmniJev, without requesting logprobs.
3. JSON: Existing core.decide output constrained by JSON schema, disabled reasoning, max_tokens=32.
4. Reasoning: Same message as short label mode, enabled native reasoning, temperature=0.6, top_p=0.95, max_tokens=20480. Final output still requires a single option letter. Sampling and output limits follow NVIDIA model card recommendations; Bionic's vLLM reasoning_budget/grace_period support unverified configurations, so no claim of full replication of NVIDIA's service setup.

Non-reasoning group temperature is 0; reasoning group uses recommended temperature 0.6. Generated seed=20260919. Model loading state saved to backend.json; model loading time excluded from per-question reasoning duration. Case × method requests within each dataset are globally randomly sorted and executed sequentially.

2,048-token initial calibration truncated, then attempted greedy 8,192-token counterpart at temperature 0. After checking NVIDIA model card, main reasoning counterpart corrected to temperature 0.6, top_p=0.95, 20,480-token limit. Old records fully retained in calibration and greedy8192-ablation directories; parameters unchanged for 152 short answer records continue to be used, reasoning records regenerated. This process is part of pilot protocol development, not pre-registered validation experiments. Truncated requests are counted as failures and do not represent infinite budget performance.

## Metrics

- Main accuracy allows explicit parsing of option from final output last line; strict format accuracy separately tracked. Failures include inability to parse explicitly, timeouts, and no final answer output; answers not taken from hidden reasoning. Original records retain strict scoring, reported separately normalized.
- End-to-end client response time P50/P95/mean, including image encoding, HTTP, and parsing; excludes model loading and pre-completed video download, decoding, and frame extraction.
- Backend-reported input, generation, and total tokens. Generated tokens include reasoning and are not double-counted.
- Proportion of requests correctly completed within 0.5/1/2/5/10/30 seconds; this analyzes response time after input is ready.
- Accuracy difference between same-question pairs, win/loss counts, answer consistency rate. Non-inferiority threshold is 2 percentage points.
- Image clustering bootstrap 95% interval, and win/loss probability for independent inputs using conservative Bonferroni + Clopper-Pearson intervals; pilot inference does not constitute formal equivalence conclusion.

## Confounding factors and conclusion boundaries

- Service natural caching enabled, no forced KV or image cache clearing. Random order may alleviate sequential bias, but cannot claim cold start performance. First batch requests may reuse technical calibration cache.
- Data preparation and initial MMStar inference overlap in time, possibly increasing that segment's delay noise; remaining inference continues sequentially after download, decoding completion. System load or thermal state of other applications not controlled.
- Main difference between current OmniJev and Direct is whether candidate token scores are requested. If results are similar, this should be interpreted as general backbone short answer capability, not evidence of new model paradigm.
- Public data may contain training set contamination; testing here uses same backbone reasoning methods, not claiming contamination exclusion.
- MMBench and MMStar have overlapping sources, so scores from both datasets cannot be treated as fully independent evidence.
- Reasoning group uses single seed and single sampling; no repeated sampling to estimate decoding randomness.
- This round does not validate native audio, closed-loop task success, cross-model generalization, or production reliability.

## Files and reproducibility

Install drawing and video decoding dependencies: `python3 -m venv .venv-eval`, then `.venv-eval/bin/pip install matplotlib==3.9.4 imageio-ffmpeg==0.6.0`.

Download and verify public data tables: `python3 scripts/download_public_data.py`.

Data preparation: `scripts/public_benchmark.py --prepare-only` and `scripts/prepare_extra_benchmarks.py`.

Run: `python3 scripts/public_benchmark.py --out results/<dataset>-public`. Be sure to generate the corresponding manifest first.

Summary: `python3 scripts/report_public_benchmark.py --out results/<dataset>-public`.

Charts: `.venv-eval/bin/python scripts/plot_public_benchmark.py --out results/<dataset>-public`; comparison charts are rejected if not all requests are completed.

After all four manifest files are ready, you can run `python3 scripts/complete_public_suite.py` to execute and aggregate all subsets sequentially.

Records are saved per question in records.jsonl, containing final answer, correctness, duration, backend usage, full response, request configuration, prompt hash, and time. Snapshots and hashes of the script and core logic are retained in the results directory.

Recommended sampling source: https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16

Backend budget check: main counterpart reasoning_effort=medium. Actual response shows some requests inserting `I have to answer now.` after about 8,192 reasoning tokens and returning the final option, even if finish_reason=stop, triggering the budget. This event is reported separately; 20,480 is the request output upper limit, not the verified internal reasoning budget. This round does not represent unlimited budget or the full NVIDIA vLLM recommended configuration.

Scoring correction: after observing that reasoning output explains first and then explicitly gives the option, the main answer accuracy increases with general last-line option normalization, while retaining strict format correctness and original records. Normalization does not use gold, does not change model output, and does not search for answers within internal reasoning content.
