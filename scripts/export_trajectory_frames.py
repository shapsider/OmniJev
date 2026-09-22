"""Reconstruct browser-ready 3D frames from a saved embodied episode.

The workbench replays trajectories in the browser: `GET /api/replay/<i>`
recomputes MuJoCo forward kinematics from the saved `qpos` and hands geometry
positions/rotations to Three.js. This script performs the same reconstruction
offline, so a released episode can be turned into video or GIF without starting
the inference backend or the workbench.

Outputs, written to --out:

- ``scene.json``  geometries and meshes, identical to ``GET /api/scene``
- ``frames.json`` one entry per saved frame: positions, rotations, cycle, phase
- ``meta.json``   episode header plus per-cycle decisions, for on-screen captions

See ``embodied/tools/trajectory-media/README.md`` for the rendering step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "embodied" / "src"))

import mujoco  # noqa: E402
import numpy as np  # noqa: E402
from embodied_jev.physics import TASKS, RobotWorld  # noqa: E402


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True, help="episode JSON under results/embodied/")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--max-frames", type=int, default=0, help="0 keeps every frame")
    args = parser.parse_args()

    episode_path = Path(args.episode)
    episode = json.loads(episode_path.read_text())
    saved_frames = episode["frames"]
    if args.max_frames:
        saved_frames = saved_frames[: args.max_frames]

    world = RobotWorld(
        task=episode["task"], seed=episode["seed"], scene_config=episode.get("scene_config")
    )

    # A saved qpos only means something on the scene it was recorded on.
    expected = episode.get("scene_hash")
    if expected and world.scene_hash != expected:
        raise SystemExit(
            f"scene hash mismatch: episode {expected[:12]} vs rebuilt {world.scene_hash[:12]}. "
            "Switch back to the revision the episode was recorded on before exporting."
        )
    print(f"scene hash verified: {world.scene_hash[:16]}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    scene = world.scene()
    (out / "scene.json").write_text(json.dumps(scene, separators=(",", ":")))

    # Same correction Session.replay_frame applies to intervened episodes.
    target_ids = list(world.target_geom_ids)
    target = np.asarray(world.target, dtype=float)

    frames = []
    for index, saved in enumerate(saved_frames):
        world.data.qpos[:] = saved["qpos"]
        mujoco.mj_forward(world.model, world.data)
        positions = world.data.geom_xpos.copy()
        shift = saved.get("evaluation_target")
        if shift is not None:
            for gid in target_ids:
                for axis in (0, 1):
                    positions[gid][axis] += shift[axis] - target[axis]
        frames.append({
            "i": index,
            "time": round(float(saved["time"]), 5),
            "cycle": saved.get("cycle"),
            "phase": saved.get("phase"),
            "positions": np.round(positions, 5).tolist(),
            "rotations": np.round(world.data.geom_xmat, 6).tolist(),
        })

    (out / "frames.json").write_text(json.dumps(frames, separators=(",", ":")))

    methods = {}
    for entry in episode.get("history", []):
        decision = entry.get("decision") or {}
        intent = entry.get("intent") or {}
        methods[str(entry["cycle"])] = {
            "phase": entry.get("phase"),
            "label": entry.get("label"),
            "skill": intent.get("choice"),
            "choice": decision.get("choice"),
            "selected_probability": decision.get("selected_probability"),
            "latency_ms": decision.get("latency_ms"),
            "model_call": decision.get("model_call"),
        }

    meta = {
        "episode_id": episode.get("id"),
        "source": repo_path(episode_path),
        "task": episode["task"],
        "task_name": TASKS[episode["task"]]["name"],
        "goal": TASKS[episode["task"]]["goal"],
        "seed": episode["seed"],
        "provider": episode.get("provider"),
        "model": episode.get("model"),
        "observation_mode": episode.get("observation_mode"),
        "control_mode": episode.get("control_mode"),
        "camera_views": episode.get("camera_views") or [],
        "status": episode.get("status"),
        "success": bool(episode.get("success")),
        "policy_version": episode.get("policy_version"),
        "cycles": len(episode.get("history", [])),
        "model_calls": episode.get("model_calls"),
        "input_tokens": episode.get("input_tokens"),
        "output_tokens": episode.get("output_tokens"),
        "wall_seconds": episode.get("wall_seconds"),
        "frame_count": len(frames),
        "sim_seconds": round(float(saved_frames[-1]["time"] - saved_frames[0]["time"]), 3),
        "methods": methods,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))

    print(
        f"{out}: {len(frames)} frames, {len(scene['geometries'])} geometries, "
        f"{meta['sim_seconds']}s simulated, success={meta['success']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
