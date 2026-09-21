# Model Comparison

Under the same task, start, and action budget, observe how MiniCPM, Jev, GPT, Claude, and others choose. Currently, [GPT-6 Astra's nine-round real API experiment](GPT6_EXPERIMENT.md) is public; counterexamples with Jev, Claude, etc., under the same settings are pending. Cloud models require you to configure permissions yourself.

## Running Side-by-Side in the Web Interface

1. Save the interface in **Model Connection** and test calls, or save multiple named connections in **Extension**. Changing model IDs requires revalidation.
2. Open **Model Comparison**, select 2–3 models, set common task, seed, control method, observation source, camera combination, preview, probability threshold, and action budget. Direct image comparison requires a connection that supports images. You may use different models via the same API or different platform connections.
3. Choose **Sequential Run** or **Parallel Run**, then click Start. Default is sequential; parallel supports up to two paths.
4. View each path's scene, stage, actions, call count, tokens, and duration. You can pause, resume, or stop all, then export the full record.
5. After pausing or completing, replay using a shared timeline based on elapsed simulation time. Models that finish early stop at the last frame.

Without a Key, you can first use two-path rule baselines to check operation flow. Model call failures are logged; models with candidate probabilities below the threshold are marked `uncertain`, ending that path's experiment while continuing others.

Each path has an independent physical world. In parallel, the first-returning model can act without waiting for others. MiniCPM shares the same model instance and inference lock, so local inference remains serial. When comparing latency, we recommend sequential runs and recording cold start, hardware, and background load.

Replay reads only this run's record, not re-invoking the model. It aligns with simulation time, excluding API wait-induced visual pauses; real wait time remains in the experiment log. Current support includes in-process posture replay; there is no import entry for historical files. openroboto's three-column page also uses recorded replay; source explanation is in [Fast Inference Analysis](FAST_INFERENCE.md).

Scene presets applied after comparison use the same `scene_config` and `user_context` across paths, retaining detailed configuration in export. To compare different scenes or inputs, create separate experiments and save exports. See [Extension Guide](EXTENDING.md) for usage.

## Command-Line Access

| Model Path | provider | Configuration |
| --- | --- | --- |
| MiniCPM5-2B FP16 | `minicpm` | `EMBODIED_MINICPM=1`, local weights, MPS/CUDA |
| GPT / platform-provided Claude | `chat` | `EMBODIED_API_BASE`, `EMBODIED_API_MODEL`, `EMBODIED_API_KEY` |
| Claude native | `claude` | `EMBODIED_CLAUDE_BASE`, `EMBODIED_CLAUDE_MODEL`, `ANTHROPIC_API_KEY` |
| TypeSafe Jev | `jev` | `TYPESAFE_API_KEY`, `TYPESAFE_MODEL` |

Model ID uses the account or platform-available name, e.g., publicly used `gpt-6-astra` in experiments. Intermediate platforms may use vendor-prefixed IDs. Enter the model name, not the development tool name.

First set the corresponding environment variables, then run the following command. `benchmark` does not read the web server-stored keychain configuration; do not put the Key in command-line arguments, repositories, or reports.

```bash
# MiniCPM: Disable the uncalibrated probability threshold
embodied-jev benchmark --provider minicpm --threshold 0 \
  --tasks transfer stack barrier --seeds 0 1 2 --max-cycles 30 \
  --output runs/minicpm.json

# Cloud model: first configure API, and account for the cost of batch calls
embodied-jev benchmark --provider chat --threshold 0 \
  --tasks transfer stack barrier --seeds 0 1 2 --max-cycles 30 \
  --output runs/chat.json

embodied-jev benchmark --provider claude --threshold 0 \
  --tasks transfer stack barrier --seeds 0 1 2 --max-cycles 30 \
  --output runs/claude.json

# Jev: Pin to a version available to the account
TYPESAFE_MODEL=jev-1.13.0 embodied-jev benchmark --provider jev --threshold 0 \
  --tasks transfer stack barrier --seeds 0 1 2 --max-cycles 30 \
  --output runs/jev.json
```

Each evaluation generates a summary file and full JSON for each round. No automatic cost limit; the page does not show unknown prices as zero, but you can calculate based on exported usage and the vendor's daily price.

## How to make results comparable

- Fixed code, prompt version, task, seed, scene hash, action budget, and preview switch.
- Fixed control method, observation source, camera combination, and perturbation settings. Preset skills and incremental XYZ, ground truth coordinates and original image grouping reports; cannot directly merge into a single model ranking.
- Use the same input information and action menu. Preset skills' goals are code-generated; incremental mode selects short steps via the model, both relying on program-provided motion control and safety checks.
- Main comparison sets probability threshold to 0. Chat and Claude interfaces have no native candidate probability; using different thresholds changes stop conditions.
- Record success, failure, stall, timeout, action count, call count, input/output tokens, latency, and full trajectory together.
- Separately report cold start and post-warmup latency; API time includes network, local time is affected by device and background load.
- FP16, MLX 4-bit, GGUF Q4/Q8 quantization recorded separately; quantization method and prompt template may affect choice. Costs calculated per actual billing rules.

A small number of seeds for the three tasks are suitable for development checks. Formal comparison also requires adding seeds and scenes not involved in tuning, freezing prompts, and publishing all failures. Output methods for different interfaces should also be documented in the report: MiniCPM reads candidate logits, chat generates JSON, Claude native returns tool parameters.
