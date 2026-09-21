# Participating in development

Welcome to contribute documentation, models, interfaces, or tasks. If you encounter issues, please first open an Issue with reproduction steps and runtime environment; see [Secondary Development Guide](docs/EXTENDING.md) for entry points.

## Local Check

After setting up the virtual environment according to [README](README.md), run:

```bash
python -m pip install -e '.[test]'
npm ci
npm run build
pytest -q
npx playwright install chromium
npm run test:ui
```

Browser testing uses a separate 8099 port and memory configuration and does not access the system keychain. The frontend formatting command is `npx prettier --write frontend/ vite.config.js`.

## Submit code or experiment

- PR description of what was changed, why it was changed, and how it was verified. Interface changes should include desktop and mobile size screenshots.
- New task requires connecting observation, candidate actions, physical feedback, pause/stop, and replay; default grasping continues to rely on real gripper contact.
- Experimental results include model version, task, seed, scene, and decision configuration, with reproduction commands and failure records retained. Rule baseline and model performance are reported separately; candidate probability is not treated as physical success rate.
- API Key only configured on your own computer. Check changes before submission, do not upload keys, private experiment records, model caches, or virtual environments; retain license statements for project and robot assets.
