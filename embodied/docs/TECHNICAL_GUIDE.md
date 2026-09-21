# Technical Guide

Xingzhi uses MuJoCo to simulate Franka Panda. The model can choose preset skills or select XYZ short steps and gripper actions based on each round of observation. Observation sources include simulated state, RGB-D detected coordinates, and direct camera images. The browser handles display and control, while the Python service manages physics, model requests, and experiment logging. Installation command see [README](../README.md#-zero-robot-basics-quick-start), multi-model experiments see [Comparison Guide](COMPARISON.md).

After installation, rule baseline requires no GPU, Key, or model download; the built page also does not depend on external fonts or CDN. Multiple browser tabs of the same service share a single experiment and model comparison state.

<a id="models"></a>

## Model access and configuration saving

Click the plug icon next to **Decision Model**, fill in interface address, model ID, and Key. Saving does not invoke the model; **Test Call** sends a small request, **Run Experiment** continuously requests decisions, and cloud costs are charged by the service provider.

When starting via `embodied-jev serve`, the Key is stored in the system keychain and restored after service restart. URL, model ID, configuration name, and other info are stored separately outside the repository:

| System | Connection Information Directory |
| --- | --- |
| macOS | `~/Library/Application Support/EmbodiedJev` |
| Windows | `%LOCALAPPDATA%/EmbodiedJev` |
| Linux | `$XDG_CONFIG_HOME/embodied-jev`, use `~/.config/embodied-jev` if not set |

When the system keychain is unavailable or access is denied, the page displays "Session Only"; refreshing retains configuration, but restarting the service does not restore this change. The program does not store keys in plaintext files. After saving passwords, they are not filled back, nor are they stored in browser storage, scene presets, experiment exports, or logs. Changing the interface address means empty passwords will not reuse the old address's key.

You can also set environment variables before startup; see [`.env.example`](../.env.example); the program does not automatically read `.env`. Successfully restored saved connections take precedence over environment variables of the same interface type. Running `benchmark` separately still requires environment variables and does not automatically use web-saved connections.

If you only want to temporarily use the configuration, run `embodied-jev serve --memory-only`, or set `EMBODIED_JEV_PERSISTENCE=memory`. This skips system storage, and keys are cleared when the service exits.

Saved, unverified, verified, and failed states are displayed separately. Editing a configuration invalidates its previous verification; editing it during a test discards the old test result. Connection tests and independent input tests allow at most two concurrent requests in total. Model errors stop the corresponding experiment and preserve the failure record.

### OpenAI Compatible API

Select **OpenAI Compatible API**, fill in the Base URL, model ID, and Key provided by the platform. The address usually ends with `/v1`, and the program adds `/chat/completions`. It supports cloud platforms and local services compatible with this protocol, with actual available models depending on the selected service.

The adapter places state and candidates into `messages`, requiring a return of `{"choice":"candidate_id"}`, and checks whether the selection belongs to the current candidates. If the platform does not accept `response_format`, JSON mode can be disabled, but the response content must still be valid JSON. The chat interface does not provide native candidate probabilities, so model-reported probabilities are not used, nor are probability thresholds applied.

Direct visual planning also sends the current step's camera PNG via the `image_url` content block. Stepwise planning responses allow attaching `intent` and `visual_evidence`, each up to 240 characters, for interface display of action intent and visible evidence. These are brief public descriptions, not internal model reasoning; correctness must be verified by actual execution results.

```bash
export EMBODIED_API_BASE=https://your-provider.example/v1
export EMBODIED_API_MODEL=your-model-id
read -s EMBODIED_API_KEY
export EMBODIED_API_KEY
embodied-jev serve --port 8090
```

### MiniCPM5-2B

```bash
python -m pip install -e '.[minicpm]'
export EMBODIED_MINICPM=1
export EMBODIED_DEVICE=auto
embodied-jev warmup
embodied-jev serve --port 8090
```

After selecting **MiniCPM5-2B**, the service loads `openbmb/MiniCPM5-2B`, with a fixed weight version `12a3808a956f869c767195e9266b59c4d21d92e2`. The initial download is about 5 GB, and additional memory is required for execution. `auto` sequentially attempts CUDA, Apple MPS, and CPU; MPS/CUDA use FP16, while CPU uses FP32. Apple Silicon can set `EMBODIED_DEVICE=mps` to explicitly specify the GPU.

`warmup` loads the model and performs one real two-candidate decision before exiting. The web service loads its own model instance from the download cache; resetting experiments within the same service reuses weights. The page displays loading, ready, and error states. After the cache is complete, `HF_HUB_OFFLINE=1` can be used to disable model download requests.

```bash
EMBODIED_MINICPM=1 EMBODIED_DEVICE=mps embodied-jev benchmark \
  --provider minicpm --seeds 0 1 2 --threshold 0.55 \
  --timeout 600 --output runs/benchmark-minicpm.json
```

Evaluation saves summary and full records for each task/seed, including actual calls, weight versions, devices, latency, probabilities, and physical results. When below the threshold, batch experiments are marked `uncertain` and end the session; `--threshold 0` disables the threshold.

The local adapter uses a non-thinking chat template, reads the next token logits of candidate letters, and applies softmax only to these candidates. It checks the full prompt's token boundaries, with a context limit of 4096 tokens. Candidate probabilities indicate relative preference but are not yet calibrated to action success rates; real reasoning for the current three tasks has not yet succeeded, see [Validation Record](VALIDATION.md). Quantized weights exist in MLX/GGUF versions, but this project has not yet integrated these backends.

### Claude Native Messages API

Select **Claude Native API**, with the default address `https://api.anthropic.com/v1`, and the program adds `/messages`. The model ID defaults to `claude-fable-5-1`, requiring account or platform confirmation that this model is available.

```bash
export EMBODIED_CLAUDE_BASE=https://api.anthropic.com/v1
export EMBODIED_CLAUDE_MODEL=claude-fable-5-1
read -s ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY
embodied-jev serve --port 8090
```

Requests use `x-api-key`, `anthropic-version: 2023-06-01`, and `max_tokens: 1024`, with candidate selection constrained by `select_action` tool enumeration parameters. Return values can only choose existing actions and will not execute code generated by the model. Truncation, rejection, unknown candidates, format errors, or multiple tool calls will terminate this decision; the record retains model name, usage, and latency.

Direct visual mode uses the native `image` content block. Stepwise planning tool parameters also allow returning brief `intent` and `visual_evidence`. Current Jev, structured decision services, and local MiniCPM adapters only accept state inputs.

See [Messages API](https://platform.claude.com/docs/en/api/messages) and [Model List](https://platform.claude.com/docs/en/models/overview). Anthropic's [OpenAI SDK compatible layer](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) has parameter limits, such as ignoring `response_format`; when using a transfer service, select the entry based on its actual provided protocol.

### TypeSafe Jev

```bash
read -s TYPESAFE_API_KEY
export TYPESAFE_API_KEY
export TYPESAFE_MODEL=jev-latest
embodied-jev serve --port 8090
```

After selecting **TypeSafe Jev**, requests are sent to `https://api.typesafe.ai/v1/systemone`. A TypeSafe Key with access permission is required; during comparative experiments, you may change `jev-latest` to a fixed version supported by the account. See [official API documentation](https://docs.typesafe.ai/api).

### Structured Decision Service

```bash
export EMBODIED_LOCAL_URL=http://127.0.0.1:8078/v1/systemone
export EMBODIED_LOCAL_MODEL=minicpm-jev
# Set when authentication is required EMBODIED_LOCAL_KEY
embodied-jev serve --port 8090
```

The service accepts `{model, state, questions: {action: {type: "choice", instructions, criteria}}}` and returns `{model, answers: {action: {choice, probabilities}}, usage}`. Each candidate must have a probability, values are bounded and sum to approximately 1, and the selected option should have the highest probability.

[openroboto's adapter](https://github.com/openroboto-ai/jev-robot-control/blob/7a4ed8b72c3c17d7aa790678ed9660df67c10dd3/incremental_policy.py) also uses OpenRouter's experimental address `https://openrouter.ai/api/alpha/decisions` and model `typesafe/jev-1.13`. In Xingzhi, you can fill in this full address and the OpenRouter Key with access permission via **Jev / Structured Decision API**. Ordinary chat interface permissions do not imply access to this route; this project has not yet tested this service.

## How a single decision is executed

**Preset skill mode (`skills`)**: First filter feasible stages based on object, goal, and contact information, then let the model choose the stage and action. Skill goals are generated by the program; if there is only one stage, use it directly and record that no model call is needed. If preview is enabled, the program first checks candidates in a simulation copy, and the model selects from the remaining actions. Input retains the results of the last two actions.

**Incremental mode (`incremental`)**: Each round provides the same 21-action menu: 40, 10, and 2 mm displacements in positive and negative directions for the XYZ axes, as well as gripper open, close, and hold. The model selects one step based on current observation and the last six actual results, without stage filtering. After selection, range and safety checks are performed; rejected actions and reasons enter feedback, and the program does not automatically change the action. See [incremental planning](PLANNING.md) for the full process.

Both modes use damping least squares IK and joint actuators to complete actions, then read the new state. Interfaces with native candidate probabilities will check the probability threshold; Chat / Claude do not have this type of probability and do not use the model's self-reported probabilities.

Physical step size is 0.002 seconds, i.e., 500 steps per simulated second; pose recording is about 25 frames per simulated second. The camera samples at the boundary between decision and action, and model calls have their own waiting time. These three frequencies are calculated separately. Full input, candidate, and pre- and post-execution states are all saved in history.

The experiment stops as `stalled` when three consecutive actions in the same phase produce almost no pose change and leave contact and gripper evidence unchanged. Incremental mode also requires the same action to have been selected three times. The system retains the result, does not choose the next action for the model, and does not automatically switch to the rule baseline.

Grasping relies on actual contact between bilateral fingers and free objects. Success conditions include target support contact, XY error less than 25 mm, speed less than 25 mm/s and stable for at least 0.4 seconds, gripper open, and end-effector height at least 170 mm. Support blocks for stacking tasks are fixed on the table. Collision monitoring currently covers partial end-effector/link/finger contact with the table and obstacles, but is incomplete.

The end-effector currently faces fixed orientation, and the model cannot generate joint code on its own. Simulation state and RGB-D mode provide coordinates to the model; direct visual mode provides the original RGB from the selected camera, calibration, and robot's own feedback, without providing true coordinates of blocks or goals. The latter is used for incremental control and does not go through skill generation dependent on coordinates. Camera configuration see [Vision Description](VISION.md). Extension is still needed for unknown objects, arbitrary tasks, and real-machine control; sources and limitations of fast reasoning see [Source Code Analysis](FAST_INFERENCE.md).

### Modify Candidate Actions

Preset skills are defined in `planning.py`: `eligible_phases()` filters stages, `candidates()` generates target coordinates, gripper instructions, and duration. The incremental action menu and input organization are in `incremental.py`, and the execution loop and post-selection safety checks are in `runtime.py`.

| Modification Content | Code Location |
| --- | --- |
| Stage Name and Chinese Display | `PHASES` and frontend stage mapping |
| Stage Explanation to Model | `PHASE_GUIDANCE`, retains corresponding displacement and gripper information |
| Goal, Duration, or New Action | `candidates()`, simultaneously checks preview, execution, and contact feedback |
| New Stage | Stage selection, candidate generation, and frontend mapping all need updates |
| Incremental displacement magnitudes or gripper options | The fixed menu in `incremental.py`, plus execution and rejection feedback in `runtime.py` |

"Input test" can edit test candidates, but executable actions in the workbench are still defined by code. Options can be in Chinese; changes in language, order, and candidate set may affect the model, requiring version recording and retesting. `direct` and `gentle` currently use the same endpoint but differ in execution duration.

## Logs, Pause, and Concurrency

Each round retains up to 200 run events; the page displays the latest 12, and export includes all retained events. When file logging is needed:

```bash
embodied-jev serve --port 8090 --log-file runs/server.jsonl
```

JSONL logs rotate at 2 MB, keeping three backups. Logs record only agreed fields, not request bodies, keys, or original service provider errors. Polling log access is disabled; polling frequency is reduced when the page is idle or hidden.

Control requests carry the experiment ID. Old tabs reset to new experiments receive HTTP 409; repeating start does not overwrite ongoing single steps. After stopping or resetting, even old model requests that return will not execute their actions. HTTP requests may still wait for response or timeout. Comparison experiments also have independent IDs and the same expiration check.

## Extensions and Development

**Extension** page manages named model configurations, scene presets, and independent input tests. Presets can also be used with `benchmark --preset file.json`; see [Extension Guide](EXTENDING.md) for details. Context and simulation observations are saved separately without replacing location, contact, or success conditions.

Related interfaces include `GET/POST /api/model-profiles`, `POST /api/presets/validate`, and `POST /api/decision/probe`. Experiments select a connection via `profile_id`, and the provider must match. Each round uses a copy of the connection at creation; subsequent configuration changes do not affect the addresses and keys of already running experiments.

```bash
python -m pip install -e '.[test]'
pytest -q
embodied-jev benchmark --output runs/benchmark.json
# UI Tests use a separate 8099 port; build the frontend first
npm run build
npx playwright install chromium
npm run test:ui
# With the backend already running on 8090 start the frontend with hot reload
npm run dev
```

Source code is located in `src/embodied_jev/` and `frontend/`; tests are in `tests/` and `tests-ui/`. `npm run build` packages web resources into the Python package, and a wheel build also requires running this command. Test results and known failures are in [Validation Record](VALIDATION.md).

Sources are listed in [Reference Mapping](REFERENCES.md). Original code uses the MIT license; Panda models and meshes retain their Apache-2.0 license, as detailed in [Third-Party Notices](../THIRD_PARTY_NOTICES.md). Model weights are downloaded separately and are subject to their respective licenses.
