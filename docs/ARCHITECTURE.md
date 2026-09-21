# OmniJev v0.2 Architecture

Browser / SDK / HTTP caller → Dynamic scenario definition → Frozen VLM → Short labels and candidate scores → Policy checks → Stable action IDs.

## Input contract

Questions, business status, and candidates are defined at request time. Action ID is separated from the A/B/C labels used for model reading, so the application depends only on semantically stable IDs. New scenarios require no changes to the model or service code. Abstention is explicit candidate metadata, not guessed from strings.

## Execution path

The model processes images and text; the service only adapts. Mode is short label or constrained JSON. No classification head added, no weight changes, no training. SDK core continues v0.1 backend; implementation can be replaced, but available interfaces do not guarantee sufficient capability for all scenarios.

## Dynamic input

The browser sends one request at a time; after completion, the latest camera frame is obtained. Configuration version is incrementally updated; old version responses are not shown; the model call itself is not cancelled. HTTP allows only one in-flight request; others return 429 and do not build stale frame queues. Multi-client does not provide fair queuing.

SDK allows the business side to manage frame numbers and status. The service returns request_id; the business side should combine its capture time and scenario version to recheck timeliness. max_latency_ms starts from the SDK, excluding upstream queue and actual media age; the service cannot know when the caller captured the image.

## Output and calibration

decided / abstained / invalid / stale are explicitly distinguished. Only decided returns action; selected retains model selection. Scores are candidate condition distributions, not accuracy. Heuristic thresholds are disabled by default and cannot be treated as statistical guarantees. No execution device actions, tool calls, or automatic closed-loop control currently exist.

## Performance boundaries

Continuous mode is sampling scheduling, not native video model streaming. Multiple images are sent in order, but the service does not automatically extract frames or sync audio. No shared prefix scheduling, visual feature caching, adaptive model routing, or post-processing calibration. Service layer serializes to avoid native large model competition; backend itself caches according to its configuration.

## Applicable scenarios

Start with labeled experiments in visual sorting, interface state checks, simple quality inspection, and ticket routing with clearly defined candidates. Exact counting, fine-grained natural images, long sequences, and open-set tasks require independent validation. Questions outside the closed set require other/unknown options; a high score cannot establish that no other answer exists in the world.
