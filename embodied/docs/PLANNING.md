# Let the model control the robotic arm step by step

Want to observe how the model plans, choose **Incremental XYZ · Closed-loop planning**. Model decides one short action at a time, robotic arm executes, then provides new observation. You can see how it approaches object, adjusts position, or reattempts after losing grasp.

[Watch real demo](DEMOS.md) · [Existing experiment results](PLANNING_RESULTS.md)

## Run it in the interface

1. Save and test an image-capable OpenAI-compatible or native Claude connection.
2. Select "Transfer to tray", set "Action decision method" to "Incremental XYZ · Closed-loop planning".
3. Set "Observation source" to "Direct image · Multimodal model", enable dual camera, or enable only one.
4. Set a sufficient action budget in “Execution settings”, such as 80 steps. Keep “No perturbation applied” for a standard demonstration.
5. Click "Run experiment", or use "Single step" to execute one action at a time. Right side shows model's action intent, visual basis, and selected displacement.
6. After completion, export experiment JSON; "Visual" page's "Download observation frames" can save original PNG and image list separately.

Direct image mode does not tell model coordinates of block and target. It receives selected camera's RGB, camera calibration, end position, gripper, and contact feedback. Visual judgment of correctness must combine actual action and next frame; cannot rely solely on model's written description.

## Why does the tray move by itself?

This is optional **disturbance test**, default off. In "Execution settings → External evaluation disturbance", select "Move target", set step number after which to move, and X/Y displacement.

The second demo on the homepage uses “after step 20, X +0.06 m, Y 0”. The test program moves the tray floor and walls, and the model then determines the target position from new images. It receives neither the new target coordinates nor a prompt to move in the X direction.

Tray movement is performed by test program, not robotic arm action. In that round, bilateral contact loss occurred separately; this was not pre-arranged loss of grasp, model re-grasps after feedback change. Both events happened in same round, so cannot fully attribute extra steps to one change.

To avoid testing disturbance, select "No disturbance applied" then reset. Settings apply in new experiment. Can also test "Move block", but block will not be forcibly moved while being grasped by gripper.

## Which actions can the model choose?

All tasks share 21 options:

| Action | Selectable range |
| --- | --- |
| Move along world coordinates X, Y, Z positive or negative directions | 40, 10, or 2 mm per step |
| Operate gripper | Open, close |
| Do not move temporarily | Keep current position |

The model decides which action to take. The program handles inverse kinematics and joint control, and checks whether the selected action is executable. Rejected actions and reasons enter the next feedback round; the program does not silently switch to another action.

"Preset skill selection" is another control method: the program generates grasp, transfer, and other skill targets based on object position, then lets the model choose. The first two videos on the homepage use incremental XYZ; early eight-action experiments use preset skills, and results are recorded separately.

## Can planning be done without images?

Yes. Control methods and observation sources are two independent settings:

| Observation source | What the model actually receives |
| --- | --- |
| Simulated ground truth | Objects, target coordinates, and robot state provided by the simulator |
| RGB-D vision | Coordinates estimated by the local detector from images and depth, plus robot state |
| Direct image | Raw RGB image from enabled camera, calibration, and robot self-state |

When no camera is present, simulated state is used. Simulated state mode also allows opening the camera for viewing, but preview images are not sent to the model. Camera configuration see [Vision Guide](VISION.md). Current Jev, structured decision service, and MiniCPM adapters handle state input; direct image only supports Chat / Claude routes.

## Reproduce experiments via command line

The script below uses the connection saved in the interface to run one round, at most 80 model calls. Real API costs will be incurred, and the output directory must be new.

```bash
python scripts/planning_trial.py --saved-connection --cameras both \
  --shuffle-candidates --max-cycles 80 --output runs/vision-transfer

python scripts/planning_trial.py --saved-connection --cameras both \
  --shuffle-candidates --max-cycles 80 \
  --intervention '{"kind":"target_shift","after_cycle":20,"delta_xy":[0.06,0]}' \
  --output runs/vision-target-shift
```

Output includes setting and source file hashes, experiment JSON, and camera ZIP. Timeouts and failures are saved as usual, without automatic retry or switching to rule-based strategy.

`--cameras` optional `external`, `wrist`, `both`, `none`; when using `none`, add `--observation privileged`. Another batch entry `embodied-jev benchmark` uses environment variables to connect; see [Technical Guide](TECHNICAL_GUIDE.md#models).

## How to verify that the model truly adjusts?

Connect the current image, selected action, actual displacement, and next frame. For example, check whether direction changes after target movement, whether re-grasping occurs after losing contact, or whether a valid solution is chosen after an action is rejected. When comparing experiments, keep task, seed, budget, and input consistent, and save all failures.

Current evidence comes from a small number of fixed scenarios. More objects, camera combinations, and unknown layouts still need testing; this project does not treat these demonstrations as proof of general robot planning.
