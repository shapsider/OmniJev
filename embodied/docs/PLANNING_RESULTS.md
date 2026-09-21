# After the model looks at the image, how to choose the next step?

Here are two real dual-camera visual rounds: one completes a regular transfer, the other re-grasps and completes the task after losing grip contact and the tray being moved. The model looks at the current image each round, selects one of 21 XYZ short steps and claw actions from 21 options; after execution, the new observation is given to the model again.

[🎬 Watch video and GIF](DEMOS.md) · [Run your own round](PLANNING.md) · [Full data report](results/planning-2026-09-20.json)

## Complete a transfer by looking at the image

The model first approaches the block, closes the gripper, lifts it and transfers it toward the tray, then releases it and withdraws. The episode executes **32 actions and receives 32 real model responses**, with success confirmed by the physics checks.

| Record | Result |
| --- | --- |
| Elapsed time | 235.41 seconds |
| Input / Output tokens | 140,800 / 4,320 tokens |
| Final end height | Approximately 0.198 m, exceeding the required 0.17 m |
| Camera archive | 33 samplings, 66 original PNGs |
| Download | [Download MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/vision-transfer.mp4) · [Experiment JSON](results/planning-vision-gpt6-v2-cameras-transfer.json.gz) · [Camera ZIP](results/planning-vision-gpt6-v2-cameras-transfer-cameras.zip) |

The model did not receive the coordinates of the block and tray, nor was any prior grasp or transfer phase given. It received camera images, calibration, robot self-state, and recent action results. No prohibited contact markers were found in the recorded frames.

## After tray movement, re-grasp and adjust route

This episode applied an external perturbation after step 20: the test program moved the tray floor, walls, and evaluation target together **6 cm** along the world X axis. The model then received new images, without new target coordinates or an instruction to move along X.

Before the disturbance, double-finger contact loss occurred during execution. This was not pre-arranged and is separate from the tray movement.

| Action moment | What actually happened |
| --- | --- |
| After step 19 | Double-finger contact lost; robot no longer judged as holding object |
| Step 20 | The model opens the gripper; after the action, the test program moves the tray |
| Steps 21–24 | Model fine-tunes position and descends |
| Step 25 | Model selects close claw, dual-finger contact restored |
| Steps 26–38 | Continue lifting, transferring, and aligning; steps 32 and 34 select X +40 mm and +10 mm respectively |
| Steps 39–43 | Release the gripper and withdraw, physical verification successful |

Re-grab the action sequentially selected by the model; the program did not invoke the preset recovery skill. Total **43 actions, 43 model calls**, took **342.21 seconds**; input / output was **189,594 / 6,037 tokens**. Final end height approximately 0.193 m, no prohibited contact marks found in the recorded frames.

[⬇ Download MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/vision-recovery.mp4) · [Experiment JSON](results/planning-vision-gpt6-v2-live-target-shift-run1.json.gz) · [Camera ZIP: 45 samples, 90 PNGs](results/planning-vision-gpt6-v2-live-target-shift-run1-cameras.zip)

This round can verify the process of "feedback change—new action—actual recovery." However, both changes occurred in the same round, so the added steps cannot be fully attributed to one, nor can the recovery success rate be derived from this round. Standard experiments default to no disturbance; see [Planning Guide](PLANNING.md#why-the-tray-moves-itself) for setup methods.

## What did the two cameras actually see?

Below are the raw PNGs from a standard transport round. Initial state `capture_id=1`, transport state `capture_id=15`, corresponding to after the 14th action.

| Time | External Camera | Wrist Camera |
| --- | --- | --- |
| Initial | ![Initial External](planning-initial-external.png) | ![Initial Wrist](planning-initial-wrist.png) |
| Transporting | ![Transporting External](planning-carrying-external.png) | ![Transporting Wrist](planning-carrying-wrist.png) |

External camera is fixed; the robotic arm and object move within the frame; wrist camera moves with the hand and may be occluded by fingers or palm. Cameras sample at action boundaries and maintain the current view while waiting for model response. Video right side shows model inputs per step; see [Visual Description](DEMOS.md#what-each-part-of-the-visual-means).

Each record's image perspective, sampling number, byte length, and SHA-256 match the camera ZIP verification. Four camera configurations were also verified via actual rendering: disabled cameras collect nothing, enabled perspectives update after motion, and wrist calibration changes with hand movement. These checks confirm image source and update process; model dependence on perspectives requires paired experiments removing images or single-camera setups.

## Which attempts were incomplete?

Besides successful demonstrations, failures and interface errors are retained in the [Full Report](results/planning-2026-09-20.json).

| Condition | Actions / API Calls | Result |
| --- | --- | --- |
| v1 Prompt, No Disturbance | 32 / 32 | After placing in tray, only withdrew to ~0.118 m, did not reach 0.17 m, ultimately stalled |
| v2 Prompt, No Disturbance Attempt | 2 / 3 | 3rd request `ReadTimeout` |
| v2 Prompt, One Attempt with Planned Target Move | 0 / 1 | First request timed out, disturbance not yet occurred |
| Explicit Rule Match, Simulated State Input and Target Move | 40 / 0 | Completed; no visual model involved |

v1 did not specify final withdrawal height to the model. v2 added complete target conditions: object stable at destination for at least 0.4 seconds, gripper released and no longer holding object, end-effector height at least 0.17 m. It did not increase stages, waypoints, or action sequence. Prompt conditions changed, so these development rounds are not merged for success rate calculation; rule-matched cases with object coordinates cannot serve as model rankings under identical input conditions.

## Experiment Setup and Reproducibility

Experiment date: 2026-09-20. Common settings for the two successful demonstrations:

| Item | Setting |
| --- | --- |
| Task / Seed | `transfer` / 7 |
| Control / Observation | `incremental` / `vision`, external + wrist RGB |
| Request / Response Model Name | `gpt-6-astra` / `gpt-6-astra-2026-09-03`, from API configuration and response |
| Prompt Version | `incremental-planning-v2` |
| Action Menu | 21 fixed options, shuffled each round; no task stages |
| Safety preview / probability threshold / budget | Enable / 0 / 80 steps |
| Display rhythm | Normal round headless `speed=0`; perturbed round workbench `speed=4` |

The display wait for the two rounds differs, and the total round time cannot be directly used to compare reasoning speed. The video separately adjusted the playback rhythm, which does not represent real-time speed. Source file hash, incremental input, and trajectory are saved in [machine-readable report](results/planning-2026-09-20.json) and its referenced original files.

```bash
# Use the connection saved in the interface for Chat connection; this incurs real API Call
python scripts/planning_trial.py --saved-connection --cameras both \
  --shuffle-candidates --max-cycles 80 --output runs/vision-transfer

# Step 20 steps, move the target along X Move 6 cm
python scripts/planning_trial.py --saved-connection --cameras both \
  --shuffle-candidates --max-cycles 80 \
  --intervention '{"kind":"target_shift","after_cycle":20,"delta_xy":[0.06,0]}' \
  --output runs/vision-target-shift
```

The script does not overwrite the old directory; failures will also save. The simulator is still responsible for proprioceptive feedback, safety checks, and final scoring. These model experiments only involve the same task and seed, with no unknown objects, cross-task, single-camera, or real-machine evaluation. Early [preset skill nine-round experiments](GPT6_EXPERIMENT.md) and RGB-D detection experiments used different input and control methods, with results listed separately in [result overview](VALIDATION.md).
