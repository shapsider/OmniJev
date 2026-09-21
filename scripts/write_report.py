"""Render a factual Markdown report from saved rows, never invent measurements."""
import json
import statistics
from pathlib import Path

sources=['nemotron-v1','nemotron-stress','qwen-v1','qwen-stress']
rows={s:[json.loads(l) for l in Path('results',s+'.jsonl').read_text().splitlines()] for s in sources}
lines=['# OmniJev Small-scale experiment report','',
       'Date: 2026-09-19.Hardware: Apple M5 Pro, 48 GB Unified memory. All using existing local weights, no training, no new weight downloads.','',
       '## Result','',
       'The basic package contains 17 text/Image question; supplement set includes 9 diagnosis. Each model and each method runs two rounds. Some questions share media and are not independent samples; repeated runs are only for diagnosing stability. Audio capability probes are counted separately.','',
       '| Model/Dataset | Method | Correct/Valid request | API Error | Median request latency |',
       '|---|---|---:|---:|---:|']
for source in sources:
    for mode in ['letter','json']:
        subset=[r for r in rows[source] if r['mode']==mode]
        valid=[r for r in subset if not r.get('error')]
        median=statistics.median(r['latency_seconds'] for r in valid)
        lines.append(f'| {source} | {mode} | {sum(r["correct"] for r in valid)}/{len(valid)} | {len(subset)-len(valid)} | {median:.3f} s |')
lines+=['',
 'Time from sending API Request to completion, including server-side media processing and inference, excluding model loading and client-side media encoding. Requests are interleaved randomly, with warm-up before execution; cache uses backend default policy, no isolation for cold/Hot cache. Cannot derive acceleration ratio or statistical significance of independent methods from these numbers.',
 '', '## Prototype implemented', '',
 '- Text, single-image, multi-image sequential frame input; passed at runtime 2–26 Option.',
 '- Non-thinking short-label output, plus a JSON Schema constrained JSON baseline.',
 '- Read scores for canonical candidate letters at the first answer position. If the candidate set is incomplete, return null, No zero padding; only relative scores, no claim of calibration.',
 '- Strict candidate validation, full response retention, fixed seed, fixture Hash, error log, and repeatable run script.',
 '', '## Audio not connected: confirmed restriction', '',
 'Bionic compatible interface rejected input_audio(HTTP 400).Using the included llama.cpp 2.41.0 Directly load the same weight and mmproj After, the audio is still rejected ( HTTP 500).Service /props Clearly return vision=true, video=true, audio=false, Evidence see native-props.json and nemotron-native-audio.jsonl.',
 '',
 'This result only indicates that the measured exported file and runtime combination cannot perform native audio inference, and does not negate NVIDIA Original Omni model audio capability. Speech transcription was not substituted, and rejected-request latency was not included in effective inference speed. Native audio support still requires validation of exports containing an audio encoder and a compatible runtime.',
 '', '## Debugging process and auditability', '',
 '- nemotron-pilot.jsonl is the first probe: max_tokens=1 Hidden structure token Consumption, short tags all truncated. Retain original records, but do not include in valid method comparison.',
 '- Effectively run changes short tags to budget 4, JSON Budget is 32, reasoning_effort=none.This is still short-label generation, not internal zero-generation forward.',
 '- Nemotron The initial run requested top_logprobs=20; MLX Error upper limit is 10 After that, subsequent runs and current code are unified as 10.Only affects the coverage range of the returned candidates, without assuming missing items are zero.',
 '- Initial round probability extraction treats space variants as ambiguous. Existing summary only reads bare letters from the specification. token, Recomputed from the original response; original files are not overwritten.',
 '- Later runs save request configurations and code hashes individually; the notes above document configuration differences in earlier runs. Model file paths, sizes, modification times, and hashes of small configuration files are in environment.json ; full weight hashes were not computed.',
 '', '## Assessment of the research topic', '',
 'Engineering feasibility: both local models can serve as training-free visual/and text finite-choice decision makers. Additional diagnostics checked option permutations, out-of-candidate colors, blank images, invisible audio attributes, and two-frame order.',
 '',
 'Research advantages remain unproven: these programmatically generated tasks are too simple and accuracy is saturated; there are too few errors to evaluate abstention, calibration, or selective risk. High scores here do not imply high reliability. No adaptive perception/reasoning policy or shared-prefix parallel engine was implemented, and no comparison was made with a single token Original forward using the same prompt.',
 '',
 'Continue validating the audio execution path, then introduce realistic, ambiguous, and cross-modal conflicting test sets. Method research can be supported only if gains remain at the same error rate and coverage after accounting for all checking/and fallback costs.',
 '', '## Viewing and reproduction', '',
 'Run the commands in the project root from README . Original results are in results/*.jsonl; Use scripts/summarize.py to recompute summaries from the original responses, and scripts/write_report.py to generate this report.','']
Path('results/EXPERIMENT_REPORT.md').write_text('\n'.join(lines))
print('\n'.join(lines[:18]))
