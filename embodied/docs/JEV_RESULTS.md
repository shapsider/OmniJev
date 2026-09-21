# Jev hierarchical XYZ experiment results

In these experiments, Jev grasped the block, transferred it to the tray, and withdrew. Both episodes met the existing simulation success criteria, but both lost their grasp during lowering and opened the gripper only after the block had fallen into the tray. Precise placement still needs improvement.

## Settings and results

Both runs use `jev-1.13.0`, transport task seed 7, simulation coordinates and contact feedback, no image input. Action budget 160 steps, probability threshold 0, safety preview enabled, no rule-based selection.

| Round | Action / API request | Actual time | Request median delay | Max lift |
| --- | --- | --- | --- | --- |
| First round verification | 89 / 178 | 72.43 seconds | 361 ms | 189.7 mm |
| Second round page demonstration | 88 / 176 | 79.71 seconds | 326 ms | 189.6 mm |

First round is headless execution, second round retains 4× execution animation, so total round duration cannot be explained solely by model latency. At the end of both rounds, blocks have target support and remain stable, gripper is open, end effector withdraws to approximately 175 mm. [Result summary](results/jev-hierarchical-summary-2026-09-20.json)

## What the model decides

Each step first has the model select from eight sub-goals: approach, grasp, lift, transfer, place, release, withdraw, and complete, then use a single request to simultaneously decide the positive, maintain, or negative direction for X/Y/Z, and the open, maintain, or close state of the gripper.

The program provides task description, measurement error and reference points, determines 2–12 mm steps per axis, and performs IK, safety checks, and physical result judgment. Model error direction will not be corrected by the program to the correct direction. This is a decision experiment guided by task knowledge, not a model learning robot control from scratch.

## What the animation shows

[8× speed GIF](media/jev-hierarchical.gif) and [MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/jev-hierarchical.mp4) from the second round's 88-step recording. Left side redraws poses according to recorded posture, right side shows actual sub-goals and four-channel probabilities, green indicates selected. Probabilities for each group are shown separately, not synthesized for task success rate.

The MP4 is 110.6 seconds long and shows each step for 1.2 seconds; the GIF is approximately 13.8 seconds long. They omit API waiting time. Neither the model nor the physics experiment was rerun to produce them. The original model inputs were coordinates and contact states; the displayed scenes are not camera images sent to Jev. [Media hashes and provenance](media/jev-hierarchical.json)

## Remaining issues

In round one step 81 and round two step 80, during placement, bilateral contact is lost, block falls onto tray. Model then selects approach and opens gripper, then selects withdraw; neither round selects `release` sub-goal. Video retains and marks loss of grasp, cannot represent final state as stably and precisely placed via written description.

Two development rounds with same seed cannot represent general success rate, nor can they be directly ranked against image-input GPT demonstrations. Experiment uses hierarchical control from local development; current public workbench version does not include this mode; this release's result summary and demo media do not include full original trajectory or controller code.
