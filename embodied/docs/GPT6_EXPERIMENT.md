# GPT-6 Astra preset skill experiment

2026-09-20, run transfer to tray, block stacking, and transfer over barrier tasks sequentially via configured OpenAI compatible API, each with seed 0, 1, 2. **All nine episodes completed, with 8 actions and 13 model calls per episode.**

This set of experiments uses **simulation ground truth state plus preset skills**. The model returns candidate selections based on position, geometry, gripper and contact state, then MuJoCo executes the action and provides new state. Entire process uses `chat` adapter, no switch to rule baseline. Original image input and incremental XYZ control results see [Visual Planning Experiment](PLANNING_RESULTS.md).

![GPT-6 Astra nine-round experiment results](results/gpt6-astra-2026-09-20.png)

## Results

| Task | Success | Avg time per round | Avg decision time per call |
| --- | --- | --- | --- |
| Transfer to tray | 3/3 | 41.60 seconds | 2.77 seconds |
| Block stacking | 3/3 | 43.84 seconds | 2.90 seconds |
| Transfer over barrier | 3/3 | 42.06 seconds | 2.77 seconds |

Nine rounds executed 72 actions, 117 model calls. API returned cumulative usage of **74,003 input tokens and 1,818 output tokens**. Avg decision time 2.81 seconds, median 2.61 seconds, P95 4.23 seconds; actual round time 38.69–47.20 seconds, average 42.50 seconds. Nine-round timing total 382.49 seconds, excluding round wait and separate connection checks.

All exported frame records showed no prohibited contact flag; this statistic checks frame records, not internal physics substeps. Max lift per round 0.1975–0.1993 meters, final results meet simulated support, position, stability and gripper conditions.

## Running Settings

| Project | Experiment Setting |
| --- | --- |
| Code Submission | [`7461356`](https://github.com/FBddcz/embodied-jev/tree/746135693c94a4f87e5d4632e16aec5bef487d21) |
| Request Model / Service Return Model | `gpt-6-astra` / `gpt-6-astra-2026-09-03` |
| Interface and Output | OpenAI compatible Chat Completions, JSON candidate selection |
| Prompt Version | `compact-effects-v4` |
| Task / Seed | `transfer`, `stack`, `barrier`; each 0, 1, 2 |
| Preview / Probability Threshold | Enable preview; threshold 0 |
| Actions per episode budget / timeout | 12 actions; 600 seconds |
| Execution mode | Run sequentially, web service `speed=4` |
| Sampling parameters | No additional temperature, top_p, or API seed set; use service defaults |

Model name comes from the selected API response, without independently verifying server-side weights. Chat adapter reads model-generated choices, does not provide native candidate probabilities. Code remains responsible for stage filtering, candidate actions, inverse kinematics, and success determination.

This is a small-sample development experiment on three fixed tasks. Old MiniCPM testing used different execution rhythms and sample counts, so speed ranking cannot be strictly inferred; TypeSafe Jev and Claude have not yet completed real API counterparts under the same settings in this project.

## Data and Reproducibility

[Public JSON report](results/gpt6-astra-2026-09-20.json) lists nine episode states, calls and usage, sequential latency, scene hash, and full trajectory files. `episodes[].episode_file` points to corresponding `.json.gz`, which decompresses to original experiment exports. The report also records SHA256 of original and compressed files; unpublished keys, API addresses, account info, or per-call usage estimates are excluded.

Start the workbench, save an OpenAI-compatible connection named `gpt-6-astra` on the page, then repeat the same nine-episode setup using the repository's current scripts:

```bash
python scripts/benchmark_server.py --model gpt-6-astra --output runs/gpt6-server
```

The script uses the local 8090 service with the saved connection, retains `speed=4`, and does not read keys. It refuses to overwrite existing output directories; it stops on API errors, timeouts, or manual intervention, halting further experiments. Running produces real API calls.

Alternatively, set corresponding environment variables and use the existing CLI:

```bash
embodied-jev benchmark --provider chat --threshold 0 \
  --tasks transfer stack barrier --seeds 0 1 2 --max-cycles 12 \
  --timeout 600 --output runs/gpt6-astra.json
```

This command reuses task and decision settings, but the CLI omits web `speed=4` display waiting; total episode time cannot be directly compared to this table. Cloud requests are affected by network and service state, so reruns may yield variable results. Confirm model permissions and API quota before running.

Charts can be regenerated directly from the public report without keys:

```bash
python -m pip install -e '.[plots]'
python scripts/plot_experiments.py --report docs/results/gpt6-astra-2026-09-20.json
```

Download charts: [SVG](results/gpt6-astra-2026-09-20.svg) · [PDF](results/gpt6-astra-2026-09-20.pdf). Data tables: [Per-episode metrics](results/gpt6-astra-2026-09-20.csv) · [Per-step latencies](results/gpt6-astra-2026-09-20-latencies.csv).
