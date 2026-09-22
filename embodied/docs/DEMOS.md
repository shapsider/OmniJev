# Demo and Video Export

This release ships one generated demonstration, drawn from a saved experiment record. No model
is re-requested and no policy or physics is re-executed: the renderer replays the archived
`qpos` stream.

| Demo | Episode | Frames | Simulated time | Media |
| --- | --- | ---: | ---: | --- |
| Trajectory replay — transfer to tray | `results/embodied/skills-seed0/transfer-0-omnijev.json` | 283 | 11.198 s | [MP4](../../docs/media/omnijev-transfer.mp4) · [GIF](../../docs/media/omnijev-transfer.gif) · [WebP](../../docs/media/omnijev-transfer.webp) |

The MP4 is 1280 × 720 at 25 fps, suitable for pausing on a single decision. The GIF is the same
clip at 1000 px and 12.5 fps, about 3 MB, so it can be embedded inline in the README. Both are
rendered from the workbench's own Three.js scene — same background, lights, materials and home
camera as `../frontend/robot-scene.js` — so the media matches what the browser shows.

## What the demonstration is, and is not

The episode is **skill mode with privileged simulator state**. At each cycle the model receives
structured simulator state and selects among a small set of preset skills; the selected skill's
IK trajectory is then executed by program code. The caption reports the episode's real record:
the chosen option, its probability where the backend supplies logprobs, the request latency, and
the call and token totals.

- It is **not** end-to-end visual planning. No image reached the model in this episode. Vision
  episodes (dual camera, incremental control, no ground-truth object coordinates) are a separate
  mode with separately reported results; see [Visual Observations](VISION.md).
- The 3D scene is a visualisation of **simulator state**, not of model input.
- Replay is not real-time playback of the robot or the model. Each frame is a saved pose; there is
  no re-simulation, so contact and grasp events are read from the record rather than recomputed.
- Camera originals for vision episodes are archived separately as `*.cameras.zip`, with a SHA-256
  per image. Those PNGs — not this replay — are what the model actually received.

## How to read the panel

- **Cycle counter and phase** — position in the episode's decision sequence and the execution
  phase selected for that cycle (`approach`, `descend`, `grasp`, `lift`, `carry`, `lower`,
  `release`, `withdraw`).
- **Option and probability** — the model's choice from the finite candidate set, with the
  provider-reported probability. A missing probability means the backend returned none; it is not
  a confidence of zero, and a high probability is not a task success rate.
- **Request latency** — the measured model call time for that cycle, taken from the episode's
  `model_latency_ms`.
- **Observation, control, policy, calls, tokens, wall clock** — the episode's recorded
  configuration and totals. These are read from the file, not re-estimated.
- **SUCCESS badge** — shown on the final frame only when the episode's own physical final state
  check reports success.

## Re-export from a saved record

The pipeline needs `mujoco` (already in `requirements.lock`) and `ffmpeg`; the browser side
reuses the `vite` and `playwright` dev dependencies of `embodied/`.

```bash
# 1. Rebuild MuJoCo forward kinematics from the episode and verify its scene hash.
python scripts/export_trajectory_frames.py \
  --episode results/embodied/skills-seed0/transfer-0-omnijev.json \
  --out embodied/tools/trajectory-media/data/transfer-omnijev

# 2. Serve the renderer and pick a camera.
cd embodied/tools/trajectory-media
npx vite --host 127.0.0.1 --port 5199     # open http://127.0.0.1:5199/?data=transfer-omnijev

# 3. Dump one PNG per frame with headless Chrome.
node shoot.mjs --data=transfer-omnijev --out=frames/transfer \
  --cam="-56.8,27.6,2.24,0.32,0,0.24,36" --orbit=8
```

Encoding commands for MP4, GIF and WebP are in
[Trajectory Media Exporter](../tools/trajectory-media/README.md), along with the meaning of the
`--cam` and `--orbit` arguments.

Before exporting, the script compares the episode's `scene_hash` against the scene rebuilt from
the current code. If the scene has changed, the episode is rejected rather than silently replayed
against different geometry — switch back to the revision it was recorded on, or re-run the
experiment.
