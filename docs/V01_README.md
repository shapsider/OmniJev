# OmniJev v0.1

A local, training-free prototype for finite-option decisions. Tested on Apple M5 Pro / 48 GB with Nemotron 3 Nano Omni Q4_K_M and Qwen3.8-27B MLX 4-bit.

**The current validation scope is text, images, and ordered image frames. The current Nemotron GGUF/projection/runtime combination explicitly reports audio as unavailable, so this version is not a completed all-modal model.** It provides an audio request interface and failure diagnostics, and does not present ASR transcripts as native audio understanding.

## Quick start

Run from the project root with system Python 3.9+; no pip installation is required. Bionic should already be open.

```sh
sh scripts/start_bionic.sh nemotron
python3 -m omnijev --case data/example.json
```

Custom question:

```sh
python3 -m omnijev \
  --image data/assets/spatial0.png \
  --question 'Is the red circle to the left of the blue square?' \
  --options yes no 'insufficient evidence'
```

Constrained JSON comparison:

```sh
python3 -m omnijev --case data/example.json --mode json
```

Qwen: first unload the experimental model with `lms unload omnijev-nemotron`, then run `sh scripts/start_bionic.sh qwen`; add `--model omnijev-qwen` when calling it. Do not load both large models at the same time. If the `lms` CLI is not on PATH, its full path is `/Applications/Bionic.app/Contents/Resources/app/.webpack-bionic/lms`.

## Output meaning

- `choice` / `value`：the option letter and original option text.
- `valid`：the output belongs to the candidate set; this does not imply semantic correctness.
- `scores.probabilities` at the first returned answer position, normalized scores among canonical single-letter candidate tokens; **these are not calibrated correctness probabilities**.
- `candidate_mass`：the mass of these canonical candidates in the returned token distribution; space variants are excluded.
- `incomplete_top_k`：a candidate is absent from the API-returned top-k; the entire probability field is then null, never zero-filled or fabricated.
- `latency_seconds`：API round-trip time, including server computation; excludes model loading, client file reads, and base64 encoding. It must not be called full end-to-end latency.
- `response`：when saved to a file, contains the complete raw model response for auditing.

`letter` method actually generates a short label and reads logprobs; it is not an internal zero-decoding forward. Nemotron’s hidden structural tokens mean `max_tokens=1` cannot produce an answer, so the budget is 4. The JSON budget is 32; both disable thinking, withtemperature=0。

## Reproduce the experiment

```sh
python3 scripts/build_fixture.py
python3 scripts/build_stress.py
python3 -m unittest discover -s tests -v
python3 scripts/run_benchmark.py --model omnijev-nemotron --output results/new-run.jsonl --repeats 2
python3 scripts/run_benchmark.py --model omnijev-nemotron --fixture data/stress.json --output results/new-stress.jsonl --repeats 2
python3 scripts/summarize.py results/new-run.jsonl results/new-stress.jsonl
```

Result files must not be overwritten. `summarize.py` recomputes canonical-letter scores and updates `results/summary.json` and `results/scored-records.jsonl`; raw run files remain unchanged. The current summary keeps both API error counts and total request counts; errors are not mixed into fast-inference latency statistics.

## Scope and limitations

The base fixture has 19 programmatically generated samples: 17 text/vision diagnostics and 2 audio capability probes. The stress set has 9 additional diagnostics with different questions/candidate permutations over the same media. Two repeated rounds are not independent samples, and derived questions are not independent either.

Request order is shuffled with a fixed seed after an unscored warm-up. The service’s default cache is used without separating cold and warm prefixes; only descriptive latency is reported, with no statistical-significance or method-speedup claims. There is no training, calibration, or test-set threshold selection, and no guarantee for large real-world data, long videos, complex audio-video reasoning, shared-prefix parallel engines, or risk controls.

The raw data are simple, and saturated accuracy cannot demonstrate research novelty. This project is a runnable starting point for further research.

## Identified backend differences

1. The Bionic-compatible interface requires `reasoning_effort=none`; passing only `chat_template_kwargs.enable_thinking=false` did not disable Nemotron thinking.
2. MLX `top_logprobs` maximum is 10. Nemotron’s first round used 20; the current code consistently uses 10.
3. Bionic `/v1/chat/completions` rejects `input_audio` (HTTP 400). Direct invocation with the bundled llama.cpp, the same model, and projection still rejects audio (HTTP 500); `results/native-props.json` contains `audio=false`.
4. Multi-frame image diagnostics only input images in sequence; they are not native continuous-video or audio-video synchronization tests.

## Main files

- `omnijev/core.py` finite-option interface, strict parsing, and candidate-score extraction.
- `omnijev/__main__.py` CLI entry point supporting custom images, audio, text, and options.
- `scripts/` startup, diagnostic-data generation, execution, and summarization.
- `tests/test_core.py` integrity tests preventing probability misreporting.
- `results/EXPERIMENT_REPORT.md` local experiment conclusions.
- `results/environment.json` model files, quantization, and environment records; credentials are not included.

This project does not reproduce TypeSafe’s unpublished Jev architecture or RLCD. It uses a general frozen model to implement a similar finite-option interface.
