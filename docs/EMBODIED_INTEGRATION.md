# OmniJev Vision Preview: Embodied Workbench and benchmark

## Project Scope

This directory provides a MuJoCo robotic arm workbench that can be installed, run, recorded, and reproduced from scratch. It combines finite-choice decision-making, RGB observations, simulated body states, physical execution, and terminal verification within a single local workflow. Experiment result panels are read locally from `results/`, and results of models that were not actually run are not shown as successful.

| Module | Current Implementation |
|---|---|
| `physics.py`, Panda assets | MuJoCo physics, IK, contact, grasping, support, and terminal verification; assets visible at `embodied/src/embodied_jev/assets/panda/LICENSE` |
| `planning.py`, `incremental.py` | Skill menu and fixed 21 XYZ / gripper actions; skills and incremental control recorded separately |
| `perception.py` | External / wrist RGB, RGB-D estimation, timestamps, and observation archiving |
| `runtime.py`, `comparison.py` | Pause, stop, action preview, replay, independent same-seed simulation, model comparison, and export |
| Browser workbench | Trajectory rendering, visual input inspection, perturbation, comparison, export, and benchmark navigation |
| `omnijev/embodied_policy.py` | Four local strategies, prompt construction, candidate score parsing, stable action ID mapping; model errors do not auto-answer |
| `scripts/benchmark_embodied.py` | Independent process, fixed random order, failures retained, protocol-resume reruns, token / physical metrics and runtime environment recording |
| `omnijev/embodied_web.py` and `web/benchmarks.html` | Local model state and result panels, separately showing public Q&A and embodied rounds |

Project license and third-party notices are in `embodied/LICENSE` and `embodied/THIRD_PARTY_NOTICES.md`. This project uses locally compatible API calls for visual backbones, does not implement TypeSafe Jev's internal architecture, native decision protocol, or RLCD training.

## Installation from scratch, startup, and browser usage

```sh
# First installation only; Python 3.12+.Model weights are not downloaded.
./setup_embodied.sh
# Start the workbench
./run_embodied.sh
```

Visit `http://127.0.0.1:8766`; the results panel is at `/benchmarks`. The service listens only on the loopback address and uses memory mode by default. Built frontend assets are included, so Node is not required to run it; rebuild only after modifying the frontend. Model download, directory, and backend startup steps are in [README](../README.md).

1. Keep the "rule baseline", choose transfer to tray / block stacking / transfer over barrier, then click run to check installation and physical environment. Rule call count is zero.
2. After inference backend is ready, select "OmniJev · Fast decision", which allows single step, pause, stop, reset, replay, and export. Model requests and execution results are recorded in round export.
3. "Preset skill selection + simulation ground truth" is used for skill decision acceptance; the program executes skill internal trajectory, and the model does not see camera images.
4. Visual experiment selection "incremental XYZ + direct image + external or dual-camera". The model receives RGB and body feedback, but not object / target true coordinates; safety preview and terminal assessment still use simulated ground truth. View actual input on the "Visual" page and download camera archives for verification.
5. In "Model Comparison" select 2–3 strategies, default serial to avoid local resource contention. Each path is an independent world; replay is aligned by simulation time, not actual reasoning duration.
6. Enable target / object displacement perturbation in execution settings to observe subsequent adjustments. Perturbation is not a model action; whether recovery must be judged by actual trajectory.

Set model parameters through environment variables at startup:

```sh
OMNIJEV_MODEL=omnijev-nemotron \
OMNIJEV_BASE_URL=http://127.0.0.1:1234 \
OMNIJEV_REASONING_TOKENS=4096 \
./run_embodied.sh
```

`OMNIJEV_REQUEST_TIMEOUT` default 180 seconds; `OMNIJEV_PORT` default 8766. When the model is offline, the interface explicitly shows not ready, but rule demonstration remains available; model request errors terminate the round and do not automatically switch rule strategy.

## Four local strategies

| Strategy | Actual Call | Notes |
|---|---|---|
| OmniJev | Single-letter generation, 4-token limit, thinking disabled, top-10 logprobs | Uses the existing generation API, not a new zero-decoding architecture |
| Direct | Same input, sampling and 4-token upper limit, no logprobs requested | Baseline without logprobs |
| Reasoning | medium, T=0.6 / top_p=0.95, default total output limit 4096 | Different from public QA evaluation 20480 upper limit, report separately |
| Adaptive | First fast request; if score missing or margin < 0.2 then real request reasoning | Heuristic experimental feature, uncalibrated or unproven better than baseline; both costs billed |

21 actions usually exceed top-10 coverage, so score may be unavailable; cannot fabricate probability. Adaptive upgrades to reasoning when score missing, possibly more expensive than fixed reasoning. Invalid output, truncation, or fast path thinking all record error, retain known token cost, do not select action.

When browser switches to local strategy, additional candidate score threshold defaults to zero because token softmax is not calibrated task success rate; simulation action preview remains on. User can still choose non-zero threshold for abstention experiment. benchmark fixed threshold zero, avoiding extra filtering only for strategies with scores.

## Reproducible benchmark

Public QA: existing 425 questions × 4 methods records, statistics, and charts remain. See [Public Protocol](PUBLIC_EVALUATION_PROTOCOL.md), not embodied success rate.

Embodied skill pilot experiment:

```sh
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier --seeds 0 1 2 \
  --max-cycles 20 --reasoning-tokens 4096 \
  --output results/embodied/my-skills-run
```

Direct visual and perturbation experiments should be in separate directory:

```sh
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers omnijev omni_direct --tasks transfer --seeds 0 \
  --observation vision --control incremental --max-cycles 60 \
  --intervention '{"kind":"target_shift","after_cycle":10,"delta_xy":[0.04,0]}' \
  --output results/embodied/my-vision-shift
```

Each round executed by independent process, saving original scene hash, strategy version, action / observation / trajectory, incremental request configuration, input hash, actual usage, failure, and camera archive. `manifest.json` also records project git revision, Python version, platform, model endpoint, and adapter hash. Fixed sort seed 20260921, generated seed 20260919. Full protocol written to manifest; existing output can only continue with same protocol, cannot overwrite failure. Denominator includes all rounds.

Report task success rate, round wall-clock time, API call count, input and output tokens, prohibited contact count, budget exhausted / stall / abstention / error. Zero model call rule strategy cannot be explained by reasoning accuracy; skill baseline success does not prove end-to-end visual planning.

Physical simulation pauses while waiting for model, so this benchmark cannot measure control risk of environment evolving during inference. Small sample cannot confirm non-inferiority, generalization, or reliability on real machines. Upstream unpublished Jev hierarchical XYZ development mode not claimed reproduced.

## Development and validation

```sh
.venv-embodied/bin/python -m pytest embodied/tests -q
python3 -m unittest discover -s tests
# After modifying the frontend source
cd embodied
pnpm install --frozen-lockfile
pnpm run build
```

Local core SDK can still be used without separate MuJoCo installation; embodied workbench depends on `.venv-embodied`. Upstream tests, OmniJev adaptation contract, real physical rounds, and browser acceptance are recorded separately, not conflating stub tests with real model evaluation.

## Re-evaluating public subset

Source package includes scores and scripts, not third-party original media. First run `python3 scripts/download_public_data.py`; charts depend on `matplotlib`, video preparation depends on `imageio-ffmpeg` (install as needed). Preparation and evaluation should use new directory, e.g.:

```sh
python3 scripts/public_benchmark.py --prepare-only --out results/mmstar-new
python3 scripts/prepare_extra_benchmarks.py mmbench --out results/mmbench-new
python3 scripts/public_benchmark.py --out results/mmbench-new
python3 scripts/report_public_benchmark.py --out results/mmbench-new
python3 scripts/audit_public_results.py --out results/mmbench-new
```

MMAD and StreamingBench rename preparation command names to `mmad` and `streaming`. Public QA script currently calls local `omnijev-nemotron`; changing backbone requires modifying protocol and call configuration and saving results separately. Old manifest absolute media paths record original experiment source; new machines must re-prepare media, cannot infer directly from them.
