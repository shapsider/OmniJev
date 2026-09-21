# OmniJev Embodied Lab

This is the OmniJev Vision Preview Embodied Workbench. It provides local MuJoCo Panda simulation, camera observation, limited candidate actions, perturbations, replay, model comparison, and reproducible benchmark. Source code, asset licensing, and dependency descriptions are retained in this directory.

Run `./setup_embodied.sh` in the parent directory, then `./run_embodied.sh`. Model weights must be downloaded by the user and loaded via a locally compatible backend; the workbench only accesses the backend's HTTP API. Access the browser at `http://127.0.0.1:8766`.

Frontend source code is located in `frontend/`, and built resources are in `src/embodied_jev/web/`. After modifying the frontend, you can run `npm ci && npm run build` with Node 22.12+ or use this project's `pnpm-lock.yaml` to execute `pnpm install --frozen-lockfile && pnpm run build`.

Full documentation available at [Integration Architecture and Reproduction Protocol](../docs/EMBODIED_INTEGRATION.md).
