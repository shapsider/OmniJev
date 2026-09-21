# Demo and Video Export

README's experiment section defaults to expanding three animated segments: Jev hierarchical XYZ, GPT dual-camera vision transfer, and tray movement followed by re-grasping. Generated from saved experiment records, no need to re-request model.

| Demo | Action Count | Original Experiment Time | Video / GIF |
| --- | --- | --- | --- |
| Jev Hierarchical XYZ with Real Probabilities | 88 | 79.71 seconds | [Download MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/jev-hierarchical.mp4) · [GIF](media/jev-hierarchical.gif) |
| Look-and-Grasp and Transfer | 32 | 235.41 seconds | [Download MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/vision-transfer.mp4) · [GIF](media/vision-transfer.gif) |
| Tray Movement and Re-grasp | 43 | 342.21 seconds | [Download MP4](https://github.com/FBddcz/embodied-jev/raw/refs/heads/main/docs/media/vision-recovery.mp4) · [GIF](media/vision-recovery.gif) |

MP4 can be played after download, resolution 1280 × 1080, suitable for pausing to examine decisions; Jev GIF is **8x speed**, approx 14 seconds; two visual GIFs are **5x speed**, approx 9 and 12 seconds, all displayed by default in experiment section. Full experiment setup and failure rounds see [Visual Planning Results](PLANNING_RESULTS.md).

## Jev's Probability GIF

Jev GIF is generated from the second round's real record: left side redraws saved poses, right side shows eight sub-goals and four action channels' real probability. Model input is coordinates and contact state, no images. Video retains the loss of grasp at step 80, followed by gripper opening and withdrawal; detailed constraints see [Jev Results Explanation](JEV_RESULTS.md). This release summary and media, hierarchical controller still under local development.

## How to Read the Two Visual Demonstrations?

- **Left Action Replay**: Redrawn using saved joint and object poses from experiment, no re-execution of control strategy or physical trajectory.
- **Right Two Cameras**: PNGs actually sent to model in that step. Action proceeds with current step's input, switches to new observation only when moving to next step; final frame shows final observation.
- **Bottom-Left Candidate Panel**: Shows actual candidate order per round, green highlights model-selected item, and displays real API call duration for that round.
- **Scoring Source and Action Description**: Candidate probability values appear only if returned by service provider. These two rounds' GPT interface provides no probability, screen explicitly marks "This interface does not provide"; green does not indicate 100% probability. Short action descriptions come from model reply.
- **Physical Feedback**: Marks action execution, object retention changes, and failed grasp. Opening, disturbance, and ending subtitles are additional demo explanations, not model replies.

MP4 retains all actions, each step shown for 1.2 seconds, API wait omitted, normal video approx 43 seconds, disturbance video approx 59 seconds. GIF accelerated 5x on this basis. This is not real-time speed of robot or model. Camera originals are merely scaled layouts; GIF and MP4 compression alter pixel display, original PNG and hash remain in camera ZIP.

"Xingzhi · EmbodiedJev" is the workbench name; screen will separately list actual model calls. Two dual-camera demonstrations are GPT visual experiments; single-column Jev GIF uses official Jev's real probability record.

In second segment, tray moves 6 cm along X axis after step 20, this is enabled external disturbance. After step 19, dual-finger contact loss is actual execution situation; re-grasped at step 25. Video labels them separately, not synthesizing once-preset recovery animation.

## Re-export from Visual Records

First install optional video dependencies:

```bash
python -m pip install -e '.[video]'
```

Run from repository root directory:

```bash
python scripts/render_demo.py \
  --episode docs/results/planning-vision-gpt6-v2-cameras-transfer.json.gz \
  --cameras docs/results/planning-vision-gpt6-v2-cameras-transfer-cameras.zip \
  --output runs/demo-transfer --title 'Use images to complete grasping and transfer'

python scripts/render_demo.py \
  --episode docs/results/planning-vision-gpt6-v2-live-target-shift-run1.json.gz \
  --cameras docs/results/planning-vision-gpt6-v2-live-target-shift-run1-cameras.zip \
  --output runs/demo-recovery --title 'Regrasp and adjust the route after the tray moves'
```

Requires available MuJoCo rendering environment and Chinese font. The script will attempt common system fonts, and you can specify a font file with `--font`. `--gif-speed` defaults to 5 and can be adjusted separately. Outputs MP4, GIF, cover PNG, and JSON describing the source; existing files are not overwritten unless `--overwrite` is explicitly provided.

Before export, it checks scene version, experiment ID, and hash of each model input image. If the scene changes, switch back to the original experiment code version before exporting. The current script is designed for incremental visual recording of dual-camera transfer tasks, supporting annotation of target movement; other experiment types require corresponding adaptation.

[Normal demonstration file information](media/vision-transfer.json) · [Disturbed demonstration file information](media/vision-recovery.json)
