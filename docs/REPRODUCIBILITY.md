# Embodied experiment replication protocol

This document defines OmniJev Vision Preview embodied experiment output format and replication boundaries.

## Environment

Experiments require Python 3.12+, MuJoCo 3.13.0, and dependencies in `embodied/requirements.lock`. First execute:

```bash
./setup_embodied.sh
```

Model weights are not distributed with the repository. Download Nemotron 3 Nano Omni Q4_K_M GGUF and its matching projection file from the official model page of the selected local inference backend, place them in the backend model directory, and load them before setting:

```bash
export OMNIJEV_MODEL=omnijev-nemotron
export OMNIJEV_BASE_URL=http://127.0.0.1:1234
```

The rule baseline requires no model weights and can be used to verify the simulation installation first.

## Protocol

Each experiment fixes the task, seed, provider, observation mode, control mode, maximum cycles, timeout, perturbation, candidate shuffling method, and reasoning token budget. Each episode runs in a separate process; model errors, timeouts, and missing results remain in the denominator.

`manifest.json` records:

- Project git revision, Python version, and platform.
- Model ID, API endpoint, and strategy adapter SHA-256.
- provider, task, seed, observation/control mode, disturbance, and budget.
- Timing scope, ordering seed, and candidate shuffling rules.

## Output files

- `episodes.jsonl`: one-line summary per turn, including state, success flag, cycle count, physical contact, latency, and token count.
- `*.config.json`: full configuration for the turn.
- `*.json`: complete action, observation, physical trajectory, events, final state, and model request records.
- `*.requests.jsonl`: request payload configuration, input hash, response metadata, latency, and errors.
- `*.cameras.zip`: PNG frames, timestamps, and frame SHA-256 for visual turns.
- `summary.json`: summary grouped by provider.

## How to rerun

Run the same protocol in a new output directory:

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier --seeds 0 1 2 \
  --max-cycles 20 --output results/embodied/reproduction-run
```

If the output directory already contains `manifest.json`, the script only accepts a protocol exactly identical to the original. It can be resumed after interruption; failure records are not deleted or disguised as successful.

## Result interpretation

Skill mode executes preset skills and is suitable for comparing finite-choice decisions. Direct vision mode uses RGB observations for incremental control. Report the two modes separately. Task success, model call success, physical contact, and token usage must also be reported separately.

Simulation pauses while the model waits, so results cannot be extrapolated to control safety on real robots under network latency or reasoning wait times. Single-seed or small-sample results can only serve as demos or pilot experiments, not as generalization success rates.
