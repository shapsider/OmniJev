# How do the cameras work?

The workstation has an external camera observing the desktop, and a wrist camera mounted on the hand, moving with the robotic arm. Both cameras come from MuJoCo simulation, each outputting 640 × 480 images.

Cameras capture new frames before and after actions. When the robotic arm or object moves, the next frame will change; while waiting for the model's response, the simulation stays at the current state, and the frame remains unchanged. This is **step-by-step photography**, and there is currently no continuous video input.

[Watch dual-camera demo](DEMOS.md) · [Enable incremental visual planning](PLANNING.md)

## Which cameras to choose?

| Configuration | What can be seen |
| --- | --- |
| Only external camera | Desktop, blocks, tray, and overall position of the robotic arm |
| Only wrist camera | Details near the gripper; field of view moves with the hand and may be partially blocked by fingers |
| Dual cameras | Simultaneously retains overall and close-up views; both images come from the same simulation moment |
| No camera | No images are collected; structured simulation state is used |

When only one camera is enabled, the other is neither rendered nor sent. Direct image and RGB-D observations require at least one camera; selecting no camera switches to non-visual state input. Camera previews can also be enabled in simulation-state mode, where images are for viewing only and are not sent to the model.

| External camera | Wrist camera |
| --- | --- |
| ![External camera original image](planning-initial-external.png) | ![Wrist camera original image](planning-initial-wrist.png) |

## What is the difference between "direct image" and "RGB-D vision"?

**Direct image** passes the original RGB to models that support images, letting the model itself judge the relationship between blocks, trays, and grippers. No object or target coordinates are in the input, and no local color detector runs. The model still knows end-effector position, gripper state, and contact feedback. The two demo segments on the homepage use this route.

**RGB-D vision** first locally searches for red blocks, blue targets, and yellow obstacles, then combines depth and camera calibration to estimate coordinates. The model receives detection results, not the original image. The detector knows the colors of existing objects and that blocks are 4 cm in side length; if colors or shapes change, the detector needs adjustment.

| Input method | Local color detection | Original image sent to model | Model receives object coordinates |
| --- | --- | --- | --- |
| Simulation ground truth | No | No | Directly provided by simulator |
| RGB-D vision | Yes | No | Estimated by detector |
| Direct image | No | Yes | Not provided |

Both visual routes use simulated cameras. Contact feedback, safety checks, and final success judgment are also provided by the simulator, and there is currently no real camera or physical machine control.

## What to do when blocked?

In direct image mode, actual occlusion is preserved, and the model combines the visible scene with recent actions to decide the next step. The "visual basis" written on the page is the model's brief explanation, which still needs to be cross-checked with the scene to assess credibility.

RGB-D mode retains the latest pose for a limited time; after grasping a block, it also combines end-effector displacement and dual-finger contact to estimate its position. When using a dual-camera setup, external detection is prioritized, with wrist supplementation for missing objects. Required objects that remain invisible for a long time and have expired tracking will stop; no simulation ground truth is secretly filled in.

## How to confirm the model received this image?

Experiment JSON saves the viewpoint, acquisition number, byte count, and SHA-256 for each input image. The visual page's "Download observation frame" saves a PNG and a checklist ZIP, which can be verified item by item. Direct images are sent via Chat's native `image_url` or Claude's native `image` block.

Trajectory replay and camera input are distinct: the web timeline replays saved poses, while the vision page shows the latest sample. Homepage videos separately read the archived images from each step and arrange them alongside recorded actions; see [Video Export Instructions](DEMOS.md).

## Validation in this release

The two completed rounds of raw dual-camera images were 32 steps and 43 steps respectively, with one insufficient withdrawal and two API timeouts, see [Visual Planning Results](PLANNING_RESULTS.md).

RGB-D + Rule baseline reran three tasks under dual cameras, each with seed 0, all completed in 8 actions, with 0 model calls. The early single external RGB-D version also saved a successful GPT transfer record, 8 actions, 13 calls. These results are saved separately in [Result Overview](VALIDATION.md) and cannot be mixed with visual planning success rate.

To replace the detector or connect a real camera, start from `perception.py` and add calibration, depth error, and occlusion handling. The extension entry point is [Development Guide](EXTENDING.md).
