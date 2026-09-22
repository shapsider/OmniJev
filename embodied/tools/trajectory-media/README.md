# Trajectory Media Exporter

Turns a saved embodied episode into video/GIF that matches what the workbench
shows in the browser. The workbench renders trajectories client-side with
Three.js (see `embodied/frontend/robot-scene.js`), so the same view can be
reproduced headlessly without starting the inference backend.

## Pipeline

```bash
# 1. Reconstruct MuJoCo forward kinematics from the saved episode (Python + mujoco).
python scripts/export_trajectory_frames.py \
  --episode results/embodied/skills-seed0/transfer-0-omnijev.json \
  --out embodied/tools/trajectory-media/data/transfer-omnijev

# 2. Render camera setup and inspect it interactively.
cd embodied/tools/trajectory-media
npx vite --host 127.0.0.1 --port 5199      # uses vite from embodied/node_modules
# open http://127.0.0.1:5199/?data=transfer-omnijev

# 3. Dump one PNG per frame with headless Chrome (reuses the playwright dev dep).
node ../../node_modules/@playwright/test/cli.js --version >/dev/null 2>&1 || true
node shoot.mjs --data=transfer-omnijev --out=frames/transfer \
  --cam="-56.8,27.6,2.24,0.32,0,0.24,36" --orbit=8
```

`--cam` is `azimuth,elevation,distance,lookX,lookY,lookZ,verticalFov` — the
defaults equal the workbench home camera (position `1.4 -1.65 1.27`, target
`0.32 0 0.24`, fov 36). `--orbit` sweeps the azimuth by ±N/2 degrees across the
clip for a slow camera arc. `--only=0,150,282` renders single probe frames.

The renderer needs a Chromium install. It launches the system Google Chrome via
`channel: "chrome"`; pass Playwright's own browser instead by editing the
`chromium.launch` call if Chrome is not installed.

## Encoding

PNG frames are encoded outside the browser. `ffmpeg` is the only requirement; a
static build is available from `pip install imageio-ffmpeg`.

```bash
ffmpeg -framerate 25 -i frames/transfer/%04d.png \
  -vf scale=1280:720:flags=lanczos -c:v libx264 -preset slow -crf 18 \
  -pix_fmt yuv420p -movflags +faststart docs/media/omnijev-transfer.mp4
```

For the inline README GIF, quantise to 256 colours at half rate to keep the file
around 3 MB for a ~11 s clip:

```bash
ffmpeg -framerate 25 -i frames/transfer/%04d.png -filter_complex \
"fps=12.5,scale=1000:-1:flags=lanczos,split[a][b];\
[a]palettegen=max_colors=256:stats_mode=full[p];\
[b][p]paletteuse=dither=floyd_steinberg" -loop 0 docs/media/omnijev-transfer.gif
```

## Honest reading of the output

The overlay lists the episode's real configuration: observation mode, control
mode, model calls, token counts and wall-clock time. The replay is the *saved*
pose stream — no policy or physics is re-executed, and no model is called. For
`privileged` episodes the model never saw an image; the rendered scene is a
visualisation of simulator state, not of model input. Vision episodes archive
their camera PNGs separately in `*.cameras.zip`.
