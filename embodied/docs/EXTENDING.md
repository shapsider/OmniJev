# Extension and secondary development

Top **Extension** provides model configuration, scene presets, and independent input testing. Existing tasks can directly adjust parameters; adding new robots or task logic requires modifying code.

![Extended page: Model configuration](extensions-models.png)

## Save multiple model interfaces

Name each connection, fill in interface type, address, model ID, and Key, save as model configuration. Both single experiments and model comparisons can select them. The same OpenAI-compatible protocol can save multiple platforms, different models, and their respective Keys without having to overwrite the same connection back and forth.

Supports TypeSafe Jev, OpenAI-compatible chat, Claude-native Messages, and structured decision services. Model IDs follow the service provider's actual open name, and can be validated via input testing after saving. The original "Model Connection" entry remains usable.

When starting via `embodied-jev serve`, the Key is stored in the system keychain, connection information is stored outside the repository, and can be restored after restart. When system storage is unavailable, the page displays "session only" and does not save the plaintext Key. The storage location and in-memory mode are described in [Technical Guide](TECHNICAL_GUIDE.md#models).

Key does not fill into the password field, nor does it enter preset or experiment export. After changing the interface address, Key must be re-entered; experiment input will check for mispasted credentials. Authentication information is only used for the service provider you configure.

## Create scene presets

Select Transfer to tray, Block stacking, or Transfer over barrier as the physical template, name the new preset, modify the object start position, target position, and barrier height. Applying the preset will rebuild the real simulation, not automatically invoke the model.

- `source_xy`: block start point, unit meters; fixed position when explicitly filled. Leave empty to use original seed with random perturbation.
- `target_xy`: Target position; move the tray or support block and its surrounding edge together.
- `barrier_height`: Only used for the transfer over barrier template, range 0.02–0.16 meters; other templates do not use this field.
- `user_context`: Additional JSON context for model reference, not replacing sensor feedback or physical success conditions. Object and target information is provided by the selected observation mode; do not enter ground truth coordinates here for direct visual experiments.

For example [transfer-preset.json](../examples/transfer-preset.json):

```json
{
  "format": "embodied-jev-preset-v1",
  "name": "Transfer practice · Fixed start point",
  "task": "transfer",
  "scene_config": {
    "name": "Transfer practice · Fixed start point",
    "source_xy": [0.42, -0.17],
    "target_xy": [0.44, 0.18]
  },
  "user_context": {
    "experiment_note": "Compare choices at a fixed object and destination position."
  }
}
```

Preset is saved in the current browser and can be exported to JSON for use in other browsers. When applied, it checks fields, ranges, initial object spacing, and key position accessibility; task completion is determined by the physical state after execution.

The same preset can also be used from the command line:

```bash
embodied-jev benchmark --preset examples/transfer-preset.json \
  --seeds 0 --provider baseline --output runs/custom-scene.json
```

When switching to model provider, need to set environment variables according to standard CLI evaluation settings; `benchmark` does not read the keychain connection saved by the web service.

The current preset editor is based on three existing task types, supporting position, obstacle height, and supplementary input. Opening doors, inserting or replacing robots requires corresponding objects, actions, and success conditions; it is not an arbitrary robot or free 3D scene editor. The rule baseline does not read natural language requirements to change strategy.

## Separate test input and candidate

In **Input Test**, select a model, fill in JSON state, decision question, and candidates, then click Test to view the selection, probability source, and duration. This entry does not execute robotic arm actions.

For example, candidate JSON:

```json
{
  "approach": "Move above the object before descending.",
  "grasp": "Close the gripper at the object's current position.",
  "hold": "Keep the current pose."
}
```

It can be used to check interface format, or compare the impact of language, candidate order, and state changes on selection. The options here are test data, not yet connected to the actuator. The rule baseline returns only fixed candidates, suitable for checking page flow.

API testing will send input and may incur costs. Key please fill in the password field of the model configuration.

## Code extension location

| What to add | Where to start | What needs to be connected |
| --- | --- | --- |
| New model of the same protocol | Named model configuration on the page | Address, model ID, authentication, real call verification |
| Model of different protocols | `policies.py` | request, candidate verification, return format, latency and usage |
| New scenario parameters | `scenarios.py`, `physics.py` | configuration validation, XML object, scene hash, replay geometry |
| New task type | `physics.py`, `planning.py`, `incremental.py` | object, contact and success conditions; skill mode phases and goals; incremental mode task description |
| New candidate actions | `planning.py` or `incremental.py`, and `runtime.py` | skill goal or fixed short step, gripper command, safety check, execution and Chinese display |
| New observation input | `perception.py`, `runtime.py`, `evidence.py`, `incremental.py` | image/state adaptation, calibration, tracking and source; direct images must not mix with object ground truth |
| Incremental action | `incremental.py`, `runtime.py` | fixed XYZ/gripper menu, safety check after selection, actual transfer history; do not mix with preset phases |
| New robot | `physics.py` and asset directory | joint/executor, IK, gripper contact, collision and reachable range |
| New interface | `frontend/` | configuration form, responsive display, real API, browser testing |

When adding a task ID or provider, remember to update backend request verification, frontend options, and tests. JSON presets accept data only, do not execute scripts or load arbitrary MJCF.

Welcome to share model adaptation, task templates, scene presets, or failure experiments via PR, please include reproduction command and actual results.
