# OmniJev Preview

OmniJev is a multimodal research project for robot decision-making, providing a finite-choice decision SDK, an HTTP service, and a MuJoCo robotic arm workbench.

Jev maps unstructured states to structured decisions over predefined candidates, supporting routing, classification, and finite action selection. Robot decision-making also requires camera images, wrist views, and observations of changing scenes. OmniJev brings these visual inputs into the same decision workflow and provides simulation execution, trajectory replay, and reproducible evaluation.

The current version uses Nemotron 3 Nano Omni Q4_K_M and a compatible generation API for multimodal decisions. Vision-Jev with native RLCD training is under development. Coming Soon.

## Preview

### Embodied trajectory replay

![OmniJev workbench trajectory replay: transfer to tray](docs/media/omnijev-transfer.gif)

Trajectory replay of a released episode (`omnijev`, task *transfer to tray*, seed 0), redrawn
in the workbench's 3D scene. The caption reports the real record: the decision for each cycle,
its probability, the request latency, and the episode's call and token totals.
The MP4 is 1280×720 at 25 fps and worth downloading to step through a single decision; the GIF above is the same clip at 1000 px and 12.5 fps, small enough to load inline. [Re-export any saved episode](embodied/tools/trajectory-media/README.md) without a model backend.

This clip is **skill mode with privileged simulator state**: the model chooses among preset
skills and a program executes the IK trajectory. It is not an end-to-end visual planning
result and should not be read as one. Dual-camera vision input is a separate mode with
separately reported results, see [Embodied Experiments and Results Display](#embodied-experiments-and-results-display).

The other two workbench tasks, from the same seed and the same skill set:

| Block stacking | Transfer over barrier |
| --- | --- |
| ![OmniJev trajectory replay: block stacking](docs/media/omnijev-stack.gif) | ![OmniJev trajectory replay: transfer over barrier](docs/media/omnijev-barrier.gif) |
| Stack the red block on the blue one. 13 model calls, 39 output tokens, success. | Cross the yellow wall into the tray. 13 model calls, 39 output tokens, success. |

MP4s: [stack](docs/media/omnijev-stack.mp4) · [barrier](docs/media/omnijev-barrier.mp4).

### Multimodal decision probes

![OmniJev decision probes across twelve input families](docs/media/omnijev-decision-probes.png)

One record from each of the **twelve probe families** in `results/scored-records.jsonl`, using
the actual PNGs the model received. Clean reads, counting, spatial relations, a state that
contradicts the image, two-frame sequences, and — importantly — the abstention cases: no image,
an unobservable property, a blank frame, a color outside the candidate set. In all four, the
model returns **insufficient evidence** instead of guessing, which is the behavior the
finite-choice interface is built to make explicit. 208 of 208 non-audio requests valid and
correct; probability bars are softmax over option-letter logprobs, **not calibrated confidence**.

### Public multimodal benchmark pilots

![OmniJev versus baselines on four public multimodal subsets](docs/media/omnijev-benchmarks.png)

Four fixed pilot subsets — MMStar (300), MMBench DEV EN (60), MMAD DS-MVTec (45),
StreamingBench causal 8-frame (20) — with four strategies on the same frozen model. Read the
latency and token columns, not the accuracy column: **paired accuracy with direct short answer
on every subset**, and budgeted reasoning is 5.67 pp *higher* on MMStar. The measured advantage
is 6.8–13.6× faster medians and 51–86% fewer total tokens. Full protocol and caveats:
[Public Evaluation Findings](results/PUBLIC_EVALUATION_FINDINGS.md).

## Environment Requirements

- Core SDK and HTTP service: Python 3.9+.
- Embodied workbench: Python 3.12+; frontend build artifacts are included, no Node.js required for execution.
- Linux GPU inference: CMake 3.24+, a C++ compiler, and a CUDA Toolkit compatible with the driver. The validated configuration uses an NVIDIA A800 80GB with approximately 25GB of GPU memory for the model service; requirements on other hardware depend on context length and offloading configuration.
- Model files are approximately 26.1GB, and additional space is needed during installation for dependencies, compiled artifacts, and download cache.



## Quick Start

All commands are executed in the repository root directory. Source code can be obtained via GitHub's **Code → Download ZIP**, or downloaded from the Release as a source package and extracted.

### 1. Install SDK

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```



### 2. Download Model

Download the Q4_K_M main model and BF16 vision projection files to `models/Nemotron-Omni-GGUF/`:

```bash
python -m pip install -U huggingface_hub
export OMNIJEV_MODEL_DIR="$PWD/models/Nemotron-Omni-GGUF"
hf download lmstudio-community/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF \
  Nemotron-3-Nano-Omni-30B-A3B-Reasoning-Q4_K_M.gguf \
  mmproj-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16.gguf \
  --local-dir "$OMNIJEV_MODEL_DIR"
```

See the [Hugging Face model repository](https://huggingface.co/lmstudio-community/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF) for the model source and license. `OMNIJEV_MODEL_DIR` can specify an external model directory.

### 3. Build and Start Inference Backend

Linux CUDA build uses a fixed llama.cpp revision:

```bash
mkdir -p .cache/llama .cache/tmp
curl -L --fail https://codeload.github.com/ggml-org/llama.cpp/tar.gz/1aa2954bde90b1cb4d2dca96f90b07d7b155124b \
  -o .cache/llama/source.tar.gz
tar -xzf .cache/llama/source.tar.gz -C .cache/llama
export TMPDIR="$PWD/.cache/tmp"
cmake -S .cache/llama/llama.cpp-1aa2954bde90b1cb4d2dca96f90b07d7b155124b \
  -B .cache/llama/build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=native \
  -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build .cache/llama/build --target llama-server -j 8
./scripts/start_gguf.sh
```

`native` targets the machine's GPU; cross-compilation requires specifying the target CUDA architecture. If the driver requires CUDA-compatible libraries, specify the installed compatible library directory via `OMNIJEV_CUDA_COMPAT`. Precompiled backend can be specified via `OMNIJEV_LLAMA_SERVER`.

The model service listens on `127.0.0.1:1234`, with the default model alias `omnijev-nemotron`. `/health` returns 503 during loading and 200 once loading is complete.

### 4. Verify calls and start HTTP service

Open a new terminal in the repository root:

```bash
source .venv/bin/activate
curl --fail http://127.0.0.1:1234/health
python scripts/probe_backend.py --output results/backend-probe.json
python examples/sdk_demo.py
python -m omnijev.server --model omnijev-nemotron --base-url http://127.0.0.1:1234
```

Open [HTTP Decision Console](http://127.0.0.1:8765). When connecting to other compatible backends, set `--model` and `--base-url` separately. macOS Bionic users can also start the service using `./run_local.sh`.

### 5. Start Embodied Workbench

Open a new terminal in the repository root:

```bash
./setup_embodied.sh
./run_embodied.sh
```

For headless Linux environments, use `MUJOCO_GL=egl ./run_embodied.sh`. Open the [Embodied Workbench](http://127.0.0.1:8766) or [Benchmark Panel](http://127.0.0.1:8766/benchmarks). The rule baseline requires no model; OmniJev policies connect to the inference backend above.

### Remote Access

Service defaults to listening only on the loopback address. To access a remotely deployed instance via SSH forwarding, replace `user@server` with your SSH login address:

```bash
ssh -N -L 8766:127.0.0.1:8766 -L 8765:127.0.0.1:8765 user@server
```

After forwarding is established, browse to the above HTTP address.

## Embodied Experiments and Results Display

The console includes three tasks, rule baseline, fast decision, direct short answer, budgeted reasoning, Adaptive policy, single-step control, dual-camera input, disturbance, pause, single-step execution, trajectory replay, model comparison, JSON export, and benchmark panel. Existing results are saved in `results/`; after starting the service, they can be viewed from `/benchmarks`; new experiments use independent output directories.

Preset skill mode compares finite-choice decisions; direct vision mode sends camera RGB images to the model. Results for these modes must be reported separately. Skill-mode results cannot be treated as end-to-end visual planning performance.

Run a small embodied benchmark:

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers baseline omnijev omni_direct omni_reasoning \
  --tasks transfer stack barrier \
  --seeds 0 1 2 \
  --max-cycles 20 \
  --output results/embodied/my-run
```

Run direct vision and disturbance experiments:

```bash
.venv-embodied/bin/python scripts/benchmark_embodied.py \
  --providers omnijev omni_direct \
  --tasks transfer --seeds 0 \
  --observation vision --control incremental --max-cycles 60 \
  --intervention '{"kind":"target_shift","after_cycle":10,"delta_xy":[0.04,0]}' \
  --output results/embodied/my-vision-shift
```

### Export a trajectory as video or GIF

Any saved episode can be re-rendered without the inference backend. Forward kinematics is
recomputed from the archived `qpos`, and the browser scene is redrawn headlessly:

```bash
.venv-embodied/bin/python scripts/export_trajectory_frames.py \
  --episode results/embodied/skills-seed0/transfer-0-omnijev.json \
  --out embodied/tools/trajectory-media/data/transfer-omnijev

cd embodied/tools/trajectory-media
npx vite --host 127.0.0.1 --port 5199          # inspect the camera: ?data=transfer-omnijev
node shoot.mjs --data=transfer-omnijev --out=frames/transfer --orbit=8
```

The exporter verifies the episode's `scene_hash` before rendering, so an episode recorded on
a different scene is rejected instead of silently replaying the wrong motion. Encoding commands
for MP4, GIF and WebP are in [Trajectory Media Exporter](embodied/tools/trajectory-media/README.md).



## Experiment Recording and Reproduction

Each benchmark output directory saves:

- `manifest.json`: protocol, project revision, Python/platform info, model endpoint, and adapter hash.
- `*.config.json`: full configuration for each round.
- `episodes.jsonl`: summary lines for all rounds, including failed rounds.
- `*.json`: action, observation, trajectory, final state, camera metadata, and model call records.
- `*.requests.jsonl`: configuration, input hash, latency, token usage, and errors for each request.
- `*.cameras.zip`: PNG frames and frame hashes for vision experiments.
- `summary.json`: success count, call count, latency, token usage, physical contact, and failure type, summarized by provider.

Continue running only after protocol is fixed; different configurations must use new output directories. Model errors do not switch to rule policy, and failures remain in the denominator. Simulation pauses while waiting for the model, so the current benchmark does not measure the risk of continued robot motion during inference wait time on real hardware.

See [Embodied Reproducibility Protocol](docs/REPRODUCIBILITY.md) and [Public Evaluation Protocol](docs/PUBLIC_EVALUATION_PROTOCOL.md) for more protocol details.

## Python SDK Example

```python
from omnijev import OmniJev, Policy

client = OmniJev(model="omnijev-nemotron")
result = client.decide(
    question="Which bin should the workpiece in the image be placed in?",
    images=["data/assets/red.png"],
    state="Only the red and blue bins are currently available.",
    options=[
        {"id": "red_bin", "description": "Place in the red bin"},
        {"id": "blue_bin", "description": "Place in the blue bin"},
        {"id": "unknown", "description": "Insufficient evidence", "abstain": True},
    ],
    policy=Policy(max_latency_ms=3000),
)
print(result["status"], result["action"])
```



## Testing and Development

```bash
python -m unittest discover -s tests -v
.venv-embodied/bin/python -m pytest embodied/tests -q
```

After modifying the frontend, run `npm ci && npm run build` in `embodied/` and then restart the embodied service.

The project's historical experiment results, data descriptions, model cards, and third-party licenses remain preserved in `results/`, `data/`, and `THIRD_PARTY_NOTICES.md` for auditability and reproducibility.