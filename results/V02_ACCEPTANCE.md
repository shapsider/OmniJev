# OmniJev v0.2 Acceptance Record

Date: 2026-09-20. Apple M5 Pro / 48 GB, using the existing local Nemotron Omni Q4_K_M. No training and no new downloads.

## Automated validation

- 16 unit/HTTP contract tests passed, covering missing candidate probabilities, stable action IDs, abstention, stale results, busy 429 responses, and invalid HTTP input.
- Real-model SDK acceptance: 30/30 passed.
- SDK median latency: 585.5 ms. Includes media reading, encoding, and API requests inside the SDK; excludes model loading.
- Raw record: acceptance-v02.jsonl. The sample consists of 26 existing synthetic/hand-written conditions and 4 newly added Chinese routing messages; these are not 30 independent natural scenes.

## Browser acceptance

- The local workbench connected to the real model.
- The red sample returned `red_bin`; switching to the blue sample returned `blue_bin`.
- Built-in 640×480 image: the first observation request took about 4318 ms, and a later request for a different image took about 2108 ms. This is not a statistical benchmark.
- After switching the text-routing template, consecutive requests returned `delivery`; clicking Stop prevented new requests.
- Repeated identical text requests showed roughly 80–100 ms warm-cache responses; this cannot be generalized to new images or requests.
- Greetings without task information returned `abstained` / `unknown` and produced no executable action.
- Camera input is implemented, but the user camera was not requested; physical camera-frame acceptance remains incomplete.

## Capability boundaries

This is a dynamic decision service around a frozen model, not a newly trained model. Low latency varies with image size, cache, context, and hardware. There is not yet sufficient evidence for natural-scene quality checks, complex interfaces, or fine-grained recognition. Native audio remains unavailable; multiple images and camera sampling are not native video temporal understanding.

## Startup and status

Run `sh run_local.sh` and open http://127.0.0.1:8765. The current source has been initialized as a local Git repository; it has not been uploaded or published to a remote repository. The model service and workbench bind only to local addresses.
